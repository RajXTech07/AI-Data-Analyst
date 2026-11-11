# 09 — Features

Each feature lists behaviour, acceptance criteria, and the part of the system it touches.

## F1. Dataset Manager
- Upload CSV (drag/drop), list, delete.
- Validation: extension, MIME sniff, size ≤ 10 MB, parseable, ≥ 1 row, ≥ 2 columns, header present.
- Encoding detection (UTF-8, fallback latin-1) and delimiter sniffing (`,` `;` `\t`).
- **Accept when:** a malformed or oversized file gives a clear error and nothing is stored.

## F2. Data Profiler
- Rows, columns, inferred types (numeric, categorical, datetime, boolean, text/id).
- Missing values per column, duplicate rows, unique counts, top categories.
- Descriptive stats for numeric columns; date range for datetime columns.
- Quality flags: constant column, high-cardinality text, mixed types, suspected ID column, inconsistent categories (e.g. `Male`, `male`, `M`).
- **Accept when:** profile matches pandas reference on all test datasets.

## F3. EDA Engine
- Univariate: distributions, skew, outliers (IQR and z-score).
- Bivariate: correlation (Pearson/Spearman), group comparisons, cross-tabs.
- Time: trend, period-over-period change, seasonality hint.
- All through registry tools, so the agent and the UI use identical code.

## F4. AI Investigation Agent
- Open exploration (no question) or focused (with question).
- Shows a plan, then runs steps, tests hypotheses, revises plan on weak or rejected results.
- Produces ranked findings.
- **Accept when:** on the planted dataset it reports each planted issue and does not report false relationships above a stated threshold.

### Finding structure
```json
{
  "title": "string",
  "observation": "what the data shows",
  "statistical_evidence": {"test": "...", "statistic": 0.0, "p_value": 0.0, "effect_size": 0.0, "n": 0},
  "interpretation": "possible explanation, clearly labelled as hypothesis",
  "limitations": "string",
  "hypothesis_status": "supported | rejected | inconclusive | descriptive",
  "confidence": "low | medium | high",
  "evidence_execution_ids": ["uuid"]
}
```

Confidence rule (code, not LLM): `high` = p < 0.01, n ≥ 100, meaningful effect size, assumptions met. `medium` = p < 0.05 or smaller sample. `low` = otherwise or assumptions violated.

## F5. Visualization Engine
- Chart types: bar, line, scatter, histogram, box, heatmap.
- Built server-side from real data, returned as Plotly JSON.
- Large data downsampled (flagged on chart).
- **Accept when:** a chart's plotted values equal the source tool output.

## F6. Conversational Analyst
- Natural-language questions answered through tools; answer links to executions.
- Context-aware ("exclude those rows", "now by gender").
- If the question can't be answered from the data, it says so.
- Refuses non-data tasks politely.

## F7. Investigation Room (UI)
- Live timeline: plan, tool started/finished, hypothesis result, finding created.
- Click a tool step → see arguments and raw result.
- Controls: cancel, steer, re-run with options.

## F8. Chart Explorer (UI)
- Pick columns, chart type, filters; re-draws via `generate_chart`.
- Save a chart into the report.

## F9. Report Generator
- Sections: dataset summary, data quality, key findings, charts, statistical evidence, limitations, recommended next investigations.
- Formats: HTML, PDF.
- Includes an appendix listing every tool run (name, args, time).
- **Accept when:** every number in the report appears in the appendix data.

## F10. What-if re-analysis
- Options such as "exclude rows with missing values", "filter category = X".
- Creates a new analysis linked to the original, so results are compared, not overwritten.

## F11. Data deletion
- One click deletes dataset, analyses, charts, reports, and files.

## F12. Optional / later
- Regression and feature importance
- K-Means clustering
- Anomaly detection with Isolation Forest
- Excel/JSON input
- Shareable read-only report link
- MCP tool server (see `11-MCP.md`)

## Feature priority

| Priority | Features |
|----------|----------|
| Must | F1, F2, F3 (core tools), F4, F5, F6, F9 |
| Should | F7, F10, F11 |
| Could | F8, F12 |
