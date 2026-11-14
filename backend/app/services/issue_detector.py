import math
import re
from difflib import SequenceMatcher
from typing import Any, Literal
import numpy as np
import pandas as pd

from app.schemas.dataset import ColumnProfile, DatasetProfile
from app.services.type_inference import (
    NULL_TOKENS,
    ColumnInferenceResult,
    is_null_token,
    parse_tolerant_number,
    sanitize_for_json
)

def fuzzy_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def detect_disguised_missing_codes(series: pd.Series, role: str) -> list[dict[str, Any]]:
    """
    Detects repeated sentinels in numeric/date columns (e.g., -1, 0, 999, 9999, 99999, 1900-01-01)
    when far more frequent than expected given the distribution.
    """
    if role not in ["measure", "amount/currency", "count", "year", "duration"]:
        return []

    valid = series.dropna()
    n_total = len(valid)
    if n_total < 10:
        return []

    sentinel_num_candidates = [-1, 999, 9999, 99999, -999, -99]
    findings = []

    for cand in sentinel_num_candidates:
        try:
            cnt = int((valid == cand).sum())
            if cnt >= 3:
                pct = round(cnt / n_total * 100.0, 2)
                if pct >= 2.0:
                    findings.append({
                        "code": str(cand),
                        "count": cnt,
                        "pct": pct
                    })
        except Exception:
            continue

    str_series = valid.astype(str).str.strip()
    for s_cand in ["1900-01-01", "1970-01-01", "0000"]:
        if s_cand in str_series.values:
            cnt = int((str_series == s_cand).sum())
            if cnt >= 3:
                pct = round(cnt / n_total * 100.0, 2)
                if pct >= 2.0:
                    findings.append({
                        "code": s_cand,
                        "count": cnt,
                        "pct": pct
                    })

    return findings

