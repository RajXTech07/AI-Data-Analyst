# 03 — Database Design

PostgreSQL 15+, SQLAlchemy 2.0, Alembic migrations. UUID primary keys. JSONB for flexible results.

## 1. Entity relationships

```
users 1──* datasets 1──* analyses 1──* tool_executions
                              │  ──* findings ──* finding_evidence ──> tool_executions
                              │  ──* charts
                              │  ──* messages
                              └─ ──* reports
```

## 2. Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | `gen_random_uuid()` |
| email | citext UNIQUE NOT NULL | |
| password_hash | text NOT NULL | argon2id |
| created_at | timestamptz | default now() |

### refresh_tokens
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| user_id | uuid FK users ON DELETE CASCADE | |
| token_hash | char(64) UNIQUE | SHA-256 of the opaque token |
| family_id | uuid | rotation family, revoked together on reuse |
| expires_at | timestamptz | |
| revoked_at | timestamptz NULL | |

### datasets
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| user_id | uuid FK users ON DELETE CASCADE | |
| filename | text | original name (display only) |
| storage_path | text | server-generated, never user-controlled |
| size_bytes | bigint | |
| sha256 | char(64) | detect duplicate uploads |
| n_rows | int | |
| n_cols | int | |
| profile | jsonb | dtypes, null %, uniques, descriptive stats |
| created_at | timestamptz | |

Index: `(user_id, created_at DESC)`.

### analyses
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| dataset_id | uuid FK datasets ON DELETE CASCADE | |
| user_id | uuid FK users | denormalised for fast auth checks |
| question | text NULL | user's focus, if any |
| status | text | `queued, running, completed, failed, cancelled` |
| plan | jsonb | latest investigation plan |
| model | text | LLM identifier used |
| error | text NULL | |
| started_at / finished_at | timestamptz | |
| created_at | timestamptz | |

Index: `(dataset_id, created_at DESC)`, `(user_id, status)`.

### tool_executions
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| analysis_id | uuid FK ON DELETE CASCADE | |
| seq | int | order within analysis |
| tool_name | text | must exist in registry |
| arguments | jsonb | validated args |
| result | jsonb | full tool output |
| ok | boolean | |
| error | text NULL | |
| duration_ms | int | |
| source | text | `agent` (default), `chat`, `mcp` |
| created_at | timestamptz | |

Unique `(analysis_id, seq)`.

### findings
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| analysis_id | uuid FK ON DELETE CASCADE | |
| title | text | |
| observation | text | what the data shows |
| statistical_evidence | jsonb | test, statistic, p-value, effect size, n |
| interpretation | text | possible explanation, labelled as such |
| limitations | text | |
| hypothesis_status | text | `supported, rejected, inconclusive, descriptive` |
| confidence | text | `low, medium, high` |
| rank | int | importance ordering |
| created_at | timestamptz | |

### finding_evidence
| Column | Type | Notes |
|--------|------|-------|
| finding_id | uuid FK ON DELETE CASCADE | |
| tool_execution_id | uuid FK ON DELETE CASCADE | |
| PK | (finding_id, tool_execution_id) | |

Rule: a finding cannot be saved without at least one evidence row (enforced in service layer).

### charts
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| analysis_id | uuid FK ON DELETE CASCADE | |
| finding_id | uuid FK NULL | |
| tool_execution_id | uuid FK NULL | |
| chart_type | text | `bar, line, scatter, histogram, box, heatmap` |
| spec | jsonb | Plotly figure JSON |
| title | text | |

### messages
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| analysis_id | uuid FK ON DELETE CASCADE | |
| role | text | `user, assistant, system_event` |
| content | text | |
| tool_execution_ids | uuid[] | tools used for this reply |
| created_at | timestamptz | |

### reports
| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| analysis_id | uuid FK ON DELETE CASCADE | |
| format | text | `pdf, html` |
| storage_path | text | |
| created_at | timestamptz | |

## 3. SQL sketch

```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE datasets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename text NOT NULL,
  storage_path text NOT NULL,
  size_bytes bigint NOT NULL,
  sha256 char(64) NOT NULL,
  n_rows int NOT NULL,
  n_cols int NOT NULL,
  profile jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_datasets_user ON datasets(user_id, created_at DESC);

CREATE TABLE analyses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  question text,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','completed','failed','cancelled')),
  plan jsonb,
  model text,
  error text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- tool_executions, findings, finding_evidence, charts, messages, reports follow the tables above
```

## 4. Retention and deletion

- Deleting a dataset cascades to analyses, executions, findings, charts, messages, reports.
- A deletion job also removes the CSV and report files from storage; the DB row is deleted only after files are gone (or queued for retry).
- Optional auto-expiry: datasets older than N days for anonymous/demo users.

## 5. Notes

- Store raw tool output once in `tool_executions.result`; findings reference it. This keeps evidence traceable and avoids copied numbers drifting.
- No vector tables in MVP.
- Add `llm_calls` (analysis_id, request, response, tokens, latency) if debugging needs it.
