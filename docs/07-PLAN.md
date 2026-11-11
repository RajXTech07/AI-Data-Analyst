# 07 — Development Plan

Solo, ~4–6 weeks after ~2 weeks of preparation. **Rule: make the analysis engine reliable before adding the LLM.**

## 0. Preparation (≈2 weeks, 2–3 h/day)

| Days | Topic | Deliverable |
|------|-------|-------------|
| 1–3 | Pandas, cleaning, groupby, NumPy | Notebook analysing one real dataset |
| 4–5 | Descriptive stats, correlation, outliers, hypothesis tests | EDA notebook, ≥5 calculated findings |
| 6–7 | FastAPI, Pydantic, file upload, Postgres basics | Upload API returning a profile |
| 8–10 | LLM function calling, structured outputs | LLM selects and runs 3 tools |
| 11–14 | Next.js, Plotly, SSE | Upload → profile → chart in browser |

## 1. Six-week build

### Week 1 — Backend foundation
- Repo, Docker, FastAPI skeleton, config, logging
- Postgres + Alembic; `users` (stub), `datasets`
- CSV upload, validation, storage, profile
- **Exit:** upload a CSV via API and get a correct profile

### Week 2 — Analysis engine
- Tool functions: `calculate_statistics`, `group_by_analysis`, `correlation_analysis`, `detect_outliers`, `detect_missing_values`, `detect_duplicates`
- `statistical_test` with assumption checks
- Registry + Pydantic arg models
- Unit tests vs SciPy references; synthetic dataset with planted issues
- **Exit:** every tool passes tests, no LLM involved

### Week 3 — LLM + tool calling
- `LLMClient` abstraction, one provider
- Function-calling loop with validation and retries
- `tool_executions` persistence
- Chat endpoint answering from tools
- **Exit:** "Show average marks by department" runs the right tool and explains it correctly

### Week 4 — Autonomous investigation
- Profile → plan → execute → validate → revise → interpret
- Findings with evidence links
- Number validator
- SSE events; cancel and steer
- **Exit:** open exploration on 3 datasets yields valid, evidence-linked findings

### Week 5 — Frontend + charts + report
- Dataset workspace, dashboard, investigation room, chart explorer, report view
- `generate_chart` → Plotly JSON → client
- HTML → PDF report
- **Exit:** full upload-to-report flow in the browser

### Week 6 — Quality and delivery
- Auth (email/password, JWT), per-user isolation
- Evaluation run, bug fixing, error and empty states
- Deploy (Vercel + Render + managed Postgres)
- README, demo script, screenshots
- **Exit:** public demo + recorded walkthrough

## 2. Definition of done (per feature)

- Works on ≥2 different datasets (not only student data)
- Unit/integration tests pass
- Errors are handled and shown to the user
- Documented in the relevant file

## 3. MVP checklist

- [ ] CSV upload and preview
- [ ] Automatic profiling
- [ ] Missing value and duplicate detection
- [ ] Statistics and correlation
- [ ] Five core tools
- [ ] LLM function calling
- [ ] Investigation plan
- [ ] Hypothesis testing with evidence
- [ ] Interactive charts and dashboard
- [ ] Chat follow-ups
- [ ] PDF report

## 4. Cut list (if behind schedule)

Drop in this order: MCP server → steering → chart explorer → trend analysis → auth (use demo mode) → HTML/PDF polish.

## 5. Weekly rhythm

- Mon: pick the week's exit criterion
- Daily: one vertical slice working end to end
- Fri: run the evaluation set, log regressions
- Keep a `DECISIONS.md` for changes in direction

## 6. Demo script (5 min)

1. Upload student data → profile appears
2. Start investigation → plan and tools stream live
3. Open a finding → show evidence, test, caveats
4. Ask "What if I exclude incomplete records?" → re-run
5. Export report
6. Show the audit trail proving numbers came from code
