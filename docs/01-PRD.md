# 01 — Product Requirements Document (PRD)

**Product:** AI Data Analyst Agent
**Version:** 0.1 (MVP)
**Owner:** Solo developer
**Status:** Draft

---

## 1. Summary

A web app where a user uploads a CSV and an AI agent investigates it on its own: profiles the data, plans an investigation, runs real statistical tests through approved Python tools, draws charts, and produces an evidence-backed report. The user can then ask follow-up questions and redirect the investigation.

**Core principle:** The LLM plans and explains. Python calculates. The backend decides what is allowed to run.

## 2. Problem

- Non-experts (students, small business owners, researchers) have data but not the statistics skills to explore it.
- "Chat with your CSV" tools let the LLM estimate or invent numbers, so results are not repeatable or checkable.
- Notebooks need coding skill; BI dashboards need a person to decide what to look at.

## 3. Goals

| # | Goal | How we know |
|---|------|-------------|
| G1 | Every number shown comes from executed code, never from the LLM | Each finding links to a `tool_executions` row |
| G2 | Useful findings without the user asking | Agent produces 3+ valid findings on a fresh dataset |
| G3 | Traceable and repeatable | Same dataset + same plan = same numbers |
| G4 | Plain-language explanation with stated limits | Each finding has evidence, caveat and confidence |

## 4. Non-goals (MVP)

- No arbitrary Python or SQL execution by the LLM
- No file types other than CSV
- No training or fine-tuning models
- No multi-agent systems, vector DBs, or Kubernetes
- No team collaboration, billing, or real-time multi-user editing

## 5. Target users

1. **Student** — uploads coursework data, needs a report for a professor.
2. **Small business owner** — uploads sales data, wants to know why something changed.
3. **Junior analyst** — wants a fast first pass before deeper work.

## 6. User stories

- As a user, I upload a CSV and immediately see rows, columns, types, missing values and duplicates.
- As a user, I start an investigation and watch the agent's plan and tool calls live.
- As a user, I see each finding with its numbers, chart and a note on limits.
- As a user, I ask "why are marks lower in department B?" and get an answer based on actual calculations.
- As a user, I exclude incomplete records and re-run the analysis.
- As a user, I download a PDF report.
- As a user, I can delete my dataset and all derived results.

## 7. Functional requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Upload CSV (max 10 MB), validate encoding and structure | Must |
| FR-2 | Automatic profile: shape, dtypes, missing, duplicates, descriptive stats | Must |
| FR-3 | Agent produces an investigation plan from profile + optional question | Must |
| FR-4 | Agent calls only whitelisted tools with Pydantic-validated arguments | Must |
| FR-5 | Hypotheses are tested and marked supported / rejected / inconclusive | Must |
| FR-6 | Findings store evidence, confidence and caveats | Must |
| FR-7 | Live progress via Server-Sent Events | Must |
| FR-8 | Interactive charts (Plotly) | Must |
| FR-9 | Conversational follow-up questions | Must |
| FR-10 | PDF/HTML report export | Must |
| FR-11 | User can interrupt or redirect a running investigation | Should |
| FR-12 | Email/password auth and per-user dataset isolation | Should |
| FR-13 | MCP server exposing the analysis tools | Could |

## 8. Non-functional requirements

- **Correctness:** statistics validated against SciPy reference results in tests.
- **Safety:** no code execution from LLM output; strict argument validation.
- **Performance:** profile of a 10 MB CSV in under 5 s; each tool call under 10 s; hard timeout 30 s.
- **Reliability:** failed tool call returns a structured error the agent can react to.
- **Privacy:** user data is never used for training; deletion removes files and rows.
- **Honesty:** the UI separates *observed pattern*, *statistical evidence*, and *possible explanation*. Correlation is never presented as causation.

## 9. Success metrics

- Planted-issue detection rate on the synthetic test dataset ≥ 90%
- Tool-call validity rate (arguments pass validation first try) ≥ 85%
- Investigation completes without error ≥ 95% of runs on 3 reference datasets
- Findings whose numbers match recomputation = 100%

## 10. Risks

| Risk | Mitigation |
|------|-----------|
| LLM picks a wrong statistical test | Tool-level guards (check normality/sample size), test selection rules in prompt, caveats in output |
| LLM states a number not in tool output | Interpreter prompt forbids new numbers; validator rejects numbers absent from results |
| Scope creep | Build order in `07-PLAN.md`; auth and deployment last |
| Large files exhaust memory | 10 MB limit, dtype downcasting, sampling for charts |

## 11. Open questions

- Gemini or OpenAI as default provider?
- Is login required for the demo, or is a session-only mode enough?
