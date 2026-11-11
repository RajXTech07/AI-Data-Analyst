# 13 — Backend Schemas and Project Architecture

## 1. Layered structure

```
Routers (HTTP)  →  Services (business logic)  →  Repositories/DB
                         │
                         ├→ Agent (orchestrator, prompts, validator)
                         └→ Tools (pure analysis functions)  ← also used by MCP
```

Rules:
- Routers only parse input, call a service, return a schema.
- Services own transactions and authorization checks.
- **Tools are pure**: DataFrame in, `ToolResult` out. No DB, no HTTP, no LLM.
- The agent talks to tools only through the registry.

## 2. Folder structure

```
apps/api/app/
├── main.py                    # app factory, middleware, routers
├── api/
│   ├── deps.py                # get_db, get_current_user
│   └── v1/
│       ├── auth.py
│       ├── datasets.py
│       ├── analyses.py        # includes SSE endpoint
│       ├── reports.py
│       └── health.py
├── core/
│   ├── config.py              # pydantic-settings
│   ├── security.py            # hashing, JWT
│   ├── errors.py              # exception classes + handlers
│   └── logging.py
├── db/
│   ├── base.py
│   ├── session.py
│   ├── models/                # SQLAlchemy models, one file per table
│   └── migrations/            # alembic
├── schemas/                   # Pydantic request/response models
│   ├── auth.py
│   ├── dataset.py
│   ├── analysis.py
│   ├── finding.py
│   ├── tool.py
│   └── events.py
├── services/
│   ├── datasets.py            # upload, validate, profile, delete
│   ├── analyses.py            # create, cancel, steer, query
│   ├── reports.py
│   ├── storage.py             # local / s3 backends
│   └── events.py              # pub/sub for SSE
├── agent/
│   ├── orchestrator.py        # the loop
│   ├── llm/
│   │   ├── base.py            # LLMClient protocol
│   │   ├── gemini.py
│   │   └── openai.py
│   ├── prompts.py
│   ├── planner.py
│   ├── interpreter.py
│   └── validator.py           # numeric grounding checks
├── tools/
│   ├── registry.py            # name → ToolSpec
│   ├── base.py                # ToolResult, helpers (require_columns, apply_filters)
│   ├── profile.py
│   ├── statistics.py
│   ├── groupby.py
│   ├── correlation.py
│   ├── outliers.py
│   ├── missing.py
│   ├── duplicates.py
│   ├── trend.py
│   ├── tests.py               # statistical_test
│   └── charts.py
├── reports/
│   ├── templates/report.html.j2
│   └── builder.py
└── mcp_server/
    └── server.py
```

## 3. Core Pydantic schemas

```python
# schemas/tool.py
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field

class Filter(BaseModel):
    column: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "notnull", "isnull"]
    value: Any | None = None

class ToolResult(BaseModel):
    ok: bool
    data: dict | list | None = None
    warnings: list[str] = []
    error: str | None = None
    row_count_used: int | None = None
    duration_ms: int | None = None

class ToolCall(BaseModel):
    name: str
    arguments: dict
```

```python
# schemas/dataset.py
class ColumnProfile(BaseModel):
    name: str
    dtype: Literal["numeric", "categorical", "datetime", "boolean", "text"]
    null_pct: float
    unique: int
    stats: dict | None = None
    top_values: list[dict] | None = None
    flags: list[str] = []          # constant, id_like, mixed_types, inconsistent_labels

class DatasetProfile(BaseModel):
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    duplicate_rows: int
    missing_total_pct: float

class DatasetOut(BaseModel):
    id: UUID
    filename: str
    n_rows: int
    n_cols: int
    size_bytes: int
    created_at: datetime
```

```python
# schemas/analysis.py
class AnalyzeRequest(BaseModel):
    question: str | None = Field(default=None, max_length=1000)
    options: AnalyzeOptions = AnalyzeOptions()

class AnalyzeOptions(BaseModel):
    exclude_incomplete_rows: bool = False
    filters: list[Filter] = []

class PlanStep(BaseModel):
    id: int
    goal: str
    hypothesis: str | None = None
    suggested_tool: str | None = None

class InvestigationPlan(BaseModel):
    steps: list[PlanStep] = Field(max_length=12)

class AnalysisOut(BaseModel):
    id: UUID
    dataset_id: UUID
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    question: str | None
    plan: InvestigationPlan | None
    created_at: datetime
```

