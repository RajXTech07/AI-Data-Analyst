# AI Data Analyst — Backend API

FastAPI backend with structured statistical validation, deterministic profiling, and LLM-powered autonomous investigations.

## Quick Start

### 1. Environment & Setup
Ensure dependencies are installed:
```bash
cd backend
pip install -r requirements.txt
```

### 2. Run the Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 3. Run Tests
```bash
pytest tests/ -v
```

## Directory Structure
- `app/api/`: Versioned API endpoints (auth, datasets, analyses, chat, SSE events, reports).
- `app/core/`: Configuration (`pydantic-settings`), logging, error handling, security.
- `app/db/`: SQLAlchemy 2.0 models, declarative base, database session management.
- `app/schemas/`: Pydantic v2 schemas for all inputs, outputs, and validation.
- `app/services/`: Pure business logic for dataset ingestion, profiling, storage, analyses, and event pub/sub.
- `app/tools/`: Pure statistical tools (statistics, groupby, correlation, outliers, tests, charts).
- `app/agent/`: Autonomous orchestrator, LLM provider (`google-genai` / fallback mock), planner, validator, and interpreter.

## Autonomous Investigation Flow
1. **Planning**: LLM receives compact dataset profile and produces an `InvestigationPlan` (up to 12 steps).
2. **Tool Execution**: Tools execute deterministically through safe registry with execution audit rows in `tool_executions`.
3. **Number Grounding**: `validator.py` checks all numeric claims against executed tool results within tolerance.
4. **Findings & Visuals**: Evidence-backed findings linked to tool execution records and Plotly interactive charts.
5. **Conversational Follow-ups**: `POST /analyses/{id}/chat` triggers targeted tool execution to answer specific questions.
