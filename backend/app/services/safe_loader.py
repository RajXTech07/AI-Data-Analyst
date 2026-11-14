import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import pandas as pd

from app.core.errors import UnsupportedFile, ValidationFailed
from app.core.logging import logger

SUMMARY_ROW_PATTERNS = [
    r"^total(s)?$", r"^grand total(s)?$", r"^subtotal(s)?$", r"^sum$",
    r"^average(s)?$", r"^mean$", r"^overall$", r"^summary$",
    r"^report generated", r"^confidential", r"^notes?:", r"^copyright"
]

@dataclass
class SafeLoadResult:
    df: pd.DataFrame
    raw_df: pd.DataFrame
    encoding: str
    delimiter: str
    quotechar: str
    loading_report: dict[str, Any] = field(default_factory=dict)
    raw_shape: tuple[int, int] = (0, 0)
    warnings: list[str] = field(default_factory=list)

def detect_encoding(content: bytes) -> tuple[str, float]:
    """Detects text encoding safely among UTF-8, UTF-8-BOM, UTF-16, Latin-1, CP1252."""
    if not content:
        return "utf-8", 1.0

    # UTF-8 BOM
    if content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", 1.0

    # UTF-16 BOM
    if content.startswith(b"\xff\xfe"):
        return "utf-16-le", 1.0
    if content.startswith(b"\xfe\xff"):
        return "utf-16-be", 1.0

    # Binary check (presence of null bytes in non-UTF16 text)
    sample = content[:4096]
    if b"\x00" in sample:
        # Check if it might be UTF-16 without BOM
        try:
            sample.decode("utf-16")
            return "utf-16", 0.9
        except Exception:
            raise UnsupportedFile("Binary file detected. Please upload a valid text CSV.")

    # Try strict UTF-8
    try:
        content.decode("utf-8")
        return "utf-8", 1.0
    except UnicodeDecodeError:
        pass

    # Try CP1252 / Latin-1
    for enc in ["cp1252", "iso-8859-1", "latin-1"]:
        try:
            content.decode(enc)
            return enc, 0.8
        except UnicodeDecodeError:
            continue

    raise ValidationFailed("Could not decode CSV text. Unsupported encoding.")

def detect_delimiter(sample_text: str) -> tuple[str, float]:
    """
    Robust delimiter detector evaluating comma, semicolon, tab, and pipe.
    Scores by line-to-line field count consistency and Sniffer.
    """
    candidates = [',', ';', '\t', '|']
    lines = [line for line in sample_text.splitlines() if line.strip() and not line.strip().startswith(('#', '//'))][:40]

    if not lines:
        return ',', 0.5

    best_delim = ','
    best_score = -1.0

    # 1. Python Sniffer as initial signal
    sniffer_delim = None
    try:
        sniffed = csv.Sniffer().sniff("\n".join(lines[:10]), delimiters=";,|\t,")
        sniffer_delim = sniffed.delimiter
    except Exception:
        sniffer_delim = None

    # 2. Consistency analysis across lines
    for cand in candidates:
        col_counts = []
        for l in lines:
            try:
                row = next(csv.reader([l], delimiter=cand))
                col_counts.append(len(row))
            except Exception:
                continue

        if not col_counts:
            continue
        first_row_cnt = col_counts[0]
        if first_row_cnt <= 1:
            continue

        consistent_rows = sum(1 for c in col_counts if c == first_row_cnt)
        consistency_ratio = consistent_rows / len(col_counts)

        score = consistency_ratio * (first_row_cnt ** 0.5)
        if cand == sniffer_delim:
            score += 0.5

        if score > best_score:
            best_score = score
            best_delim = cand

    confidence = min(1.0, max(0.4, best_score / 2.0)) if best_score > 0 else 0.5
    return best_delim, confidence

def detect_quotechar(sample_text: str, delimiter: str) -> str:
    """Detects quoting character ('\"' or '\'')."""
    d_count = sample_text.count('"')
    s_count = sample_text.count("'")
    return "'" if s_count > d_count and s_count >= 2 else '"'

def split_and_filter_lines(text: str) -> tuple[list[str], list[int], list[int]]:
    """
    Identifies and strips comment lines (#, //) and blank lines.
    Returns: (kept_lines, comment_line_numbers, blank_line_numbers) 1-indexed.
    """
    kept = []
    comment_rows = []
    blank_rows = []

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            blank_rows.append(idx)
        elif stripped.startswith(('#', '//', '-- ')):
            comment_rows.append(idx)
        else:
            kept.append(raw_line)

    return kept, comment_rows, blank_rows

