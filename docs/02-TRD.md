# 02 — Technical Requirements Document (TRD)

## 1. Architecture principle

```
LLM  = plans, picks tools, explains results   (never calculates)
Python = executes whitelisted tools, returns numbers
Backend = validates every tool call, enforces limits, stores evidence
Frontend = shows the investigation live and lets the user steer it
```

## 2. Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind, shadcn/ui, Plotly.js | Dashboard, charts, SSE |
| Backend | Python 3.11+, FastAPI, Pydantic v2 | Typed validation of tool arguments |
| Analysis | Pandas, NumPy, SciPy, scikit-learn | Deterministic computation |
| Charts | Plotly (server builds JSON spec, client renders) | Interactive, serialisable, testable |
| LLM | Gemini or OpenAI via native function calling | No framework needed for MVP |
| DB | PostgreSQL 15+ (JSONB), SQLAlchemy 2.0, Alembic | Persistent state |
| Storage | Local disk (dev), S3-compatible (prod) | Uploaded CSVs and reports |
| Reports | Jinja2 → HTML → WeasyPrint PDF | Simple, reproducible |
| Infra | Docker, docker-compose, GitHub Actions | Reproducible environment |
| Deploy | Vercel (web), Render/Fly (API), managed Postgres | Free/cheap tiers |

**Not in MVP:** LangChain, LangGraph, Celery, Redis, vector DB. Add LangGraph only if the loop needs checkpoints or branching. Add a queue only when FastAPI background tasks stop being reliable.

## 3. Components

1. **API layer** — routes, auth dependency, request/response models.
2. **Dataset service** — upload validation, CSV parsing, profile, storage.
3. **Analysis engine** — pure functions over a DataFrame; no I/O, no LLM. Each is a *tool*.
4. **Tool registry** — maps tool name → (Pydantic args model, function, description). Source of truth for both the LLM schema and the MCP server.
5. **Agent orchestrator** — the investigation loop (see `05-AGENTS.md`).
6. **Result validator** — checks that claims in LLM text match numbers in tool output.
7. **Event bus** — in-process pub/sub that feeds SSE streams.
8. **Report service** — assembles findings, charts, limits into HTML/PDF.

## 4. Data flow

1. `POST /datasets/upload` → validate → save file → compute profile → store metadata.
2. `POST /datasets/{id}/analyze` → create `analyses` row (status `queued`) → background task starts.
3. Orchestrator loads DataFrame (cached per analysis), builds a compact profile for the LLM.
4. Loop: LLM proposes tool call → registry validates → engine executes with timeout → result stored in `tool_executions` → event emitted → result returned to LLM.
5. Agent writes findings (structured output) referencing `tool_execution_ids`.
6. Status → `completed`; frontend fetches findings and charts.
7. Chat questions reuse the same loop with the stored context.

## 5. Tool execution contract

Every tool:
- Takes a Pydantic model (`dataset_id`, plus tool-specific fields).
- Verifies referenced columns exist and have a compatible dtype.
- Returns a `ToolResult`: `{ok, data, warnings, row_count_used, duration_ms}`.
- Never mutates the stored dataset. Row filters (e.g. exclude missing) are passed as validated arguments and recorded.
- Runs with a 30 s timeout and a row limit; numerical output is rounded in presentation but stored at full precision.

## 6. LLM integration

- Provider abstraction: `LLMClient.generate(messages, tools, response_schema) -> LLMResponse`.
- Context sent to the LLM: compact profile (column names, dtypes, null %, top categories, numeric summary), the user question, and prior tool results (truncated summaries, with full results referenced by ID).
- **Never** send the full dataset. Cap sampled rows (e.g. 5) and redact if the user opts in.
- Structured outputs for plans and findings; function calling for tools.
- Max 12 tool calls per investigation, max 3 retries per failed call, per-analysis token budget.

## 7. Performance and limits

| Item | Limit |
|------|-------|
| Upload size | 10 MB |
| Rows analysed | 200k (sample beyond, flagged in the report) |
| Tool timeout | 30 s |
| Investigation wall time | 3 min |
| Concurrent analyses per user | 1 |
| Chart points sent to client | 5,000 (downsampled) |

## 8. Security

- CSV only; check extension, MIME, and sniff content; reject binary.
- Parse with `pandas.read_csv` with explicit limits; no `eval`, no `exec`, no `df.query` from LLM strings.
- Column names from LLM are matched against the real column list, never interpolated.
- Prefix `=`, `+`, `-`, `@` cells with `'` in any exported CSV (formula injection).
- Per-user dataset isolation enforced in every query (`WHERE user_id = :uid`).
- Prompt-injection stance: cell values and column names are *data*. System prompt states this; tool results are wrapped and labelled as untrusted.
- Secrets in env vars only; rate limiting on upload and chat.

## 9. Observability

- Structured JSON logs with `analysis_id`, `tool_name`, `duration_ms`.
- Every LLM request/response stored (redacted) for debugging in `llm_calls` (optional table).
- `/healthz` and `/readyz` endpoints.

## 10. Decisions log

| Decision | Alternatives | Why |
|----------|-------------|-----|
| Native function calling | LangChain/LangGraph | Fewer moving parts; loop is simple |
| FastAPI BackgroundTasks first | Celery | Solo MVP; upgrade later |
| SSE for progress | WebSockets | One-way stream is enough, simpler |
| Plotly JSON from server | Client builds charts | Keeps charts testable against real data |
| Fixed tools | LLM-written pandas code | Safety and repeatability |