```python
# schemas/finding.py
class StatEvidence(BaseModel):
    test: str | None = None
    statistic: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    n: int | None = None
    assumptions: dict | None = None

class FindingDraft(BaseModel):          # what the LLM must return
    title: str = Field(max_length=160)
    observation: str
    interpretation: str
    limitations: str
    hypothesis_status: Literal["supported", "rejected", "inconclusive", "descriptive"]
    evidence_execution_ids: list[UUID] = Field(min_length=1)

class FindingOut(FindingDraft):
    id: UUID
    statistical_evidence: StatEvidence
    confidence: Literal["low", "medium", "high"]   # computed by code
    chart_ids: list[UUID] = []
```

```python
# schemas/events.py
class Event(BaseModel):
    event: Literal["status", "plan", "tool_started", "tool_finished",
                   "hypothesis", "finding", "chart", "message_delta", "error", "done"]
    data: dict
```

## 4. Registry pattern

```python
# tools/registry.py
@dataclass
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[BaseModel, pd.DataFrame], ToolResult]

REGISTRY: dict[str, ToolSpec] = {}

def tool(name: str, description: str):
    def deco(fn):
        args_model = get_type_hints(fn)["args"]
        REGISTRY[name] = ToolSpec(name, description, args_model, fn)
        return fn
    return deco

def llm_tool_schemas() -> list[dict]:
    return [{"name": s.name, "description": s.description,
             "parameters": s.args_model.model_json_schema()} for s in REGISTRY.values()]

def run_tool(name: str, raw_args: dict, df: pd.DataFrame) -> ToolResult:
    spec = REGISTRY.get(name)
    if spec is None:
        return ToolResult(ok=False, error=f"Unknown tool '{name}'")
    try:
        args = spec.args_model.model_validate(raw_args)
    except ValidationError as e:
        return ToolResult(ok=False, error=str(e))
    with timeout(settings.tool_timeout_seconds):
        return spec.fn(args, df)
```

## 5. Orchestrator skeleton

```python
async def run_analysis(analysis_id: UUID):
    ctx = await load_context(analysis_id)              # dataset, df, profile, question
    plan = await planner.make_plan(ctx)
    await emit(analysis_id, "plan", plan)

    for step in plan.steps:
        if await is_cancelled(analysis_id) or ctx.budget_exhausted():
            break
        await apply_pending_steer(ctx, plan)
        result = await execute_step(ctx, step)         # LLM tool-call + registry
        verdict = validator.judge(step, result)
        if verdict.needs_revision:
            plan.extend(await planner.revise(ctx, step, result))

    drafts = await interpreter.write_findings(ctx)
    drafts = validator.ground_numbers(drafts, ctx.results)
    await save_findings(analysis_id, drafts)
    await finish(analysis_id)
```

## 6. Error classes

| Class | HTTP |
|-------|------|
| `NotFoundError` | 404 |
| `ValidationFailed` | 422 |
| `FileTooLarge` | 413 |
| `UnsupportedFile` | 415 |
| `AnalysisConflict` | 409 |
| `ToolArgumentError` | internal, returned to LLM |
| `LLMProviderError` | internal, retried |

## 7. Frontend structure (Next.js)

```
apps/web/
├── app/
│   ├── (auth)/login, register
│   ├── datasets/                 # workspace list + upload
│   ├── datasets/[id]/            # preview + profile
│   ├── analyses/[id]/            # investigation room, findings, chat
│   ├── analyses/[id]/explore/    # chart explorer
│   └── reports/[id]/
├── components/                   # DataTable, FindingCard, ToolTimeline, ChartView, ChatPanel
├── lib/
│   ├── api.ts                    # typed fetch client
│   ├── sse.ts                    # fetch-based SSE with auth header + reconnect
│   └── types.ts                  # mirrors backend schemas
└── store/                        # Zustand or React Query
```

Generate TypeScript types from the FastAPI OpenAPI schema (`openapi-typescript`) so frontend and backend never drift.

## 8. Deployment view

```
Browser ── HTTPS ──> Vercel (Next.js)
                        │ REST + SSE
                        ▼
                 Render/Fly (FastAPI, Docker)
                   │        │         │
                   ▼        ▼         ▼
              Postgres   S3 bucket   LLM API
```

## 9. Design principles to keep

1. Tools are deterministic and pure.
2. Findings cannot exist without evidence rows.
3. Confidence is computed by code, not claimed by the LLM.
4. All LLM inputs/outputs go through typed schemas.
5. One registry feeds the agent, the API docs, and the MCP server.
6. Build the analysis engine and tests before the agent, and the agent before the UI.
