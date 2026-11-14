import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
import numpy as np
import pandas as pd

# Standard tokens considered missing/null
NULL_TOKENS = {
    "", " ", "nan", "nan", "null", "none", "n/a", "na", "-", "--", "---",
    "?", "unknown", "tbd", "tba", "not available", "missing", "nil",
    "#n/a", "#value!", "#ref!", "nonetype", "undefined"
}

BOOLEAN_TRUE_TOKENS = {"true", "t", "yes", "y", "1", "oui", "ja", "sim", "vrai", "on"}
BOOLEAN_FALSE_TOKENS = {"false", "f", "no", "n", "0", "non", "nein", "nao", "não", "faux", "off"}

CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₹", "₽", "₩", "₺", "₫", "฿", "R$", "zł", "CHF"}
CURRENCY_CODES = {"USD", "EUR", "GBP", "INR", "JPY", "CNY", "CAD", "AUD", "BRL", "CHF", "RUB"}

DURATION_PATTERNS = [
    r"^(\d+)\s*(?:sec|second|seconds|s)$",
    r"^(\d+)\s*(?:min|minute|minutes|m)$",
    r"^(\d+)\s*(?:hr|hour|hours|h)$",
    r"^(\d+)\s*(?:d|day|days)$",
    r"^(\d+):([0-5]\d):([0-5]\d)$",
    r"^(\d+):([0-5]\d)$",
    r"^(\d+)\s*h\s*(\d+)\s*m(?:in)?$"
]

@dataclass
class ParsedValue:
    val: Any
    is_valid: bool
    raw_str: str

@dataclass
class ColumnInferenceResult:
    storage_type: Literal["integer", "decimal", "text", "date", "datetime", "time", "boolean"]
    semantic_role: Literal[
        "identifier", "category", "measure", "amount/currency", "percentage",
        "rate", "count", "duration", "year", "geographic", "free text", "constant"
    ]
    legacy_dtype: Literal["numeric", "categorical", "datetime", "boolean", "text"]
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str
    parsed_series: pd.Series
    valid_count: int
    null_count: int
    invalid_count: int
    invalid_pct: float
    invalid_samples: list[str] = field(default_factory=list)
    detected_format: str | None = None
    needs_review: bool = False
    review_question: str | None = None
    stats: dict[str, Any] | None = None
    top_values: list[dict[str, Any]] | None = None
    flags: list[str] = field(default_factory=list)

def is_null_token(val: Any) -> bool:
    if val is None or pd.isna(val):
        return True
    s = str(val).strip().lower()
    return s in NULL_TOKENS

def get_null_mask(series: pd.Series) -> pd.Series:
    """Fast vectorized null mask detecting pandas NA and domain null tokens."""
    isna_mask = series.isna()
    if isna_mask.all():
        return isna_mask
    sub = series[~isna_mask].astype(str).str.strip().str.lower()
    token_mask = sub.isin(NULL_TOKENS)
    full_mask = isna_mask.copy()
    full_mask.loc[~isna_mask] = token_mask
    return full_mask

def parse_boolean(val: str) -> bool | None:
    s = val.strip().lower()
    if s in BOOLEAN_TRUE_TOKENS:
        return True
    if s in BOOLEAN_FALSE_TOKENS:
        return False
    return None

def parse_duration_to_seconds(val: str) -> float | None:
    s = val.strip().lower()
    # 01:45:00
    m = re.match(r"^(\d+):([0-5]\d):([0-5]\d)$", s)
    if m:
        return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
    # 01:45
    m = re.match(r"^(\d+):([0-5]\d)$", s)
    if m:
        return float(m.group(1)) * 60 + float(m.group(2))
    # 2h 5m
    m = re.match(r"^(\d+)\s*h(?:ours?)?\s*(\d+)\s*m(?:in|inutes?)?$", s)
    if m:
        return float(m.group(1)) * 3600 + float(m.group(2)) * 60
    # 97 min
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:min|minute|minutes|m)$", s)
    if m:
        return float(m.group(1)) * 60
    # 2 hr
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:hr|hour|hours|h)$", s)
    if m:
        return float(m.group(1)) * 3600
    # 3 days
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:d|day|days)$", s)
    if m:
        return float(m.group(1)) * 86400
    return None