def clean_and_repair_headers(raw_headers: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Repairs duplicate, empty, or whitespace headers deterministically.
    Never silently changes a header; records every modification.
    """
    seen: dict[str, int] = {}
    clean_headers = []
    modifications = []

    for i, h in enumerate(raw_headers):
        orig = h
        name = str(h).strip() if h is not None else ""
        if not name:
            name = f"unnamed_{i + 1}"
            modifications.append({
                "column_index": i,
                "original": orig,
                "repaired": name,
                "reason": "Empty or whitespace-only header"
            })
        elif name in seen:
            seen[name] += 1
            repaired = f"{name}_{seen[name]}"
            modifications.append({
                "column_index": i,
                "original": orig,
                "repaired": repaired,
                "reason": f"Duplicate header name; appended index {seen[name]}"
            })
            name = repaired
        else:
            seen[name] = 1

        clean_headers.append(name)

    return clean_headers, modifications

def detect_and_remove_trailing_summaries(
    rows: list[list[str]],
    headers: list[str]
) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """
    Detects trailing summary rows (e.g. 'Total', 'Subtotal', 'Average') or footer text at bottom.
    """
    cleaned_rows = list(rows)
    removed_summaries = []

    # Check from bottom up (up to 5 trailing rows)
    while cleaned_rows and len(removed_summaries) < 5:
        last_row = cleaned_rows[-1]
        if not last_row:
            cleaned_rows.pop()
            continue

        first_val = str(last_row[0]).strip().lower() if len(last_row) > 0 else ""
        second_val = str(last_row[1]).strip().lower() if len(last_row) > 1 else ""

        is_summary = any(re.search(pat, first_val) for pat in SUMMARY_ROW_PATTERNS)
        if not is_summary and second_val:
            is_summary = any(re.search(pat, second_val) for pat in SUMMARY_ROW_PATTERNS)

        # Also check if row has mostly blanks except 1-2 summary words
        non_empty = [c for c in last_row if str(c).strip()]
        if len(non_empty) == 1 and any(re.search(pat, str(non_empty[0]).strip().lower()) for pat in SUMMARY_ROW_PATTERNS):
            is_summary = True

        if is_summary:
            row_idx = len(cleaned_rows)
            removed_summaries.append({
                "row_number": row_idx,
                "values": last_row[:5],
                "reason": f"Trailing summary row detected ('{first_val or second_val}')"
            })
            cleaned_rows.pop()
        else:
            break

    return cleaned_rows, removed_summaries

def detect_and_remove_repeated_headers(
    headers: list[str],
    rows: list[list[str]]
) -> tuple[list[list[str]], list[int]]:
    """Detects and removes rows within the data that duplicate the header row."""
    clean_rows = []
    skipped_rows = []
    h_lower = [str(h).strip().lower() for h in headers]

    for idx, r in enumerate(rows, start=2): # 1-indexed, header is row 1
        r_lower = [str(v).strip().lower() for v in r[:len(headers)]]
        if r_lower == h_lower:
            skipped_rows.append(idx)
        else:
            clean_rows.append(r)

    return clean_rows, skipped_rows

def repair_ragged_rows(
    rows: list[list[str]],
    expected_cols: int
) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """Pads short rows with empty strings and trims or logs rows with excess columns."""
    repaired = []
    repairs_log = []

    for idx, r in enumerate(rows, start=2):
        col_count = len(r)
        if col_count == expected_cols:
            repaired.append(r)
        elif col_count < expected_cols:
            padded = r + [""] * (expected_cols - col_count)
            repaired.append(padded)
            repairs_log.append({
                "row_number": idx,
                "original_col_count": col_count,
                "expected_col_count": expected_cols,
                "action": f"Padded {expected_cols - col_count} empty column(s)"
            })
        else:
            # col_count > expected_cols: preserve first expected_cols, join extra into last column
            truncated = r[:expected_cols - 1] + ["; ".join(r[expected_cols - 1:])]
            repaired.append(truncated)
            repairs_log.append({
                "row_number": idx,
                "original_col_count": col_count,
                "expected_col_count": expected_cols,
                "action": f"Merged {col_count - expected_cols + 1} extra trailing field(s)"
            })

    return repaired, repairs_log

def load_csv_safely(
    content: bytes,
    filename: str,
    max_rows: int | None = None
) -> SafeLoadResult:
    """
    Master safe CSV loader.
    - Preserves all raw text values as strings without loss (leading zeros, long IDs, '1E5').
    - Reports encoding, delimiter, quotechar, comments, blank lines, ragged rows, headers.
    - Deterministic and non-destructive.
    """
    if not filename.lower().endswith(".csv") and not filename.lower().endswith(".txt"):
        raise UnsupportedFile("Only .csv or .txt tabular files are supported")

    # 1. Encoding detection
    encoding, enc_conf = detect_encoding(content)
    try:
        decoded_text = content.decode(encoding)
    except Exception as e:
        raise ValidationFailed(f"Failed to decode text using detected encoding '{encoding}': {str(e)}")

    if not decoded_text.strip():
        raise ValidationFailed("CSV file is completely empty.")

    # 2. Comment & Blank line removal
    kept_lines, comment_lines, blank_lines = split_and_filter_lines(decoded_text)
    if not kept_lines:
        raise ValidationFailed("CSV contains only comments or blank lines.")

    sample_block = "\n".join(kept_lines[:60])

    # 3. Delimiter & Quotechar detection
    delimiter, delim_conf = detect_delimiter(sample_block)
    quotechar = detect_quotechar(sample_block, delimiter)

    # 4. Parse rows with standard csv.reader
    try:
        reader = csv.reader(
            io.StringIO("\n".join(kept_lines)),
            delimiter=delimiter,
            quotechar=quotechar,
            skipinitialspace=True
        )
        all_raw_rows = list(reader)
    except Exception as e:
        # Fallback to python csv reader without quotes
        try:
            reader = csv.reader(
                io.StringIO("\n".join(kept_lines)),
                delimiter=delimiter,
                skipinitialspace=True
            )
            all_raw_rows = list(reader)
        except Exception as e2:
            raise ValidationFailed(f"CSV parsing error: {str(e2)}")

    if not all_raw_rows:
        raise ValidationFailed("CSV contains no rows.")

    raw_header = all_raw_rows[0]
    data_rows = all_raw_rows[1:]

    # 5. Header repair (empty, duplicate, whitespace)
    clean_headers, header_repairs = clean_and_repair_headers(raw_header)
    expected_cols = len(clean_headers)

    # 6. Remove repeated header rows inside data
    data_rows, repeated_header_rows = detect_and_remove_repeated_headers(raw_header, data_rows)

    # 7. Remove trailing summary rows
    data_rows, removed_summaries = detect_and_remove_trailing_summaries(data_rows, clean_headers)

    # 8. Ragged rows repair
    data_rows, ragged_repairs = repair_ragged_rows(data_rows, expected_cols)

    # 9. Handle 0-row / header-only file
    if not data_rows:
        empty_df = pd.DataFrame(columns=clean_headers)
        raw_df = empty_df.copy()
        report = {
            "encoding": encoding,
            "delimiter": delimiter,
            "quotechar": quotechar,
            "encoding_confidence": enc_conf,
            "delimiter_confidence": delim_conf,
            "comment_lines_skipped": comment_lines,
            "blank_lines_skipped": blank_lines,
            "header_modifications": header_repairs,
            "repeated_headers_removed": repeated_header_rows,
            "trailing_summaries_removed": removed_summaries,
            "ragged_rows_repaired": ragged_repairs,
            "raw_row_count": 0,
            "final_row_count": 0,
            "column_count": expected_cols,
            "sampled": False,
        }
        return SafeLoadResult(
            df=empty_df,
            raw_df=raw_df,
            encoding=encoding,
            delimiter=delimiter,
            quotechar=quotechar,
            loading_report=report,
            raw_shape=(0, expected_cols),
            warnings=["File contains only headers; 0 data rows."]
        )

    # 10. Construct raw object DataFrame (preserves raw strings without pyarrow string-casting restrictions)
    raw_df = pd.DataFrame(data_rows, columns=clean_headers, dtype=object)
    
    # Store exact raw copy before any sampling or trimming
    raw_shape = raw_df.shape

    # Apply row limits if needed
    sampled = False
    active_df = raw_df
    if max_rows and len(raw_df) > max_rows:
        active_df = raw_df.iloc[:max_rows].copy()
        sampled = True

    warnings = []
    if comment_lines:
        warnings.append(f"Skipped {len(comment_lines)} comment line(s) (lines: {comment_lines[:5]}).")
    if blank_lines:
        warnings.append(f"Skipped {len(blank_lines)} blank line(s).")
    if header_repairs:
        warnings.append(f"Repaired {len(header_repairs)} header column name(s).")
    if repeated_header_rows:
        warnings.append(f"Removed {len(repeated_header_rows)} repeated header row(s) inside dataset.")
    if removed_summaries:
        warnings.append(f"Removed {len(removed_summaries)} trailing summary row(s).")
    if ragged_repairs:
        warnings.append(f"Repaired {len(ragged_repairs)} ragged row(s) with mismatched column counts.")
    if sampled:
        warnings.append(f"Loaded {max_rows} rows out of {raw_shape[0]} total rows for execution safety.")

    report = {
        "encoding": encoding,
        "delimiter": delimiter,
        "quotechar": quotechar,
        "encoding_confidence": enc_conf,
        "delimiter_confidence": delim_conf,
        "comment_lines_skipped": comment_lines,
        "blank_lines_skipped": blank_lines,
        "header_modifications": header_repairs,
        "repeated_headers_removed": repeated_header_rows,
        "trailing_summaries_removed": removed_summaries,
        "ragged_rows_repaired": ragged_repairs,
        "raw_row_count": raw_shape[0],
        "final_row_count": len(active_df),
        "column_count": raw_shape[1],
        "sampled": sampled,
    }

    return SafeLoadResult(
        df=active_df,
        raw_df=raw_df,
        encoding=encoding,
        delimiter=delimiter,
        quotechar=quotechar,
        loading_report=report,
        raw_shape=raw_shape,
        warnings=warnings
    )
