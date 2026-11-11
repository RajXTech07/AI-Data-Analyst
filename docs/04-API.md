# 04 — API Specification

Base URL: `/api/v1` · JSON unless noted · Auth: `Authorization: Bearer <access_token>` (see `10-AUTH.md`).

## 1. Conventions

**Error shape**
```json
{ "error": { "code": "validation_error", "message": "Column 'regoin' not found", "details": {} } }
```

| HTTP | code | When |
|------|------|------|
| 400 | `bad_request` | malformed input |
| 401 | `unauthorized` | missing/invalid token |
| 403 | `forbidden` | not your resource |
| 404 | `not_found` | |
| 409 | `conflict` | analysis already running |
| 413 | `file_too_large` | > 10 MB |
| 415 | `unsupported_media_type` | not CSV |
| 422 | `validation_error` | Pydantic failure |
| 429 | `rate_limited` | |
| 500 | `internal_error` | |

Resources owned by another user return **404**, not 403, to avoid leaking existence.

## 2. Auth

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/auth/register` | `{email, password}` | `201 {user}` |
| POST | `/auth/login` | `{email, password}` | `{access_token, token_type, expires_in}` + refresh cookie |
| POST | `/auth/refresh` | cookie | `{access_token}` |
| POST | `/auth/logout` | | `204` |
| GET | `/auth/me` | | `{id, email}` |

## 3. Datasets

| Method | Path | Description |
|--------|------|-------------|
| POST | `/datasets/upload` | multipart `file` → `201 Dataset` |
| GET | `/datasets` | list mine (`?limit&cursor`) |
| GET | `/datasets/{id}` | metadata |
| GET | `/datasets/{id}/profile` | full profile |
| GET | `/datasets/{id}/preview?rows=20` | first N rows |
| DELETE | `/datasets/{id}` | delete dataset and all derived data → `204` |

**Dataset**
```json
{
  "id": "uuid", "filename": "student_performance.csv",
  "n_rows": 1200, "n_cols": 12, "size_bytes": 184320,
  "created_at": "2026-11-02T07:30:00Z"
}
```

**Profile (excerpt)**
```json
{
  "columns": [
    {"name": "attendance", "dtype": "numeric", "null_pct": 0.0, "unique": 87,
     "stats": {"mean": 78.4, "std": 12.1, "min": 31, "max": 100}},
    {"name": "department", "dtype": "categorical", "null_pct": 0.0, "unique": 5,
     "top_values": [{"value": "CSE", "count": 310}]}
  ],
  "duplicates": 4,
  "missing_total_pct": 2.3
}
```

## 4. Analyses

| Method | Path | Description |
|--------|------|-------------|
| POST | `/datasets/{id}/analyze` | start investigation → `202 Analysis` |
| GET | `/analyses/{id}` | status, plan, timings |
| GET | `/analyses/{id}/events` | **SSE** progress stream |
| POST | `/analyses/{id}/cancel` | request cancellation → `202` |
| GET | `/analyses/{id}/findings` | list findings |
| GET | `/analyses/{id}/findings/{fid}` | one finding with evidence |
| GET | `/analyses/{id}/tool-executions` | audit trail |
| GET | `/analyses/{id}/charts` | list chart specs |
| POST | `/analyses/{id}/chat` | ask follow-up → `202 {message_id}` (answer streamed on events) |
| GET | `/analyses/{id}/messages` | chat history |
| POST | `/analyses/{id}/steer` | redirect a running investigation |
| POST | `/analyses/{id}/report` | generate report → `202 Report` |

**POST `/datasets/{id}/analyze`**
```json
{ "question": "Why are marks lower in one department?", "options": { "exclude_incomplete_rows": false } }
```
`question` is optional; without it the agent runs an open exploration.

**Finding**
```json
{
  "id": "uuid", "title": "Attendance is positively associated with marks",
  "observation": "Higher attendance goes with higher marks in this dataset.",
  "statistical_evidence": {"test": "spearman", "rho": 0.61, "p_value": 1.2e-120, "n": 1196},
  "interpretation": "Possible explanation: engaged students attend more. This analysis cannot show causation.",
  "limitations": "4 rows excluded for missing values. Self-reported attendance.",
  "hypothesis_status": "supported", "confidence": "high",
  "evidence": ["tool_execution_uuid"], "chart_ids": ["uuid"]
}
```

**POST `/analyses/{id}/steer`**
```json
{ "instruction": "Ignore the 2019 rows and focus on department B" }
```

## 5. SSE event stream

`GET /analyses/{id}/events` → `text/event-stream`. Each event has `id`, `event`, JSON `data`. Supports `Last-Event-ID` to resume.

| event | data |
|-------|------|
| `status` | `{status}` |
| `plan` | `{steps:[...]}` |
| `tool_started` | `{seq, tool_name, arguments}` |
| `tool_finished` | `{seq, ok, duration_ms, summary}` |
| `hypothesis` | `{statement, status}` |
| `finding` | `{id, title}` |
| `chart` | `{id}` |
| `message_delta` | `{message_id, text}` |
| `error` | `{code, message}` |
| `done` | `{status}` |

## 6. Reports

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports/{id}` | status |
| GET | `/reports/{id}/download?format=pdf\|html` | file |

## 7. Health

`GET /healthz` → `200 {"status":"ok"}` · `GET /readyz` → checks DB and storage.

## 8. Rate limits (MVP)

- Upload: 10 / hour / user
- Analyze: 5 / hour / user, 1 concurrent
- Chat: 30 / hour / analysis

## 9. Idempotency and versioning

- `POST /analyze` accepts an `Idempotency-Key` header to avoid duplicate runs on retry.
- Breaking changes go to `/api/v2`.