def parse_tolerant_number(val: str) -> tuple[float | None, dict[str, Any]]:
    """
    Parses numbers tolerantly across:
    - Decimal commas (1.234,56 or 12,50)
    - Indian lakh/crore (12,34,567.89)
    - Currency symbols ($, €, £, etc.)
    - Percent signs (45%)
    - Parentheses negatives (123.45) -> -123.45
    - Suffixes (K, M, B, lakh, crore)
    - Scientific notation (1.23e-4, 1E5)
    """
    metadata: dict[str, Any] = {
        "is_currency": False,
        "is_percentage": False,
        "is_parentheses_neg": False,
        "suffix": None,
        "is_integer": False,
    }

    if not isinstance(val, str):
        val = str(val)

    s = val.strip()
    if not s or s.lower() in NULL_TOKENS:
        return None, metadata

    # Check parentheses negative: (123.45)
    is_neg = False
    if s.startswith("(") and s.endswith(")"):
        is_neg = True
        s = s[1:-1].strip()
        metadata["is_parentheses_neg"] = True

    # Check currency symbols / codes
    for sym in CURRENCY_SYMBOLS:
        if sym in s:
            metadata["is_currency"] = True
            s = s.replace(sym, "").strip()
            break
    for code in CURRENCY_CODES:
        if code in s:
            metadata["is_currency"] = True
            s = re.sub(rf"\b{code}\b", "", s).strip()
            break

    # Check percentage
    if "%" in s:
        metadata["is_percentage"] = True
        s = s.replace("%", "").strip()

    # Check suffixes (K, M, B, million, billion, crore, lakh)
    multiplier = 1.0
    s_lower = s.lower().strip()
    if s_lower.endswith("crore") or s_lower.endswith("cr"):
        multiplier = 10000000.0
        s = re.sub(r"(?i)\s*(crore|cr)$", "", s).strip()
        metadata["suffix"] = "crore"
    elif s_lower.endswith("lakh") or s_lower.endswith("lac"):
        multiplier = 100000.0
        s = re.sub(r"(?i)\s*(lakh|lac)$", "", s).strip()
        metadata["suffix"] = "lakh"
    elif s_lower.endswith("billion") or s.endswith("B"):
        multiplier = 1000000000.0
        s = re.sub(r"(?i)\s*(billion|b)$", "", s).strip()
        metadata["suffix"] = "B"
    elif s_lower.endswith("million") or s.endswith("M"):
        multiplier = 1000000.0
        s = re.sub(r"(?i)\s*(million|m)$", "", s).strip()
        metadata["suffix"] = "M"
    elif s.endswith("k") or s.endswith("K"):
        multiplier = 1000.0
        s = s[:-1].strip()
        metadata["suffix"] = "K"

    # Normalize spaces inside numbers (e.g. French '1 234,56')
    s = s.replace("\u00A0", " ") # non-breaking space
    s = re.sub(r"(?<=\d)\s(?=\d)", "", s)

    # Detect European decimal comma vs standard
    # Cases:
    # 1. '1.234,56' -> period is thousands, comma is decimal
    # 2. '1,234.56' -> comma is thousands, period is decimal
    # 3. '123,45' (has comma, no period) -> comma is decimal
    # 4. '12,34,567.89' (Indian format) -> period is decimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:
            # 1,234.56
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        # Check if comma is decimal (e.g. 12,5 or 12,50) vs thousands (1,000)
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(",", ".")
        elif len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")

    # Now attempt standard float parse
    try:
        num = float(s)
        if is_neg:
            num = -num
        num *= multiplier

        # Check if exact integer
        if num.is_integer() and not metadata["is_percentage"] and multiplier == 1.0:
            metadata["is_integer"] = True

        return num, metadata
    except (ValueError, OverflowError):
        return None, metadata

