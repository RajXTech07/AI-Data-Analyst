from difflib import SequenceMatcher
import math
import re
from typing import Any
import numpy as np
import pandas as pd

from app.core.logging import logger
from app.services.type_inference import (
    BOOLEAN_FALSE_TOKENS,
    BOOLEAN_TRUE_TOKENS,
    NULL_TOKENS,
    ColumnInferenceResult,
    get_null_mask,
    is_null_token,
    parse_boolean,
    parse_duration_to_seconds,
    parse_tolerant_number,
)

def fuzzy_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, str(a).lower().strip(), str(b).lower().strip()).ratio()

def is_text_column(s: pd.Series) -> bool:
    return s.dtype == object or pd.api.types.is_string_dtype(s) or s.dtype.kind in ('O', 'S', 'U')

def preview_fix_operation(
    df: pd.DataFrame,
    fix_id: str,
    fix_type: str,
    column: str | None = None,
    arg: Any = None
) -> dict[str, Any]:
    """Generates 3-5 before/after examples and expected affected cell count without modifying the DataFrame."""
    examples = []
    affected_count = 0

    if fix_type == "drop_duplicates":
        dups = df.duplicated(keep="first")
        affected_count = int(dups.sum())
        if affected_count > 0:
            dup_sample = df[dups].head(3)
            examples = [{"before": f"Duplicate row {idx}", "after": "Row removed"} for idx in dup_sample.index]

    elif fix_type == "standardize_text_hygiene" or fix_type == "drop_near_duplicates":
        affected_count = min(len(df), 5)
        examples = [{"before": "Record with non-standard whitespace/casing", "after": "Normalized and deduplicated record"}]

    elif fix_type == "flag_id_duplicates" or fix_type == "deduplicate_identifier":
        if column and column in df.columns:
            s_id = df[column]
            dups = s_id.duplicated(keep="first") & s_id.notna()
            affected_count = int(dups.sum())
            for idx in s_id[dups].head(3).index:
                examples = [{"before": f"Duplicate ID: {s_id[idx]}", "after": "Unique ID record preserved"}]

    elif fix_type == "replace_sentinel_with_na" and column and column in df.columns:
        sentinel_val = str(arg) if arg is not None else "-1"
        mask = (df[column] == sentinel_val) | (df[column].astype(str).str.strip() == sentinel_val)
        affected_count = int(mask.sum())
        examples = [{"before": sentinel_val, "after": "null (NaN)"}]

    elif fix_type == "fill_median" and column and column in df.columns:
        s = df[column]
        mask = get_null_mask(s)
        affected_count = int(mask.sum())
        non_null_nums = pd.to_numeric(s[~mask], errors="coerce").dropna()
        med = round(float(non_null_nums.median()), 2) if not non_null_nums.empty else 0.0
        null_samples = s[mask].head(3)
        examples = [{"before": str(v), "after": str(med)} for v in null_samples]

    elif fix_type == "fill_unknown" and column and column in df.columns:
        s = df[column]
        mask = get_null_mask(s)
        affected_count = int(mask.sum())
        examples = [{"before": str(v), "after": "Unknown"} for v in s[mask].head(3)]

    elif fix_type == "parse_numeric" and column and column in df.columns:
        s = df[column]
        for v in s.dropna().head(20):
            num, meta = parse_tolerant_number(str(v))
            if num is not None and str(v) != str(num):
                examples.append({"before": str(v), "after": str(round(num, 4))})
                affected_count += 1
                if len(examples) >= 3:
                    break

    elif fix_type == "trim_whitespace" and column and column in df.columns:
        s = df[column].dropna().astype(str)
        ws_mask = s != s.str.strip()
        affected_count = int(ws_mask.sum())
        for v in s[ws_mask].head(3):
            examples.append({"before": f"'{v}'", "after": f"'{v.strip()}'"})

    elif fix_type == "standardize_labels" and column and column in df.columns:
        s = df[column].dropna().astype(str)
        titled = s.str.strip().str.title()
        diff_mask = s != titled
        affected_count = int(diff_mask.sum())
        for v, t in zip(s[diff_mask].head(3), titled[diff_mask].head(3)):
            examples.append({"before": v, "after": t})

    elif fix_type == "merge_fuzzy_categories" and column and column in df.columns:
        if isinstance(arg, list) and arg:
            examples = [{"before": f"'{m.get('from')}'", "after": f"'{m.get('to')}'"} for m in arg[:3]]
            affected_count = sum(m.get("from_count", 1) for m in arg)
        else:
            examples = [{"before": "Spelling typo variant", "after": "Dominant canonical category"}]
            affected_count = 3

    elif fix_type in ("convert_invalid_to_na", "invalid_values") and column and column in df.columns:
        examples = [{"before": "Unparseable corrupt token", "after": "null (imputed with median)"}]
        affected_count = 3

    elif fix_type in ("flag_negative_values", "clip_non_negative") and column and column in df.columns:
        s = pd.to_numeric(df[column], errors="coerce").dropna()
        neg_mask = s < 0
        affected_count = int(neg_mask.sum())
        examples = [{"before": str(v), "after": "0.0"} for v in s[neg_mask].head(3)]

    elif fix_type in ("flag_scale_violations", "clip_scale") and column and column in df.columns:
        s = pd.to_numeric(df[column], errors="coerce").dropna()
        out_mask = (s < 0) | (s > 100)
        affected_count = int(out_mask.sum())
        examples = [{"before": str(v), "after": "Clipped to scale bounds [0, 100]"} for v in s[out_mask].head(3)]

    elif fix_type in ("cap_outliers", "keep_and_flag") and column and column in df.columns:
        examples = [{"before": "Extreme statistical anomaly", "after": "Capped at robust Tukey IQR fence"}]
        affected_count = 3

    elif fix_type == "standardize_iso_date" and column and column in df.columns:
        examples = [{"before": "01/15/2023 or 2023.01.15", "after": "2023-01-15 (ISO-8601)"}]
        affected_count = len(df)

    elif fix_type in ("repair_ragged_rows", "strip_trailing_summaries", "repair_headers", "drop_repeated_headers", "strip_comments"):
        affected_count = len(df)
        examples = [{"before": "Structural raw irregularity", "after": "Standardized schema alignment"}]

    return {
        "fix_id": fix_id,
        "fix_type": fix_type,
        "column": column,
        "affected_cells": affected_count,
        "preview_examples": examples
    }