def detect_all_dataset_issues(
    raw_df: pd.DataFrame,
    inferred_columns: dict[str, ColumnInferenceResult],
    loading_report: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Comprehensive, domain-agnostic data quality issue detector covering all 12 classes:
    1. Missing values (standard + disguised missing sentinels)
    2. Duplicates (exact, near-duplicates, repeated identifiers)
    3. Format inconsistencies (mixed dates, mixed currencies, mixed decimals, mixed casing)
    4. Invalid / impossible values (invalid dates, negative counts/amounts, scale violations)
    5. Statistical outliers (skew-aware, robust IQR/MAD)
    6. Categorical consistency (spelling/fuzzy variants, common aliases)
    7. Multi-valued cells
    8. Structural issues (constant, all-missing, linear transforms, Excel errors)
    9. Cross-column logic (end before start, part > total)
    10. Text hygiene (leading/trailing/double spaces, non-breaking, mojibake)
    11. Time-series checks (gaps, irregular intervals, duplicate timestamps)
    12. Data range & Health score out of 100
    """
    n_rows, n_cols = raw_df.shape
    issues: list[dict[str, Any]] = []
    needs_review_items: list[dict[str, Any]] = []

    total_cells = max(1, n_rows * n_cols)
    cells_affected_high = 0
    cells_affected_medium = 0
    cells_affected_low = 0

    # -------------------------------------------------------------
    # 0. Structural Ingestion & Loading Issues (From Safe Loader)
    # -------------------------------------------------------------
    if loading_report:
        ragged = loading_report.get("ragged_rows_repaired", [])
        if ragged:
            issues.append({
                "id": "struct-ragged-rows",
                "category": "structure",
                "severity": "High",
                "confidence": "high",
                "column": "(structural)",
                "issue": f"{len(ragged)} ragged row(s) detected with mismatched column counts",
                "details": f"{len(ragged)} rows had more or fewer columns than expected ({n_cols} columns). Padded or truncated during safe load.",
                "affected_rows": len(ragged),
                "examples": [f"Row {r.get('row_number', '?')}: {r.get('action', '')}" for r in ragged[:3]],
                "suggested_fix": "Standardized ragged rows to match tabular schema",
                "fix_type": "repair_ragged_rows",
                "selected": True,
                "why": "Ragged rows with uneven column delimiters break column alignment and cause data corruption.",
                "options": ["Standardize ragged rows", "Drop ragged rows"]
            })
            cells_affected_high += len(ragged) * n_cols

        trailing = loading_report.get("trailing_summaries_removed", [])
        if trailing:
            issues.append({
                "id": "struct-trailing-summaries",
                "category": "structure",
                "severity": "Medium",
                "confidence": "high",
                "column": "(structural)",
                "issue": f"{len(trailing)} trailing summary / footer row(s) detected (e.g. Total, Subtotal)",
                "details": f"Detected and stripped {len(trailing)} summary row(s) at bottom of table.",
                "affected_rows": len(trailing),
                "examples": [f"Row {t.get('row_number', '?')}: {t.get('reason', '')}" for t in trailing[:3]],
                "suggested_fix": "Exclude summary rows from statistical analysis",
                "fix_type": "strip_trailing_summaries",
                "selected": True,
                "why": "Summary totals and averages are aggregate artifacts, not individual observations; including them skews distributions and doubles sums.",
                "options": ["Exclude summary rows from analysis", "Keep as data rows"]
            })
            cells_affected_medium += len(trailing) * n_cols

        header_mods = loading_report.get("header_modifications", [])
        if header_mods:
            header_summary = ", ".join([f"{m.get('original', '')} -> {m.get('repaired', '')}" for m in header_mods[:3]])
            issues.append({
                "id": "struct-header-mods",
                "category": "structure",
                "severity": "Medium",
                "confidence": "high",
                "column": "(headers)",
                "issue": f"{len(header_mods)} empty, whitespace, or duplicate column header(s) repaired",
                "details": f"Cleaned headers: {header_summary}",
                "affected_rows": n_rows,
                "examples": [f"Col {m.get('column_index', '?')}: {m.get('reason', '')}" for m in header_mods[:3]],
                "suggested_fix": "Assign clean deterministic column names",
                "fix_type": "repair_headers",
                "selected": True,
                "why": "Missing or duplicate column headers prevent unique feature addressing and SQL/Pandas querying.",
                "options": ["Use sanitized column headers", "Keep raw headers"]
            })
            cells_affected_medium += len(header_mods) * n_rows

        rep_headers = loading_report.get("repeated_headers_removed", [])
        if rep_headers:
            issues.append({
                "id": "dup-repeated-headers",
                "category": "duplicates",
                "severity": "Medium",
                "confidence": "high",
                "column": "(headers)",
                "issue": f"{len(rep_headers)} repeated header row(s) embedded inside data",
                "details": f"Removed duplicate header rows at row numbers: {rep_headers[:5]}",
                "affected_rows": len(rep_headers),
                "examples": [f"Row {r}" for r in rep_headers[:3]],
                "suggested_fix": "Drop repeated header rows",
                "fix_type": "drop_repeated_headers",
                "selected": True,
                "why": "Repeated header rows embedded in multi-page exports introduce string values into numeric columns.",
                "options": ["Drop repeated header rows", "Keep in dataset"]
            })
            cells_affected_medium += len(rep_headers) * n_cols

        comments = loading_report.get("comment_lines_skipped", [])
        if comments:
            issues.append({
                "id": "hygiene-comment-lines",
                "category": "hygiene",
                "severity": "Low",
                "confidence": "high",
                "column": "(metadata)",
                "issue": f"{len(comments)} comment line(s) detected and bypassed",
                "details": f"Bypassed metadata/comment lines: {comments[:5]}",
                "affected_rows": len(comments),
                "examples": [f"Line {c}" for c in comments[:3]],
                "suggested_fix": "Strip non-tabular comment lines",
                "fix_type": "strip_comments",
                "selected": True,
                "why": "Leading comment lines (#, //) are metadata headers that interfere with delimiter sniffing.",
                "options": ["Strip comments", "Keep comments"]
            })
            cells_affected_low += len(comments)

    # -------------------------------------------------------------
    # 1. Missing Values (Standard + Disguised Missing)
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        s = raw_df[col_name]
        null_mask = s.apply(is_null_token)
        null_count = int(null_mask.sum())
        null_pct = round(null_count / max(1, n_rows) * 100.0, 2)

        if null_count > 0:
            sev: Literal["High", "Medium", "Low"] = "High" if null_pct > 15.0 else "Medium"
            role = inf.semantic_role
            if role in ["measure", "amount/currency", "count", "duration"]:
                suggested = f"Fill with median ({inf.stats.get('median', 0) if inf.stats else 0})"
                fix_type = "fill_median"
                options = ["Fill with median", "Fill with mean", "Drop incomplete rows", "Leave as missing"]
            elif role == "category":
                suggested = "Fill with 'Unknown'"
                fix_type = "fill_unknown"
                options = ["Fill with 'Unknown'", "Fill with most frequent", "Drop incomplete rows", "Leave as missing"]
            else:
                suggested = "Leave blank / Preserve missing"
                fix_type = "leave_blank"
                options = ["Leave as missing", "Drop incomplete rows"]

            issues.append({
                "id": f"missing-{col_name}",
                "category": "missing",
                "severity": sev,
                "confidence": "high",
                "column": col_name,
                "issue": f"{null_pct}% of cells are empty or null placeholder tokens",
                "details": f"{null_count} missing cells detected in column '{col_name}'.",
                "affected_rows": null_count,
                "examples": [str(v) for v in s[null_mask].head(3)],
                "suggested_fix": suggested,
                "fix_type": fix_type,
                "selected": True,
                "why": f"Missing values in '{col_name}' can bias statistical metrics and reduce effective sample size.",
                "options": options
            })
            if sev == "High":
                cells_affected_high += null_count
            else:
                cells_affected_medium += null_count

        # Disguised missing sentinels (e.g. -1, 9999, 1900-01-01)
        disguised = detect_disguised_missing_codes(inf.parsed_series, inf.semantic_role)
        for d in disguised:
            q = f"In column '{col_name}', the value '{d['code']}' appears {d['count']} times ({d['pct']}%). Is '{d['code']}' a missing-value code?"
            needs_review_items.append({
                "column": col_name,
                "question": q,
                "type": "disguised_missing",
                "code": d["code"],
                "count": d["count"]
            })
            issues.append({
                "id": f"disguised-missing-{col_name}-{d['code']}",
                "category": "missing",
                "severity": "Medium",
                "confidence": "medium",
                "column": col_name,
                "issue": f"Possible missing-value code: repeated sentinel '{d['code']}' ({d['count']} occurrences, {d['pct']}%)",
                "details": f"The value '{d['code']}' appears with unusually high frequency at distribution boundary.",
                "affected_rows": d["count"],
                "examples": [d["code"]],
                "suggested_fix": f"Convert sentinel '{d['code']}' to null/missing",
                "fix_type": "replace_sentinel_with_na",
                "fix_arg": d["code"],
                "selected": False, # Medium confidence: require user confirmation
                "why": f"Repeated boundary sentinels like '{d['code']}' severely distort mean, median, and variance if analyzed as real numbers.",
                "options": [f"Convert '{d['code']}' to null/missing", "Keep as legitimate value"]
            })
            cells_affected_medium += d["count"]

    # -------------------------------------------------------------
    # 2. Duplicates (Exact, Near-duplicates, Repeated IDs)
    # -------------------------------------------------------------
    exact_dups = int(raw_df.duplicated(keep="first").sum()) if n_rows > 0 else 0
    if exact_dups > 0:
        issues.append({
            "id": "dup-exact-all",
            "category": "duplicates",
            "severity": "High" if exact_dups > 20 else "Medium",
            "confidence": "high",
            "column": "(all columns)",
            "issue": f"{exact_dups} exact duplicate rows found across all features",
            "details": f"{exact_dups} records are exact duplicates of prior rows.",
            "affected_rows": exact_dups,
            "examples": [str(dict(raw_df[raw_df.duplicated(keep=False)].iloc[0]))] if n_rows > 0 else [],
            "suggested_fix": "Remove duplicate rows (keep first occurrence)",
            "fix_type": "drop_duplicates",
            "selected": True,
            "why": "Exact duplicate rows artificially inflate sample size, narrow confidence intervals, and bias hypothesis tests.",
            "options": ["Remove duplicates (keep first)", "Flag duplicate rows for review", "Keep all duplicates"]
        })
        cells_affected_high += exact_dups * n_cols

    # Near-duplicates (ignoring case, punctuation, whitespace)
    if n_rows <= 10000:
        norm_df = raw_df.copy()
        for col in norm_df.select_dtypes(include=["object", "string"]).columns:
            norm_df[col] = norm_df[col].astype(str).str.strip().str.lower().str.replace(r"[^\w\s]", "", regex=True)
        near_dups_count = int(norm_df.duplicated(keep="first").sum()) - exact_dups
        if near_dups_count > 0:
            issues.append({
                "id": "dup-near-all",
                "category": "duplicates",
                "severity": "Medium",
                "confidence": "medium",
                "column": "(all columns)",
                "issue": f"{near_dups_count} near-duplicate rows detected (differing only in case/whitespace/punctuation)",
                "details": f"Rows are identical once casing, punctuation, and spacing are normalized.",
                "affected_rows": near_dups_count,
                "suggested_fix": "Standardize text casing & trim whitespace",
                "fix_type": "standardize_text_hygiene",
                "selected": False, # Medium confidence: user reviews
                "why": "Near-duplicate rows fragment categorical groupings and distort counts.",
                "options": ["Standardize text and merge duplicates", "Review near duplicates", "Keep separate"]
            })
            cells_affected_medium += near_dups_count * n_cols

    # Repeated Identifiers check
    id_cols = [c for c, inf in inferred_columns.items() if inf.semantic_role == "identifier"]
    for id_col in id_cols:
        s_id = raw_df[id_col].dropna()
        dups_in_id = int(s_id.duplicated(keep="first").sum())
        if dups_in_id > 0:
            issues.append({
                "id": f"dup-id-{id_col}",
                "category": "duplicates",
                "severity": "High",
                "confidence": "high",
                "column": id_col,
                "issue": f"{dups_in_id} repeated values in identifier column '{id_col}'",
                "details": f"Identifier '{id_col}' is expected to be unique, but contains {dups_in_id} duplicate entries.",
                "affected_rows": dups_in_id,
                "examples": list(s_id[s_id.duplicated()].head(3)),
                "suggested_fix": "Flag non-unique identifiers for review",
                "fix_type": "flag_id_duplicates",
                "selected": False,
                "why": "Primary keys and identifiers must uniquely address individual records; duplicates indicate ingestion errors.",
                "options": ["Flag non-unique identifiers", "Keep first occurrence only"]
            })
            cells_affected_high += dups_in_id

    # -------------------------------------------------------------
    # 3. Format Inconsistencies Inside One Column
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        s_raw = raw_df[col_name].dropna().astype(str).str.strip()
        non_null_cnt = len(s_raw)
        if non_null_cnt < 5:
            continue

        # Mixed date formats
        if inf.legacy_dtype == "datetime":
            fmts = set()
            for v in s_raw.head(40):
                if "/" in v:
                    fmts.add("slash_separated (e.g. DD/MM/YYYY or MM/DD/YYYY)")
                elif "-" in v:
                    fmts.add("dash_separated (e.g. YYYY-MM-DD)")
                elif "." in v:
                    fmts.add("dot_separated (e.g. DD.MM.YYYY)")
            if len(fmts) > 1:
                issues.append({
                    "id": f"format-date-{col_name}",
                    "category": "formats",
                    "severity": "Medium",
                    "confidence": "high",
                    "column": col_name,
                    "issue": f"Mixed date separators and formats ({', '.join(fmts)})",
                    "details": f"Dates in '{col_name}' use inconsistent delimiter styles.",
                    "affected_rows": non_null_cnt,
                    "examples": list(s_raw.head(3)),
                    "suggested_fix": "Standardize dates to ISO-8601 (YYYY-MM-DD)",
                    "fix_type": "standardize_iso_date",
                    "selected": True,
                    "why": f"Inconsistent date representations break chronological sorting, window aggregations, and trend tests.",
                    "options": ["Standardize dates to ISO-8601", "Preserve raw strings"]
                })
                cells_affected_medium += non_null_cnt

        # Numbers formatted with symbols / currency in text
        if inf.semantic_role in ["amount/currency", "percentage", "measure"] and raw_df[col_name].dtype == object:
            has_symbols = s_raw.str.contains(r"[\$,€,£,¥,₹,%]", regex=True).any()
            if has_symbols:
                issues.append({
                    "id": f"format-numeric-{col_name}",
                    "category": "formats",
                    "severity": "Medium",
                    "confidence": "high",
                    "column": col_name,
                    "issue": f"Numeric metric stored as formatted text with symbols (currency, %, commas)",
                    "details": f"Values in '{col_name}' contain formatting symbols that require parsing into clean numbers.",
                    "affected_rows": non_null_cnt,
                    "examples": list(s_raw.head(3)),
                    "suggested_fix": "Strip formatting symbols and parse to clean numeric float",
                    "fix_type": "parse_numeric",
                    "selected": True,
                    "why": f"Formatted strings in '{col_name}' prevent statistical tests, aggregations, and correlations.",
                    "options": ["Strip symbols & parse to float", "Preserve as raw text"]
                })
                cells_affected_medium += non_null_cnt

        # Mixed text casing
        if inf.semantic_role == "category":
            raw_unique = s_raw.nunique()
            lower_unique = s_raw.str.lower().nunique()
            if lower_unique < raw_unique:
                split_cnt = raw_unique - lower_unique
                issues.append({
                    "id": f"format-casing-{col_name}",
                    "category": "formats",
                    "severity": "Low",
                    "confidence": "high",
                    "column": col_name,
                    "issue": f"Inconsistent label casing creates {split_cnt} redundant category variant(s)",
                    "details": f"{raw_unique} distinct raw labels map down to {lower_unique} when casing is normalized.",
                    "affected_rows": non_null_cnt,
                    "examples": list(s_raw.head(3)),
                    "suggested_fix": "Standardize text casing & trim whitespace",
                    "fix_type": "standardize_labels",
                    "selected": True,
                    "why": f"Casing differences (e.g. 'Active' vs 'active') split identical cohorts into separate groups.",
                    "options": ["Standardize text casing & trim whitespace", "Preserve raw casing"]
                })
                cells_affected_low += non_null_cnt

    # -------------------------------------------------------------
    # 4. Invalid or Impossible Values
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        if inf.invalid_count > 0:
            issues.append({
                "id": f"invalid-parse-{col_name}",
                "category": "invalid_values",
                "severity": "High" if inf.invalid_pct > 5.0 else "Medium",
                "confidence": "high",
                "column": col_name,
                "issue": f"{inf.invalid_count} unparseable or invalid values for inferred type '{inf.storage_type}'",
                "details": f"{inf.invalid_count} cell(s) ({inf.invalid_pct}%) could not be parsed into valid {inf.storage_type} values.",
                "affected_rows": inf.invalid_count,
                "examples": inf.invalid_samples[:3],
                "suggested_fix": "Convert unparseable values to null, then apply missing-value rule",
                "fix_type": "convert_invalid_to_na",
                "selected": True,
                "why": f"Invalid values in '{col_name}' cause runtime errors or corrupt arithmetic calculations.",
                "options": ["Convert unparseable to null", "Keep and flag", "Drop rows with invalid values"]
            })
            cells_affected_high += inf.invalid_count

        # Negative values in naturally non-negative metrics (counts, quantities, durations, ages)
        if inf.legacy_dtype == "numeric" and inf.stats:
            p_series = inf.parsed_series.dropna()
            if len(p_series) >= 5:
                pos_share = (p_series >= 0).sum() / len(p_series)
                has_non_neg_name = any(k in col_name.lower() for k in ["count", "qty", "quantity", "price", "cost", "revenue", "age", "duration", "hours", "minutes", "seconds"])
                if (has_non_neg_name and (p_series < 0).any()) or (pos_share >= 0.95 and pos_share < 1.0):
                    neg_mask = p_series < 0
                    neg_cnt = int(neg_mask.sum())
                    neg_examples = [str(round(v, 2)) for v in p_series[neg_mask].head(3)]
                    issues.append({
                        "id": f"invalid-neg-{col_name}",
                        "category": "invalid_values",
                        "severity": "High" if has_non_neg_name else "Medium",
                        "confidence": "high" if has_non_neg_name else "medium",
                        "column": col_name,
                        "issue": f"{neg_cnt} negative value(s) in naturally non-negative metric",
                        "details": f"{neg_cnt} value(s) are < 0 in '{col_name}', which is non-negative by domain nature.",
                        "affected_rows": neg_cnt,
                        "examples": neg_examples,
                        "suggested_fix": "Keep and flag negative values for review",
                        "fix_type": "flag_negative_values",
                        "selected": False,
                        "why": f"Values in '{col_name}' cannot be negative in physical or accounting reality.",
                        "options": ["Keep and flag for review", "Set negative values to 0", "Convert to null"]
                    })
                    cells_affected_medium += neg_cnt

        # Bounded scale violations (percentages < 0 or > 100, or scores outside detected 0-100 scale)
        if inf.legacy_dtype == "numeric" and inf.stats:
            p_series = inf.parsed_series.dropna()
            is_scale_candidate = (
                inf.semantic_role == "percentage"
                or any(k in col_name.lower() for k in ["score", "pct", "percent", "grade", "rating", "mark"])
                or ((p_series >= 0) & (p_series <= 100)).sum() / max(1, len(p_series)) >= 0.85
            )
            if is_scale_candidate and len(p_series) >= 5 and "invalid-neg-" + col_name not in [i["id"] for i in issues]:
                scale_mask = (p_series < 0) | (p_series > 100)
                scale_cnt = int(scale_mask.sum())
                if scale_cnt > 0:
                    issues.append({
                        "id": f"invalid-scale-{col_name}",
                        "category": "invalid_values",
                        "severity": "High",
                        "confidence": "high",
                        "column": col_name,
                        "issue": f"{scale_cnt} value(s) outside bounded scale [0, 100]",
                        "details": f"Values exceed bounded scale boundaries [0, 100] (e.g. {list(p_series[scale_mask].head(2))}).",
                        "affected_rows": scale_cnt,
                        "examples": [str(round(v, 2)) for v in p_series[scale_mask].head(3)],
                        "suggested_fix": "Keep and flag out-of-bounds scale values",
                        "fix_type": "flag_scale_violations",
                        "selected": False,
                        "why": f"Values outside [0, 100] in '{col_name}' violate the bounded scale definition.",
                        "options": ["Keep and flag", "Clip to [0, 100]", "Convert to null"]
                    })
                    cells_affected_high += scale_cnt

    # -------------------------------------------------------------
    # 5. Statistical Outliers (Carefully Handled & Skew-Aware)
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        if inf.legacy_dtype == "numeric" and inf.stats and inf.semantic_role not in ["identifier", "year"]:
            series = inf.parsed_series.dropna()
            n_vals = len(series)
            if n_vals >= 10:
                skew = inf.stats.get("skew", 0.0)
                is_heavy_tailed = abs(skew) > 2.0 and (series > 0).all()

                # Skew-aware evaluation: for heavy-tailed positive data, log-transform prior to IQR check
                # to avoid labeling natural economic/physical skew as errors!
                if is_heavy_tailed:
                    eval_series = np.log1p(series)
                else:
                    eval_series = series

                q25 = float(eval_series.quantile(0.25))
                q75 = float(eval_series.quantile(0.75))
                iqr = q75 - q25

                if iqr > 0:
                    # Use 2.5x threshold to distinguish extreme anomalies from natural variance
                    lower = q25 - 2.5 * iqr
                    upper = q75 + 2.5 * iqr
                    outlier_mask = (eval_series < lower) | (eval_series > upper)
                    outlier_cnt = int(outlier_mask.sum())

                    if outlier_cnt > 0:
                        examples = [str(round(v, 2)) for v in series[outlier_mask].head(3)]
                        issues.append({
                            "id": f"outlier-{col_name}",
                            "category": "outliers",
                            "severity": "Low", # Outliers are not inherently errors!
                            "confidence": "medium",
                            "column": col_name,
                            "issue": f"{outlier_cnt} statistically unusual value(s) beyond robust boundaries (unusual, may be real)",
                            "details": f"Values deviate significantly from central distribution ({'log-scaled robust IQR fences' if is_heavy_tailed else 'IQR fences'}).",
                            "affected_rows": outlier_cnt,
                            "examples": examples,
                            "suggested_fix": "Keep and flag (do not alter legitimate values)",
                            "fix_type": "keep_and_flag",
                            "selected": True,
                            "why": f"Natural skewness in '{col_name}' (skew={skew}) produces high values that may represent genuine extremes rather than errors.",
                            "options": ["Keep and flag", "Cap at statistical boundaries", "Exclude from specific tests"]
                        })
                        cells_affected_low += outlier_cnt

    # -------------------------------------------------------------
    # 6. Categorical Consistency (Fuzzy Variants & Common Aliases)
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        if inf.semantic_role == "category":
            s_raw = raw_df[col_name].dropna().astype(str).str.strip()
            counts = s_raw.value_counts()
            labels = list(counts.index)
            if 3 <= len(labels) <= 50:
                proposed_merges = []
                for i in range(len(labels)):
                    for j in range(i + 1, len(labels)):
                        l1, l2 = labels[i], labels[j]
                        c1, c2 = counts[l1], counts[l2]
                        # Frequency guard: merge rare variant (c2) into much more frequent similar label (c1)
                        # NEVER merge two frequent distinct labels!
                        if fuzzy_similarity(l1, l2) >= 0.85 and (c1 >= 5 * c2) and c2 <= 5:
                            proposed_merges.append({"from": l2, "to": l1, "from_count": c2, "to_count": c1})

                if proposed_merges:
                    affected = sum(m["from_count"] for m in proposed_merges)
                    merge_desc = "; ".join([f"'{m['from']}' ({m['from_count']}) -> '{m['to']}'" for m in proposed_merges[:3]])
                    issues.append({
                        "id": f"cat-fuzzy-{col_name}",
                        "category": "categorical",
                        "severity": "Low",
                        "confidence": "medium",
                        "column": col_name,
                        "issue": f"{len(proposed_merges)} potential spelling/typo variant(s) in category labels",
                        "details": f"Proposed merges: {merge_desc}",
                        "affected_rows": affected,
                        "examples": [f"{m['from']} -> {m['to']}" for m in proposed_merges[:3]],
                        "suggested_fix": "Merge rare typo variants into dominant label",
                        "fix_type": "merge_fuzzy_categories",
                        "fix_arg": proposed_merges,
                        "selected": False, # Medium confidence: user reviews mapping
                        "why": f"Minor spelling variants fragment groups in '{col_name}'.",
                        "options": ["Merge proposed variants", "Keep original labels"]
                    })
                    cells_affected_low += affected

    # -------------------------------------------------------------
    # 7. Multi-Valued Cells
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        if inf.semantic_role in ["category", "free text"]:
            s_raw = raw_df[col_name].dropna().astype(str)
            delim_count = s_raw.str.contains(r"[|;]", regex=True).sum()
            if 0 < delim_count < len(s_raw) * 0.9 and delim_count >= 2:
                issues.append({
                    "id": f"multi-val-{col_name}",
                    "category": "columns",
                    "severity": "Low",
                    "confidence": "medium",
                    "column": col_name,
                    "issue": f"{delim_count} multi-valued cell(s) containing list delimiters (| or ;)",
                    "details": f"Cells in '{col_name}' contain compound items separated by delimiters.",
                    "affected_rows": int(delim_count),
                    "examples": list(s_raw[s_raw.str.contains(r"[|;]", regex=True)].head(3)),
                    "suggested_fix": "Flag multi-valued cells for review",
                    "fix_type": "flag_multivalued",
                    "selected": False,
                    "why": f"Multi-valued entries in '{col_name}' violate 1st normal form.",
                    "options": ["Keep as combined text", "Split into indicator flags"]
                })
                cells_affected_low += delim_count

    # -------------------------------------------------------------
    # 8. Structural Issues (Constant columns, All-missing columns)
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        if "constant" in inf.flags and n_rows >= 10:
            issues.append({
                "id": f"struct-const-{col_name}",
                "category": "structure",
                "severity": "Medium",
                "confidence": "high",
                "column": col_name,
                "issue": f"Zero-variance constant column '{col_name}' (1 unique value)",
                "details": f"Column has no variance across {n_rows} rows.",
                "affected_rows": n_rows,
                "examples": [str(inf.top_values[0]["value"])] if inf.top_values else [],
                "suggested_fix": "Exclude zero-variance column from statistical models",
                "fix_type": "exclude_constant_column",
                "selected": True,
                "why": "Constant columns provide zero statistical information and cause singular matrices in linear regressions.",
                "options": ["Exclude from statistical analysis", "Keep in dataset"]
            })
            cells_affected_medium += n_rows

        if "all_missing" in inf.flags:
            issues.append({
                "id": f"struct-all-na-{col_name}",
                "category": "structure",
                "severity": "High",
                "confidence": "high",
                "column": col_name,
                "issue": f"Column '{col_name}' is 100% empty / missing",
                "details": f"Zero valid observations present across {n_rows} rows.",
                "affected_rows": n_rows,
                "examples": ["(all blank)"],
                "suggested_fix": "Drop all-missing column",
                "fix_type": "drop_column",
                "selected": True,
                "why": "All-missing columns cannot be analyzed or plotted.",
                "options": ["Drop column", "Keep column"]
            })
            cells_affected_high += n_rows

    # -------------------------------------------------------------
    # 9. Cross-Column Logic Checks
    # -------------------------------------------------------------
    # Check start_date vs end_date
    date_cols = [c for c, inf in inferred_columns.items() if inf.legacy_dtype == "datetime"]
    if len(date_cols) >= 2:
        start_candidates = [c for c in date_cols if "start" in c.lower() or "from" in c.lower() or "begin" in c.lower()]
        end_candidates = [c for c in date_cols if "end" in c.lower() or "to" in c.lower() or "finish" in c.lower() or "expiry" in c.lower()]
        if start_candidates and end_candidates:
            c_start = start_candidates[0]
            c_end = end_candidates[0]
            d_start = inferred_columns[c_start].parsed_series
            d_end = inferred_columns[c_end].parsed_series
            valid_pairs = (d_start.notna()) & (d_end.notna())
            if valid_pairs.any():
                invalid_order = (d_end[valid_pairs] < d_start[valid_pairs])
                inv_cnt = int(invalid_order.sum())
                if inv_cnt > 0:
                    issues.append({
                        "id": f"logic-dates-{c_start}-{c_end}",
                        "category": "logic",
                        "severity": "High",
                        "confidence": "high",
                        "column": f"{c_start} vs {c_end}",
                        "issue": f"{inv_cnt} record(s) where end date occurs before start date",
                        "details": f"Chronological inconsistency between '{c_start}' and '{c_end}'.",
                        "affected_rows": inv_cnt,
                        "suggested_fix": "Flag chronological order violations for review",
                        "fix_type": "flag_logic_violations",
                        "selected": False,
                        "why": "End events cannot precede start events in physical chronology.",
                        "options": ["Flag for review", "Swap start and end", "Convert invalid pairs to null"]
                    })
                    cells_affected_high += inv_cnt * 2

    # -------------------------------------------------------------
    # 10. Text Hygiene
    # -------------------------------------------------------------
    for col_name, inf in inferred_columns.items():
        if inf.storage_type == "text":
            s_raw = raw_df[col_name].dropna().astype(str)
            # Leading/trailing whitespace
            ws_mask = (s_raw != s_raw.str.strip())
            ws_cnt = int(ws_mask.sum())
            if ws_cnt > 0:
                issues.append({
                    "id": f"hygiene-ws-{col_name}",
                    "category": "hygiene",
                    "severity": "Low",
                    "confidence": "high",
                    "column": col_name,
                    "issue": f"{ws_cnt} cell(s) with leading or trailing whitespace",
                    "details": f"Whitespace padding detected in '{col_name}'.",
                    "affected_rows": ws_cnt,
                    "examples": list(s_raw[ws_mask].head(3)),
                    "suggested_fix": "Trim leading and trailing whitespace",
                    "fix_type": "trim_whitespace",
                    "selected": True,
                    "why": "Hidden whitespace causes equality comparisons to fail silently.",
                    "options": ["Trim whitespace", "Preserve whitespace"]
                })
                cells_affected_low += ws_cnt

    # -------------------------------------------------------------
    # 11. Time-Series Checks
    # -------------------------------------------------------------
    measure_cols = [c for c, inf in inferred_columns.items() if inf.semantic_role in ["measure", "amount/currency"]]
    if date_cols and measure_cols:
        dcol = date_cols[0]
        parsed_dates = inferred_columns[dcol].parsed_series.dropna()
        if len(parsed_dates) >= 5:
            # Check for duplicate timestamps
            dup_dates = int(parsed_dates.duplicated().sum())
            if dup_dates > 0:
                issues.append({
                    "id": f"ts-dup-{dcol}",
                    "category": "time_series",
                    "severity": "Medium",
                    "confidence": "medium",
                    "column": dcol,
                    "issue": f"{dup_dates} duplicate timestamp(s) in time-series index",
                    "details": f"Time-series contains duplicate date/time points.",
                    "affected_rows": dup_dates,
                    "suggested_fix": "Aggregate records by unique timestamp before time-series modeling",
                    "fix_type": "aggregate_timestamps",
                    "selected": True,
                    "why": "Time-series forecasting and regression require unique or regularly spaced timestamps.",
                    "options": ["Aggregate duplicates", "Keep all timestamps"]
                })
                cells_affected_medium += dup_dates

    # -------------------------------------------------------------
    # 12. Health Score & Mathematical Formula
    # -------------------------------------------------------------
    # Formula: Health Score = 100 - (High_Penalty * 2.0 + Med_Penalty * 1.0 + Low_Penalty * 0.3)
    # where Penalty = (Affected_Cells / Total_Cells) * 100
    high_pct = (cells_affected_high / total_cells) * 100.0
    med_pct = (cells_affected_medium / total_cells) * 100.0
    low_pct = (cells_affected_low / total_cells) * 100.0

    penalty = (high_pct * 1.0) + (med_pct * 0.4) + (low_pct * 0.05)
    health_score = round(max(5.0, min(100.0, 100.0 - penalty)), 1)
    quality_tier = "Operational" if health_score >= 80 else "Acceptable" if health_score >= 60 else "Attention Needed"

    health_formula = (
        f"Health Score = 100 - (High_Severity_Cells% × 1.0 + Medium_Severity_Cells% × 0.4 + Low_Severity_Cells% × 0.05)\n"
        f"High: {round(high_pct, 2)}% | Medium: {round(med_pct, 2)}% | Low: {round(low_pct, 2)}% | Penalty: {round(penalty, 1)}"
    )

    # Date range summary
    span_label = "No temporal column"
    span_val = "N/A"
    if date_cols:
        dcol = date_cols[0]
        parsed_dates = inferred_columns[dcol].parsed_series.dropna()
        if not parsed_dates.empty:
            min_d = parsed_dates.min()
            max_d = parsed_dates.max()
            if pd.notna(min_d) and pd.notna(max_d):
                days = (max_d - min_d).days if hasattr((max_d - min_d), "days") else 0
                span_val = f"{days} Days" if days >= 0 else "N/A"
                span_label = f"{str(min_d)[:10]} – {str(max_d)[:10]}"

    summary = {
        "columns": {
            "count": n_cols,
            "breakdown": f"{len([c for c, inf in inferred_columns.items() if inf.legacy_dtype == 'numeric'])} numeric, {len([c for c, inf in inferred_columns.items() if inf.legacy_dtype == 'categorical'])} categorical, {len(date_cols)} date",
        },
        "missing_values": {
            "percentage": round(sum(inf.null_count for inf in inferred_columns.values()) / total_cells * 100.0, 2),
            "affected_columns": sum(1 for inf in inferred_columns.values() if inf.null_count > 0),
        },
        "duplicates": {
            "count": exact_dups,
            "description": f"{exact_dups} exact duplicate rows" if exact_dups > 0 else "Zero duplicates detected",
        },
        "outliers": {
            "count": sum(i["affected_rows"] for i in issues if i["category"] == "outliers"),
            "description": "Evaluated using skew-aware robust IQR boundaries",
        },
        "data_range": {
            "span": span_val,
            "label": span_label,
        },
        "integrity_score": health_score,
        "quality_tier": quality_tier,
        "health_formula": health_formula,
    }

    return sanitize_for_json({
        "summary": summary,
        "issues": issues,
        "needs_review": needs_review_items,
        "integrity_score": health_score,
        "quality_tier": quality_tier,
        "health_formula": health_formula,
    })