def analyze_date_column(non_null_samples: list[str]) -> tuple[bool, str | None, bool, str | None, bool]:
    """
    Analyzes date patterns.
    Returns: (is_date, format_or_type, is_ambiguous_day_month, reason, has_day_over_12)
    """
    if not non_null_samples:
        return False, None, False, None, False

    # Check common date patterns
    sample_size = min(len(non_null_samples), 50)
    samples = non_null_samples[:sample_size]

    # Pattern check
    date_regex = re.compile(
        r"^(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
        r"(?:[T\s](\d{1,2}:\d{1,2}(?::\d{1,2})?(?:\.\d+)?)?(?:\s*(?:AM|PM|am|pm))?(?:Z|[+-]\d{2}:?\d{2})?)?$"
    )

    matching_samples = [s for s in samples if date_regex.match(s.strip())]
    if len(matching_samples) / len(samples) < 0.7:
        # Check Unix timestamps: integers between 1e9 and 2e9 (seconds) or 1e12 and 2e12 (ms)
        try:
            nums = [float(s) for s in samples if s.replace(".", "", 1).isdigit()]
            if len(nums) / len(samples) >= 0.8:
                if all(946684800 <= n <= 2147483647 for n in nums): # 2000 to 2038 in seconds
                    return True, "unix_timestamp_seconds", False, "Detected Unix timestamps (seconds: 2000-2038).", False
                if all(946684800000 <= n <= 2147483647000 for n in nums):
                    return True, "unix_timestamp_ms", False, "Detected Unix timestamps (milliseconds).", False
        except Exception:
            pass

        return False, None, False, None, False

    # Disambiguate day-first vs month-first
    # E.g. '03/04/2020' vs '25/03/2020'
    has_day_over_12 = False
    has_month_over_12 = False
    two_digit_years = False
    has_slash_or_dash = False

    for s in matching_samples:
        clean = s.strip().split()[0].split("T")[0]
        parts = re.split(r"[-/.]", clean)
        if len(parts) == 3:
            has_slash_or_dash = True
            p0, p1, p2 = parts
            if len(p0) == 4: # YYYY-MM-DD
                continue
            if len(p2) == 2:
                two_digit_years = True
            try:
                v0, v1 = int(p0), int(p1)
                if v0 > 12:
                    has_day_over_12 = True
                if v1 > 12:
                    has_month_over_12 = True
            except ValueError:
                pass

    is_ambiguous = False
    fmt_reason = "Standard ISO or resolved date format."
    if has_slash_or_dash:
        if has_day_over_12 and not has_month_over_12:
            fmt_reason = "Disambiguated as Day-first (found day values > 12)."
        elif has_month_over_12 and not has_day_over_12:
            fmt_reason = "Disambiguated as Month-first (found month values > 12)."
        elif not has_day_over_12 and not has_month_over_12:
            is_ambiguous = True
            fmt_reason = "Ambiguous Day/Month: all day and month values are <= 12."

    if two_digit_years:
        fmt_reason += " Contains 2-digit years (e.g. '24')."

    return True, "date_or_datetime", is_ambiguous, fmt_reason, has_day_over_12