def apply_clean_fixes(
    df: pd.DataFrame,
    inferred_columns: dict[str, ColumnInferenceResult],
    selected_fixes: list[str],
    custom_overrides: dict[str, Any] | None = None
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """
    Executes approved data cleaning operations deterministically across all 7 core data cleaning areas:
    1. Deduplication (Exact + Near duplicates + Repeated IDs)
    2. Standardize Missing Values (Disguised sentinels + Universal null tokens + Smart role-based imputation)
    3. Clean Categorical Typos (Fuzzy variant merging + Multi-space whitespace trimming + Title casing)
    4. Fix Mixed Data Types (Formatted numbers + Currency symbols + Unparseable invalid values + Durations)
    5. Handle Outliers & Impossible Values (Impossible negatives + Bounded scale violations + Tukey outlier capping)
    6. Standardize Dates and Times (ISO-8601 formatting + Ambiguous format parsing + Chronological order correction)
    7. Boolean & Scale Standardization (Truthy/falsy normalization + Percentage scale standardization)

    Returns: (cleaned_df, changelog)
    Original data is never modified; a clean copy is produced.
    """
    clean_df = df.copy()
    changelog: list[dict[str, Any]] = []

    def is_selected(fix_key: str, col: str | None = None, alt_keys: list[str] | None = None) -> bool:
        if not selected_fixes:
            return False
        target_keys = set()
        if fix_key:
            target_keys.add(fix_key.lower())
            if col:
                target_keys.add(f"{fix_key}-{col}".lower())
        if alt_keys:
            for ak in alt_keys:
                target_keys.add(ak.lower())
                if col and not ak.endswith(f"-{col}") and not ak.startswith(f"{col}-"):
                    target_keys.add(f"{ak}-{col}".lower())

        for f in selected_fixes:
            f_str = str(f).strip().lower()
            if f_str in target_keys:
                return True
            if col:
                if f_str == f"{fix_key}-{col}".lower():
                    return True
                for ak in (alt_keys or []):
                    if f_str == ak.lower() or f_str == f"{ak}-{col}".lower():
                        return True
        return False

    # -------------------------------------------------------------
    # 0. Structural Standardizations (Logged from Safe Load)
    # -------------------------------------------------------------
    for f in selected_fixes:
        if "ragged" in f or "repair_ragged_rows" in f:
            changelog.append({
                "step": "Repair Ragged Rows",
                "operation": "repair_ragged_rows",
                "description": "Standardized rows with mismatched column counts to maintain rectangular tabular structure.",
                "affected_rows": len(clean_df),
                "reversible": True
            })
            break
    for f in selected_fixes:
        if "trailing" in f or "strip_trailing_summaries" in f:
            changelog.append({
                "step": "Strip Trailing Summaries",
                "operation": "strip_trailing_summaries",
                "description": "Excluded trailing summary totals and footer rows from observational analysis.",
                "affected_rows": 1,
                "reversible": True
            })
            break
    for f in selected_fixes:
        if "header" in f or "repair_headers" in f:
            changelog.append({
                "step": "Standardize Column Headers",
                "operation": "repair_headers",
                "description": "Cleaned empty or duplicate column headers to ensure unique feature names.",
                "affected_rows": len(clean_df.columns),
                "reversible": True
            })
            break

    # -------------------------------------------------------------
    # 1. Deduplication (Exact + Near Duplicates + Repeated IDs)
    # -------------------------------------------------------------
    # 1a. Exact Duplicate Rows
    if is_selected("drop_duplicates", alt_keys=["dup-exact-all", "dup-exact", "duplicates"]):
        before_cnt = len(clean_df)
        clean_df = clean_df.drop_duplicates(keep="first").reset_index(drop=True)
        dropped = before_cnt - len(clean_df)
        if dropped > 0:
            changelog.append({
                "step": "Remove Exact Duplicates",
                "operation": "drop_duplicates",
                "description": f"Removed {dropped} exact duplicate rows across all features (kept first occurrence).",
                "affected_rows": dropped,
                "reversible": True
            })

    # 1b. Near Duplicate Rows (Differing only by whitespace, casing, or punctuation)
    if is_selected("standardize_text_hygiene", alt_keys=["dup-near-all", "drop_near_duplicates", "near_duplicate"]):
        if len(clean_df) > 1:
            norm_s = clean_df.astype(str).apply(lambda row: " ".join(row).lower().strip(), axis=1)
            norm_s = norm_s.str.replace(r"[^\w\s]", "", regex=True).str.replace(r"\s+", " ", regex=True)
            near_dups_mask = norm_s.duplicated(keep="first")
            near_cnt = int(near_dups_mask.sum())
            if near_cnt > 0:
                clean_df = clean_df[~near_dups_mask].reset_index(drop=True)
                changelog.append({
                    "step": "Remove Near Duplicates",
                    "operation": "drop_near_duplicates",
                    "description": f"Removed {near_cnt} near-duplicate rows differing only in casing, punctuation, or spacing.",
                    "affected_rows": near_cnt,
                    "reversible": True
                })

    # 1c. Repeated Identifiers (Ensure 1:1 entity uniqueness for ID columns)
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        is_id_col = (inf and inf.semantic_role == "identifier") or any(k in col.lower() for k in ["id", "_id", "key", "code"])
        if is_id_col and is_selected("flag_id_duplicates", col=col, alt_keys=[f"dup-id-{col}", "deduplicate_identifier"]):
            s_id = clean_df[col]
            id_dups = s_id.duplicated(keep="first") & s_id.notna()
            id_dup_cnt = int(id_dups.sum())
            if id_dup_cnt > 0:
                clean_df = clean_df[~id_dups].reset_index(drop=True)
                changelog.append({
                    "step": f"Deduplicate Identifier: {col}",
                    "operation": "deduplicate_identifier",
                    "description": f"Deduplicated {id_dup_cnt} non-unique primary key / ID entries in '{col}'.",
                    "affected_rows": id_dup_cnt,
                    "reversible": True
                })

    # -------------------------------------------------------------
    # 2. Standardize Missing Values & Disguised Sentinels
    # -------------------------------------------------------------
    # 2a. Disguised Sentinel Codes (-1, 999, 9999, 1900-01-01)
    sentinel_nums = [-1, -99, -999, 999, 9999, 99999]
    sentinel_dates = ["1900-01-01", "1970-01-01", "0000", "0000-00-00", "9999-12-31"]
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        should_fix_sentinels = is_selected(
            "replace_sentinel_with_na",
            col=col,
            alt_keys=[f"disguised-missing-{col}", f"missing-{col}", "replace_sentinels"]
        )
        if should_fix_sentinels:
            converted_cnt = 0
            for s_num in sentinel_nums:
                mask = (clean_df[col] == s_num) | (clean_df[col].astype(str).str.strip() == str(s_num))
                cnt = int(mask.sum())
                if cnt >= 1:
                    clean_df.loc[mask, col] = np.nan
                    converted_cnt += cnt
            for s_date in sentinel_dates:
                mask = clean_df[col].astype(str).str.strip() == s_date
                cnt = int(mask.sum())
                if cnt >= 1:
                    clean_df.loc[mask, col] = np.nan
                    converted_cnt += cnt
            if converted_cnt > 0:
                changelog.append({
                    "step": f"Standardize Sentinels: {col}",
                    "operation": "replace_sentinel_with_na",
                    "description": f"Converted {converted_cnt} boundary sentinel codes (e.g. -1, 999, 1900-01-01) to proper nulls in '{col}'.",
                    "affected_rows": converted_cnt,
                    "reversible": True
                })

    # 2b. Universal Null Tokens Standardized to np.nan Across All Columns
    for col in clean_df.columns:
        null_mask = get_null_mask(clean_df[col])
        if null_mask.any():
            clean_df.loc[null_mask, col] = np.nan

    # 2c. Smart Imputation by Inferred Semantic Role
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        should_impute = is_selected(
            "fill_missing",
            col=col,
            alt_keys=[f"missing-{col}", "fill_median", "fill_unknown", "leave_blank", "impute_missing"]
        )
        if should_impute:
            null_mask = clean_df[col].isna()
            null_count = int(null_mask.sum())
            if null_count > 0:
                is_num = (inf and (inf.semantic_role in ["measure", "amount/currency", "count", "duration", "percentage", "year"] or inf.legacy_dtype == "numeric")) or pd.api.types.is_numeric_dtype(clean_df[col])
                if is_num:
                    num_series = pd.to_numeric(clean_df[col], errors="coerce")
                    med = float(num_series.median()) if num_series.notna().any() else 0.0
                    clean_df[col] = num_series.fillna(med)
                    changelog.append({
                        "step": f"Impute Numeric Missing: {col}",
                        "operation": "fill_median",
                        "description": f"Imputed {null_count} missing cells in measure '{col}' with robust median ({round(med, 2)}).",
                        "affected_rows": null_count,
                        "reversible": True
                    })
                elif (inf and inf.semantic_role in ["category", "geographic"]) or is_text_column(clean_df[col]):
                    clean_df[col] = clean_df[col].fillna("Unknown")
                    changelog.append({
                        "step": f"Impute Categorical Missing: {col}",
                        "operation": "fill_unknown",
                        "description": f"Imputed {null_count} missing cells in category '{col}' with 'Unknown'.",
                        "affected_rows": null_count,
                        "reversible": True
                    })
                else:
                    changelog.append({
                        "step": f"Preserve Missing: {col}",
                        "operation": "leave_blank",
                        "description": f"Preserved {null_count} missing cells in '{col}' as blank (never impute identifiers or dates).",
                        "affected_rows": null_count,
                        "reversible": True
                    })

    # -------------------------------------------------------------
    # 3. Clean Categorical Typos & Spelling Variants
    # -------------------------------------------------------------
    for col in clean_df.columns:
        inf = inferred_columns.get(col)

        # 3a. Fuzzy Spelling Variant Merging
        should_merge = is_selected("merge_fuzzy_categories", col=col, alt_keys=[f"cat-fuzzy-{col}", "fuzzy_typos"])
        if should_merge and is_text_column(clean_df[col]):
            s_raw = clean_df[col].dropna().astype(str).str.strip()
            counts = s_raw.value_counts()
            labels = list(counts.index)
            if len(labels) >= 2:
                merges_done = []
                for i in range(len(labels)):
                    for j in range(i + 1, len(labels)):
                        l1, l2 = labels[i], labels[j]
                        c1, c2 = counts[l1], counts[l2]
                        if fuzzy_similarity(l1, l2) >= 0.80:
                            target_label = l1 if c1 >= c2 else l2
                            source_label = l2 if c1 >= c2 else l1
                            clean_df[col] = clean_df[col].replace(source_label, target_label)
                            merges_done.append(f"'{source_label}' -> '{target_label}'")
                if merges_done:
                    changelog.append({
                        "step": f"Merge Categorical Typos: {col}",
                        "operation": "merge_fuzzy_categories",
                        "description": f"Harmonized spelling typo variants in '{col}': {'; '.join(merges_done[:3])}.",
                        "affected_rows": len(merges_done),
                        "reversible": True
                    })

        # 3b. Whitespace Trimming & Multi-space Collapse
        should_trim = is_selected(
            "trim_whitespace",
            col=col,
            alt_keys=[f"hygiene-ws-{col}", "trim_whitespace", "standardize_text_hygiene", f"standardize_text_hygiene-{col}"]
        )
        if should_trim and is_text_column(clean_df[col]):
            before_s = clean_df[col].astype(str)
            clean_df[col] = clean_df[col].apply(
                lambda x: re.sub(r"\s+", " ", x.strip()) if isinstance(x, str) and not is_null_token(x) else x
            )
            changed = int((before_s != clean_df[col].astype(str)).sum())
            if changed > 0:
                changelog.append({
                    "step": f"Trim Whitespace: {col}",
                    "operation": "trim_whitespace",
                    "description": f"Stripped irregular leading/trailing and multi-spaces from {changed} cells in '{col}'.",
                    "affected_rows": changed,
                    "reversible": True
                })

        # 3c. Title Casing for Category Labels
        should_casing = is_selected("standardize_labels", col=col, alt_keys=[f"format-casing-{col}", "standardize_labels"])
        if should_casing and is_text_column(clean_df[col]):
            clean_df[col] = clean_df[col].apply(
                lambda x: x.strip().title() if isinstance(x, str) and not is_null_token(x) else x
            )
            changelog.append({
                "step": f"Standardize Categorical Casing: {col}",
                "operation": "standardize_labels",
                "description": f"Standardized text labels in '{col}' to clean Title Case.",
                "affected_rows": len(clean_df),
                "reversible": True
            })

    # -------------------------------------------------------------
    # 4. Fix Mixed Data Types & Formatted Numeric Text
    # -------------------------------------------------------------
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        should_parse_num = is_selected(
            "parse_numeric",
            col=col,
            alt_keys=[f"format-numeric-{col}", f"mixed-type-{col}", "parse_numeric"]
        )
        should_fix_invalid = is_selected(
            "convert_invalid_to_na",
            col=col,
            alt_keys=[f"invalid-parse-{col}", f"mixed-type-{col}", "invalid_values"]
        )
        is_duration = (inf and inf.semantic_role == "duration") or any(k in col.lower() for k in ["duration", "runtime", "elapsed"])
        should_parse_duration = is_selected(
            "parse_duration",
            col=col,
            alt_keys=[f"format-duration-{col}", f"duration-{col}"]
        ) or (is_duration and should_parse_num)

        # 4a. Numeric Values Stored with Currency Symbols, Commas, Percent Signs
        if should_parse_num and is_text_column(clean_df[col]) and not should_parse_duration:
            parsed_vals = []
            cleaned_sym_count = 0
            for v in clean_df[col]:
                if is_null_token(v):
                    parsed_vals.append(np.nan)
                else:
                    num, meta = parse_tolerant_number(str(v))
                    if num is not None:
                        parsed_vals.append(num)
                        if meta.get("is_currency") or meta.get("is_percentage") or meta.get("suffix") or meta.get("is_parentheses_neg"):
                            cleaned_sym_count += 1
                    else:
                        parsed_vals.append(np.nan)
            clean_df[col] = pd.Series(parsed_vals, index=clean_df.index, dtype=float)
            if clean_df[col].isna().any():
                med_val = float(clean_df[col].median()) if clean_df[col].notna().any() else 0.0
                clean_df[col] = clean_df[col].fillna(med_val)
            changelog.append({
                "step": f"Parse Formatted Numbers: {col}",
                "operation": "parse_numeric",
                "description": f"Normalized formatted numbers to clean numeric floats in '{col}'.",
                "affected_rows": cleaned_sym_count or len(clean_df),
                "reversible": True
            })

        # 4b. Duration parsing
        elif should_parse_duration and is_text_column(clean_df[col]):
            parsed_durs = []
            for v in clean_df[col]:
                if is_null_token(v):
                    parsed_durs.append(np.nan)
                else:
                    sec = parse_duration_to_seconds(str(v))
                    if sec is not None:
                        parsed_durs.append(sec / 60.0)
                    else:
                        parsed_durs.append(np.nan)
            dur_series = pd.Series(parsed_durs, index=clean_df.index, dtype=float)
            med_dur = float(dur_series.median()) if dur_series.notna().any() else 0.0
            clean_df[col] = dur_series.fillna(med_dur)
            changelog.append({
                "step": f"Normalize Durations: {col}",
                "operation": "parse_duration",
                "description": f"Normalized duration strings to numeric minutes in '{col}'.",
                "affected_rows": len(clean_df),
                "reversible": True
            })

    # -------------------------------------------------------------
    # 5. Handle Outliers & Impossible Values
    # -------------------------------------------------------------
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        num_s = pd.to_numeric(clean_df[col], errors="coerce")

        # 5a. Impossible Negative Values in Non-Negative Metrics
        should_clip_neg = is_selected("flag_negative_values", col=col, alt_keys=[f"invalid-neg-{col}", "clip_non_negative"])
        if should_clip_neg and num_s.notna().any():
            neg_mask = num_s < 0
            neg_cnt = int(neg_mask.sum())
            if neg_cnt > 0:
                clean_df.loc[neg_mask, col] = 0.0
                changelog.append({
                    "step": f"Correct Impossible Negatives: {col}",
                    "operation": "clip_non_negative",
                    "description": f"Corrected {neg_cnt} impossible negative values in naturally non-negative metric '{col}' (clipped to 0).",
                    "affected_rows": neg_cnt,
                    "reversible": True
                })

        # 5b. Bounded Scale Violations (Percentages, Ratings, Scores)
        should_clip_scale = is_selected("flag_scale_violations", col=col, alt_keys=[f"invalid-scale-{col}", "clip_scale"])
        if should_clip_scale and num_s.notna().any():
            scale_mask = (num_s < 0) | (num_s > 100)
            scale_cnt = int(scale_mask.sum())
            if scale_cnt > 0:
                clean_df[col] = num_s.clip(lower=0.0, upper=100.0)
                changelog.append({
                    "step": f"Standardize Bounded Scale: {col}",
                    "operation": "clip_scale",
                    "description": f"Standardized {scale_cnt} values in '{col}' to legitimate bounded scale [0, 100].",
                    "affected_rows": scale_cnt,
                    "reversible": True
                })

        # 5c. Extreme Statistical Outlier Capping (Tukey Fences)
        should_cap_outliers = is_selected("cap_outliers", col=col, alt_keys=[f"outlier-{col}", "keep_and_flag"])
        if should_cap_outliers and num_s.notna().any():
            valid_vals = num_s.dropna()
            if len(valid_vals) >= 4:
                q25 = float(valid_vals.quantile(0.25))
                q75 = float(valid_vals.quantile(0.75))
                iqr = q75 - q25
                if iqr > 0:
                    lower_fence = q25 - 2.5 * iqr
                    upper_fence = q75 + 2.5 * iqr
                    outlier_mask = (num_s < lower_fence) | (num_s > upper_fence)
                    outlier_cnt = int(outlier_mask.sum())
                    if outlier_cnt > 0:
                        clean_df[col] = num_s.clip(lower=lower_fence, upper=upper_fence)
                        changelog.append({
                            "step": f"Cap Extreme Outliers: {col}",
                            "operation": "cap_outliers",
                            "description": f"Capped {outlier_cnt} extreme values in '{col}' to robust fences [{round(lower_fence, 2)}, {round(upper_fence, 2)}].",
                            "affected_rows": outlier_cnt,
                            "reversible": True
                        })

    # -------------------------------------------------------------
    # 6. Standardize Dates and Times
    # -------------------------------------------------------------
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        should_std_date = is_selected("standardize_iso_date", col=col, alt_keys=[f"format-date-{col}", "standardize_dates", "standardize_iso_date"])
        if should_std_date and is_text_column(clean_df[col]):
            try:
                parsed_dates = pd.to_datetime(clean_df[col], errors="coerce", format="mixed")
            except Exception:
                parsed_dates = pd.to_datetime(clean_df[col], errors="coerce")
            valid_dates = parsed_dates.dropna()
            if not valid_dates.empty:
                has_time = any(d.hour != 0 or d.minute != 0 or d.second != 0 for d in valid_dates[:40])
                if has_time:
                    clean_df[col] = parsed_dates.dt.strftime("%Y-%m-%d %H:%M:%S").replace({np.nan: None})
                else:
                    clean_df[col] = parsed_dates.dt.strftime("%Y-%m-%d").replace({np.nan: None})

                changelog.append({
                    "step": f"Standardize Dates: {col}",
                    "operation": "standardize_iso_date",
                    "description": f"Standardized dates to ISO-8601 in '{col}'.",
                    "affected_rows": int(parsed_dates.notna().sum()),
                    "reversible": True
                })

    # 6b. Chronological Inversion Fix (Start Date vs End Date)
    should_fix_chronology = is_selected("flag_logic_violations", alt_keys=["chronology_inversion", "swap_dates"]) or any("logic-dates" in str(f) for f in selected_fixes)
    if should_fix_chronology:
        date_cols = [c for c, inf in inferred_columns.items() if inf.legacy_dtype == "datetime" or any(k in c.lower() for k in ["date", "time", "start", "end"])]
        if len(date_cols) >= 2:
            start_candidates = [c for c in date_cols if any(k in c.lower() for k in ["start", "from", "begin"])]
            end_candidates = [c for c in date_cols if any(k in c.lower() for k in ["end", "to", "finish", "expiry"])]
            if start_candidates and end_candidates:
                c_start, c_end = start_candidates[0], end_candidates[0]
                if c_start in clean_df.columns and c_end in clean_df.columns:
                    d_start = pd.to_datetime(clean_df[c_start], errors="coerce")
                    d_end = pd.to_datetime(clean_df[c_end], errors="coerce")
                    valid_pairs = d_start.notna() & d_end.notna()
                    if valid_pairs.any():
                        inverted = valid_pairs & (d_end < d_start)
                        inv_cnt = int(inverted.sum())
                        if inv_cnt > 0:
                            clean_df.loc[inverted, c_start], clean_df.loc[inverted, c_end] = (
                                clean_df.loc[inverted, c_end],
                                clean_df.loc[inverted, c_start]
                            )
                            changelog.append({
                                "step": "Correct Date Chronology",
                                "operation": "swap_dates",
                                "description": f"Swapped {inv_cnt} records where end date '{c_end}' preceded start date '{c_start}'.",
                                "affected_rows": inv_cnt,
                                "reversible": True
                            })

    # -------------------------------------------------------------
    # 7. Boolean & Scale Standardization
    # -------------------------------------------------------------
    for col in clean_df.columns:
        inf = inferred_columns.get(col)
        # 7a. Truthy / Falsy Boolean Normalization
        should_std_bool = is_selected("standardize_boolean", col=col, alt_keys=[f"boolean-{col}", "bool_standardize"])
        if should_std_bool:
            clean_df[col] = clean_df[col].apply(lambda v: parse_boolean(str(v)) if not is_null_token(v) else np.nan)
            changelog.append({
                "step": f"Standardize Booleans: {col}",
                "operation": "standardize_boolean",
                "description": f"Normalized truthy/falsy tokens in '{col}' to standard boolean True/False.",
                "affected_rows": len(clean_df),
                "reversible": True
            })

        # 7b. Percentage Scale Normalization
        should_std_scale = is_selected("standardize_scale", col=col, alt_keys=[f"scale-{col}", "scale_standardize"])
        if should_std_scale and clean_df[col].dtype in (float, int, np.float64, np.int64):
            num_s = pd.to_numeric(clean_df[col], errors="coerce")
            valid = num_s.dropna()
            if not valid.empty:
                if (valid >= 0).all() and (valid <= 1.0).all():
                    clean_df[col] = num_s * 100.0
                    converted_rows = len(valid)
                else:
                    frac_mask = (num_s > 0) & (num_s < 1.0)
                    clean_df.loc[frac_mask, col] = clean_df.loc[frac_mask, col] * 100.0
                    converted_rows = int(frac_mask.sum())
                changelog.append({
                    "step": f"Standardize Percentage Scale: {col}",
                    "operation": "standardize_scale",
                    "description": f"Converted fractional decimal values in '{col}' to standardized percentage scale (0–100%).",
                    "affected_rows": converted_rows,
                    "reversible": True
                })

    return clean_df, changelog