def infer_column_type(
    series: pd.Series,
    col_name: str,
    total_rows: int
) -> ColumnInferenceResult:
    """
    Infers storage type and semantic role for a column strictly from data,
    using column name only as a soft confidence hint.
    """
    non_null_mask = ~get_null_mask(series)
    non_null_series = series[non_null_mask].astype(str)
    n_non_null = len(non_null_series)
    n_null = total_rows - n_non_null
    name_lower = col_name.lower().strip()

    flags = []

    # 1. Check all-missing / 0 valid rows
    if n_non_null == 0:
        return ColumnInferenceResult(
            storage_type="text",
            semantic_role="constant",
            legacy_dtype="text",
            confidence="high",
            confidence_reason="Column contains 100% missing values.",
            parsed_series=pd.Series(index=series.index, dtype=object),
            valid_count=0,
            null_count=total_rows,
            invalid_count=0,
            invalid_pct=0.0,
            flags=["all_missing", "constant"]
        )

    # 2. Check constant (1 unique non-null value)
    unique_vals = non_null_series.unique()
    if len(unique_vals) == 1 and total_rows > 1:
        flags.append("constant")
        return ColumnInferenceResult(
            storage_type="text",
            semantic_role="constant",
            legacy_dtype="categorical",
            confidence="high",
            confidence_reason=f"Column has only 1 constant non-null value: '{unique_vals[0]}'.",
            parsed_series=series.replace(list(NULL_TOKENS), None),
            valid_count=n_non_null,
            null_count=n_null,
            invalid_count=0,
            invalid_pct=0.0,
            flags=flags,
            top_values=[{"value": str(unique_vals[0]), "count": n_non_null}]
        )

    # Systematic sample for large series (up to 1,000 items)
    if n_non_null > 1000:
        step = max(1, n_non_null // 1000)
        sample_series = non_null_series.iloc[::step].iloc[:1000]
    else:
        sample_series = non_null_series

    # 3. Test Boolean
    sample_bool = [parse_boolean(v) for v in sample_series]
    sample_bool_valid = sum(1 for b in sample_bool if b is not None)
    if (sample_bool_valid / len(sample_series)) >= 0.7:
        bool_parsed = [parse_boolean(v) for v in non_null_series] if n_non_null > len(sample_series) else sample_bool
        bool_valid_cnt = sum(1 for b in bool_parsed if b is not None)
        if bool_valid_cnt / n_non_null >= 0.8:
            parsed_s = pd.Series(index=series.index, dtype=object)
            idx_mask = np.where(non_null_mask)[0]
            parsed_s.iloc[idx_mask] = bool_parsed
            inv_cnt = n_non_null - bool_valid_cnt
            inv_samples = [v for v, b in zip(non_null_series, bool_parsed) if b is None][:5]
            return ColumnInferenceResult(
                storage_type="boolean",
                semantic_role="category",
                legacy_dtype="boolean",
                confidence="high" if inv_cnt == 0 else "medium",
                confidence_reason=f"{round(bool_valid_cnt/n_non_null*100, 1)}% of values parse as booleans.",
                parsed_series=parsed_s,
                valid_count=bool_valid_cnt,
                null_count=n_null,
                invalid_count=inv_cnt,
                invalid_pct=round(inv_cnt / total_rows * 100.0, 2),
                invalid_samples=inv_samples,
                flags=flags,
                top_values=[
                    {"value": "True", "count": sum(1 for b in bool_parsed if b is True)},
                    {"value": "False", "count": sum(1 for b in bool_parsed if b is False)}
                ]
            )

    # 4. Test Duration
    sample_dur = [parse_duration_to_seconds(v) for v in sample_series]
    sample_dur_valid = sum(1 for d in sample_dur if d is not None)
    if (sample_dur_valid / len(sample_series)) >= 0.7:
        dur_parsed = [parse_duration_to_seconds(v) for v in non_null_series] if n_non_null > len(sample_series) else sample_dur
        dur_valid_cnt = sum(1 for d in dur_parsed if d is not None)
        if dur_valid_cnt / n_non_null >= 0.8:
            parsed_s = pd.Series(np.nan, index=series.index, dtype=float)
            idx_mask = np.where(non_null_mask)[0]
            parsed_s.iloc[idx_mask] = [float(d) if d is not None else np.nan for d in dur_parsed]
            inv_cnt = n_non_null - dur_valid_cnt
            inv_samples = [v for v, d in zip(non_null_series, dur_parsed) if d is None][:5]
            return ColumnInferenceResult(
                storage_type="decimal",
                semantic_role="duration",
                legacy_dtype="numeric",
                confidence="high" if inv_cnt == 0 else "medium",
                confidence_reason=f"{round(dur_valid_cnt/n_non_null*100, 1)}% of values are time durations (normalized to seconds).",
                parsed_series=parsed_s,
                valid_count=dur_valid_cnt,
                null_count=n_null,
                invalid_count=inv_cnt,
                invalid_pct=round(inv_cnt / total_rows * 100.0, 2),
                invalid_samples=inv_samples,
                flags=flags
            )

    # 5. Test Date / Datetime
    is_date, dt_fmt, is_ambiguous, dt_reason, has_day_over_12 = analyze_date_column(sample_series.tolist())
    if is_date:
        parsed_dates = pd.to_datetime(non_null_series, errors="coerce", dayfirst=has_day_over_12)
        dt_valid_cnt = int(parsed_dates.notna().sum())
        if dt_valid_cnt / n_non_null >= 0.75:
            inv_cnt = n_non_null - dt_valid_cnt
            inv_samples = non_null_series[parsed_dates.isna()].head(5).tolist()

            has_time = any(d.hour != 0 or d.minute != 0 or d.second != 0 for d in parsed_dates.dropna()[:30])
            storage = "datetime" if has_time else "date"

            conf: Literal["high", "medium", "low"] = "high"
            if is_ambiguous or inv_cnt > 0:
                conf = "medium"

            review_q = None
            if is_ambiguous:
                review_q = f"Date column '{col_name}' has ambiguous Day/Month order (e.g. '{non_null_series.iloc[0]}'). Is this Day-first (DD/MM) or Month-first (MM/DD)?"

            stats = {
                "min_date": str(parsed_dates.min()),
                "max_date": str(parsed_dates.max())
            }

            return ColumnInferenceResult(
                storage_type=storage,
                semantic_role="measure" if has_time else "date" if storage == "date" else "datetime",
                legacy_dtype="datetime",
                confidence=conf,
                confidence_reason=f"Parsed as {storage}. {dt_reason}",
                parsed_series=pd.to_datetime(series, errors="coerce", dayfirst=has_day_over_12),
                valid_count=dt_valid_cnt,
                null_count=n_null,
                invalid_count=inv_cnt,
                invalid_pct=round(inv_cnt / total_rows * 100.0, 2),
                invalid_samples=inv_samples,
                detected_format=dt_fmt,
                needs_review=is_ambiguous,
                review_question=review_q,
                stats=stats,
                flags=flags
            )

    # 6. Test Numbers
    # 6a. Fast path: try standard numeric parsing (C-optimized)
    fast_nums = pd.to_numeric(non_null_series, errors="coerce")
    fast_valid_cnt = int(fast_nums.notna().sum())

    if fast_valid_cnt / n_non_null >= 0.8:
        valid_nums_s = fast_nums.dropna()
        all_integers = bool((valid_nums_s % 1 == 0).all()) if not valid_nums_s.empty else False
        storage_type: Literal["integer", "decimal"] = "integer" if all_integers else "decimal"

        is_currency = any(k in name_lower for k in ["price", "cost", "revenue", "salary", "wage", "amount", "budget", "sales", "fee"])
        is_percentage = "%" in name_lower or "pct" in name_lower or "percent" in name_lower
        is_year = all_integers and bool((valid_nums_s >= 1800).all() and (valid_nums_s <= 2100).all()) and any(k in name_lower for k in ["year", "yr", "birth"])

        unique_cnt = int(valid_nums_s.nunique())
        is_id_like = False
        if all_integers and not is_currency and not is_percentage and not is_year:
            has_leading_zeros = any(v.startswith("0") and len(v) > 1 and v.isdigit() for v in sample_series)
            is_unique = (unique_cnt == n_non_null) and (n_non_null >= 5)
            has_id_name = any(k in name_lower for k in ["id", "code", "key", "zip", "postal", "phone", "ssn", "account", "ticket", "order_num", "seq"])

            if has_leading_zeros or (is_unique and has_id_name) or (is_unique and "id" in name_lower):
                is_id_like = True
                flags.append("id_like")

        inv_cnt = n_non_null - fast_valid_cnt
        inv_samples = non_null_series[fast_nums.isna()].head(5).tolist()

        if is_id_like:
            semantic_role = "identifier"
            legacy_dtype = "text"
            conf = "high"
            reason = "Unique/code integer pattern with ID characteristics (preserved as identifier, not measure)."
        elif is_year:
            semantic_role = "year"
            legacy_dtype = "numeric"
            conf = "high"
            reason = "Integer range 1800-2100 matching year semantics."
        elif is_currency:
            semantic_role = "amount/currency"
            legacy_dtype = "numeric"
            conf = "high"
            reason = "Monetary currency values detected from symbols/keywords."
        elif is_percentage:
            semantic_role = "percentage"
            legacy_dtype = "numeric"
            conf = "high"
            reason = "Percentage scale detected."
        elif all_integers and bool((valid_nums_s >= 0).all()) and any(k in name_lower for k in ["count", "quantity", "num_", "n_", "visits", "clicks"]):
            semantic_role = "count"
            legacy_dtype = "numeric"
            conf = "high"
            reason = "Non-negative integer count."
        else:
            semantic_role = "measure"
            legacy_dtype = "numeric"
            conf = "high" if inv_cnt == 0 else "medium"
            reason = f"{round(fast_valid_cnt/n_non_null*100, 1)}% numeric values."

        stats = {
            "mean": round(float(valid_nums_s.mean()), 3),
            "std": round(float(valid_nums_s.std(ddof=1)), 3) if len(valid_nums_s) > 1 else 0.0,
            "min": round(float(valid_nums_s.min()), 3),
            "q25": round(float(valid_nums_s.quantile(0.25)), 3),
            "median": round(float(valid_nums_s.median()), 3),
            "q75": round(float(valid_nums_s.quantile(0.75)), 3),
            "max": round(float(valid_nums_s.max()), 3),
            "skew": round(float(valid_nums_s.skew()), 3) if len(valid_nums_s) > 2 else 0.0,
            "kurtosis": round(float(valid_nums_s.kurtosis()), 3) if len(valid_nums_s) > 3 else 0.0,
            "iqr": round(float(valid_nums_s.quantile(0.75) - valid_nums_s.quantile(0.25)), 3),
        }

        parsed_s = pd.Series(np.nan, index=series.index, dtype=float)
        idx_mask = np.where(non_null_mask)[0]
        parsed_s.iloc[idx_mask] = fast_nums.values

        return ColumnInferenceResult(
            storage_type=storage_type,
            semantic_role=semantic_role,
            legacy_dtype=legacy_dtype,
            confidence=conf,
            confidence_reason=reason,
            parsed_series=parsed_s,
            valid_count=fast_valid_cnt,
            null_count=n_null,
            invalid_count=inv_cnt,
            invalid_pct=round(inv_cnt / total_rows * 100.0, 2),
            invalid_samples=inv_samples,
            stats=stats,
            flags=flags
        )

    # 6b. Tolerant parsing path (for currency symbols, commas, percent signs, suffixes)
    sample_num_res = [parse_tolerant_number(v) for v in sample_series]
    sample_nums = [res[0] for res in sample_num_res]
    sample_num_valid = sum(1 for n in sample_nums if n is not None)

    if (sample_num_valid / len(sample_series)) >= 0.7:
        num_results = [parse_tolerant_number(v) for v in non_null_series] if n_non_null > len(sample_series) else sample_num_res
        nums = [res[0] for res in num_results]
        metas = [res[1] for res in num_results]
        num_valid_cnt = sum(1 for n in nums if n is not None)

        if num_valid_cnt / n_non_null >= 0.8:
            valid_nums = [n for n in nums if n is not None]
            valid_metas = [m for n, m in zip(nums, metas) if n is not None]
            inv_cnt = n_non_null - num_valid_cnt
            inv_samples = [v for v, n in zip(non_null_series, nums) if n is None][:5]

            # Determine if integer or decimal
            all_integers = all(m["is_integer"] for m in valid_metas)
            storage_type: Literal["integer", "decimal"] = "integer" if all_integers else "decimal"

            # Check semantic roles:
            # Currency:
            currency_cnt = sum(1 for m in valid_metas if m["is_currency"])
            is_currency = (currency_cnt / len(valid_metas) >= 0.2) or any(k in name_lower for k in ["price", "cost", "revenue", "salary", "wage", "amount", "budget", "sales", "fee"])

            # Percentage:
            percent_cnt = sum(1 for m in valid_metas if m["is_percentage"])
            is_percentage = (percent_cnt / len(valid_metas) >= 0.2) or "%" in name_lower or "pct" in name_lower or "percent" in name_lower

            # Year:
            is_year = all_integers and all(1800 <= n <= 2100 for n in valid_nums) and any(k in name_lower for k in ["year", "yr", "birth"])

            # ID-like check:
            unique_cnt = len(set(valid_nums))
            is_id_like = False
            if all_integers and not is_currency and not is_percentage and not is_year:
                has_leading_zeros = any(v.startswith("0") and len(v) > 1 and v.isdigit() for v in non_null_series)
                is_unique = (unique_cnt == n_non_null) and (n_non_null >= 5)
                has_id_name = any(k in name_lower for k in ["id", "code", "key", "zip", "postal", "phone", "ssn", "account", "ticket", "order_num", "seq"])

                if has_leading_zeros or (is_unique and has_id_name) or (is_unique and "id" in name_lower):
                    is_id_like = True
                    flags.append("id_like")

            # Assign semantic role
            if is_id_like:
                semantic_role = "identifier"
                legacy_dtype = "text"
                conf = "high"
                reason = "Unique/code integer pattern with ID characteristics (preserved as identifier, not measure)."
            elif is_year:
                semantic_role = "year"
                legacy_dtype = "numeric"
                conf = "high"
                reason = "Integer range 1800-2100 matching year semantics."
            elif is_currency:
                semantic_role = "amount/currency"
                legacy_dtype = "numeric"
                conf = "high"
                reason = "Monetary currency values detected from symbols/keywords."
            elif is_percentage:
                semantic_role = "percentage"
                legacy_dtype = "numeric"
                conf = "high"
                reason = "Percentage scale detected."
            elif all_integers and all(n >= 0 for n in valid_nums) and any(k in name_lower for k in ["count", "quantity", "num_", "n_", "visits", "clicks"]):
                semantic_role = "count"
                legacy_dtype = "numeric"
                conf = "high"
                reason = "Non-negative integer count."
            else:
                semantic_role = "measure"
                legacy_dtype = "numeric"
                conf = "high" if inv_cnt == 0 else "medium"
                reason = f"{round(num_valid_cnt/n_non_null*100, 1)}% numeric values."

            # Compute summary stats
            valid_series = pd.Series(valid_nums)
            stats = {
                "mean": round(float(valid_series.mean()), 3),
                "std": round(float(valid_series.std(ddof=1)), 3) if len(valid_series) > 1 else 0.0,
                "min": round(float(valid_series.min()), 3),
                "q25": round(float(valid_series.quantile(0.25)), 3),
                "median": round(float(valid_series.median()), 3),
                "q75": round(float(valid_series.quantile(0.75)), 3),
                "max": round(float(valid_series.max()), 3),
                "skew": round(float(valid_series.skew()), 3) if len(valid_series) > 2 else 0.0,
                "kurtosis": round(float(valid_series.kurtosis()), 3) if len(valid_series) > 3 else 0.0,
                "iqr": round(float(valid_series.quantile(0.75) - valid_series.quantile(0.25)), 3),
            }

            # Build parsed series
            parsed_s = pd.Series(np.nan, index=series.index, dtype=float)
            idx_mask = np.where(non_null_mask)[0]
            parsed_s.iloc[idx_mask] = [float(n) if n is not None else np.nan for n in nums]

            return ColumnInferenceResult(
                storage_type=storage_type,
                semantic_role=semantic_role,
                legacy_dtype=legacy_dtype,
                confidence=conf,
                confidence_reason=reason,
                parsed_series=parsed_s,
                valid_count=num_valid_cnt,
                null_count=n_null,
                invalid_count=inv_cnt,
                invalid_pct=round(inv_cnt / total_rows * 100.0, 2),
                invalid_samples=inv_samples,
                stats=stats,
                flags=flags
            )

    # 7. Text / Categorical / Geographic / Free Text / Identifier
    unique_cnt = non_null_series.nunique()
    cardinality_ratio = unique_cnt / n_non_null if n_non_null > 0 else 0.0
    avg_len = non_null_series.str.len().mean()

    # Check Geographic hints
    geo_keywords = ["country", "state", "city", "region", "province", "postal", "zip", "latitude", "longitude", "lat", "lon"]
    is_geo = any(k in name_lower for k in geo_keywords)

    # Check ID strings (e.g. UUID, alphanumeric codes, 100% unique short strings)
    is_id = False
    if unique_cnt == n_non_null and n_non_null >= 10:
        is_id = True
        flags.append("id_like")
    elif any(k in name_lower for k in ["id", "uuid", "hash", "key", "token"]):
        is_id = True
        flags.append("id_like")

    if is_id:
        role = "identifier"
        legacy_dtype = "text"
        storage = "text"
        reason = f"Distinct alphanumeric identifier (100% unique or ID keyword)."
    elif is_geo:
        role = "geographic"
        legacy_dtype = "categorical"
        storage = "text"
        reason = "Geographic location metadata."
    elif avg_len > 80:
        role = "free text"
        legacy_dtype = "text"
        storage = "text"
        reason = f"Unstructured free text (average character length {round(avg_len, 1)})."
    elif unique_cnt <= 60 or cardinality_ratio <= 0.25:
        role = "category"
        legacy_dtype = "categorical"
        storage = "text"
        reason = f"Discrete category with {unique_cnt} distinct labels."
    else:
        role = "free text"
        legacy_dtype = "text"
        storage = "text"
        reason = f"High-cardinality textual descriptions."

    # Top values for categories
    top_counts = non_null_series.value_counts().head(10)
    top_values = [{"value": str(k), "count": int(v)} for k, v in top_counts.items()]

    parsed_s = series.replace(list(NULL_TOKENS), None)

    return ColumnInferenceResult(
        storage_type=storage,
        semantic_role=role,
        legacy_dtype=legacy_dtype,
        confidence="high",
        confidence_reason=reason,
        parsed_series=parsed_s,
        valid_count=n_non_null,
        null_count=n_null,
        invalid_count=0,
        invalid_pct=0.0,
        top_values=top_values,
        flags=flags
    )

def sanitize_for_json(obj: Any) -> Any:
    """Recursively replaces NaNs, infinities, numpy arrays, and numpy primitives with standard Python types."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    elif isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    elif isinstance(obj, (np.floating, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return round(float(obj), 6)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (pd.Timestamp, np.datetime64)):
        return str(obj)
    elif pd.api.types.is_scalar(obj) and pd.isna(obj):
        return None
    return obj
