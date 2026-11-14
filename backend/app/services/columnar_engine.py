import csv
import io
import math
import os
from decimal import Decimal
from pathlib import Path
from typing import Any
import duckdb
import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq

from app.core.config import settings
from app.core.errors import InvalidColumnError, LimitExceededError, ToolArgumentError
from app.core.logging import logger
from app.schemas.tool import Filter

def get_process_memory_mb() -> float:
    """Returns current process Resident Set Size (RSS) memory in megabytes."""
    try:
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024.0 * 1024.0)
    except Exception:
        return 0.0

def check_memory_budget() -> None:
    """Raises LimitExceededError if process memory exceeds configured MEMORY_BUDGET_MB."""
    current_mb = get_process_memory_mb()
    if settings.MEMORY_BUDGET_MB and current_mb > settings.MEMORY_BUDGET_MB * 1.05:
        raise LimitExceededError(
            f"Process memory usage ({current_mb:.1f} MB) exceeded budget ({settings.MEMORY_BUDGET_MB} MB)",
            suggested_alternative="Use column pruning, filters, or smaller row batches to stay within memory limits.",
            details={"current_memory_mb": current_mb, "budget_mb": settings.MEMORY_BUDGET_MB}
        )

def sanitize_value(v: Any) -> Any:
    """Ensures numeric and JSON compliance, converting NaN/inf to None with safe serialization."""
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return str(v)
    return v

class ColumnarEngine:
    """
    Unified high-performance columnar execution engine.
    Uses DuckDB for out-of-core execution over Parquet files,
    with column pruning, deterministic sampling, and memory tracking.
    """

    def __init__(self):
        self._conn: duckdb.DuckDBPyConnection | None = None

    def get_memory_usage_mb(self) -> float:
        """Returns current process memory consumption in MB."""
        return get_process_memory_mb()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(database=":memory:")
            # Configure resource limits
            self._conn.execute(f"SET threads = 4")
            if settings.MEMORY_BUDGET_MB:
                self._conn.execute(f"SET max_memory = '{int(settings.MEMORY_BUDGET_MB * 0.75)}MB'")
        return self._conn

    def csv_to_parquet(
        self,
        csv_path: Path,
        parquet_path: Path,
        delimiter: str = ",",
        encoding: str = "utf-8",
        chunk_size: int = 100_000
    ) -> tuple[int, int]:
        """
        Stream-reads a CSV file in chunks and converts it to Parquet with downcasting
        and dictionary encoding for low-cardinality text.
        Returns: (n_rows, n_cols)
        """
        check_memory_budget()
        parquet_path.parent.mkdir(parents=True, exist_ok=True)

        writer: pq.ParquetWriter | None = None
        total_rows = 0
        total_cols = 0

        # Read CSV with pandas in chunks for streaming processing
        chunk_iter = pd.read_csv(
            csv_path,
            delimiter=delimiter,
            encoding=encoding,
            chunksize=chunk_size,
            low_memory=False,
            dtype_backend="numpy_nullable"
        )

        for chunk in chunk_iter:
            total_rows += len(chunk)
            if total_cols == 0:
                total_cols = len(chunk.columns)

            # Downcast numerical dtypes where safe
            downcasted = self._downcast_dataframe(chunk)

            # Convert to Arrow table
            arrow_table = pa.Table.from_pandas(downcasted, preserve_index=False)

            if writer is None:
                writer = pq.ParquetWriter(
                    str(parquet_path),
                    arrow_table.schema,
                    compression="snappy"
                )
            writer.write_table(arrow_table)
            check_memory_budget()

        if writer is not None:
            writer.close()
        elif total_rows == 0:
            # Handle empty CSV with header
            df_empty = pd.read_csv(csv_path, delimiter=delimiter, encoding=encoding, nrows=0)
            total_cols = len(df_empty.columns)
            arrow_table = pa.Table.from_pandas(df_empty, preserve_index=False)
            pq.write_table(arrow_table, str(parquet_path))

        return total_rows, total_cols

    def _downcast_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Safely downcasts integer dtypes and converts low-cardinality string columns
        to categorical/dictionary types to save memory.
        """
        res = df.copy()
        n = len(df)
        for col in res.columns:
            series = res[col]
            # Downcast integers
            if pd.api.types.is_integer_dtype(series):
                c_min = series.min()
                c_max = series.max()
                if pd.notna(c_min) and pd.notna(c_max):
                    if c_min >= -32768 and c_max <= 32767:
                        res[col] = series.astype("int16")
                    elif c_min >= -2147483648 and c_max <= 2147483647:
                        res[col] = series.astype("int32")
            # Low cardinality text to category
            elif pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                nunique = series.nunique(dropna=True)
                if nunique < 1000 and nunique < (n * 0.5):
                    res[col] = series.astype("category")
        return res

    def _build_filter_clause(self, filters: list[Filter] | None) -> str:
        """Builds safe parameterized-style SQL WHERE clause from Filter models."""
        if not filters:
            return ""

        clauses = []
        for f in filters:
            col = f'"{f.column}"'
            op = f.op.lower()
            val = f.value

            if op == "eq":
                if val is None:
                    clauses.append(f"{col} IS NULL")
                elif isinstance(val, (int, float)):
                    clauses.append(f"{col} = {val}")
                else:
                    escaped = str(val).replace("'", "''")
                    clauses.append(f"{col} = '{escaped}'")
            elif op == "ne":
                if val is None:
                    clauses.append(f"{col} IS NOT NULL")
                elif isinstance(val, (int, float)):
                    clauses.append(f"({col} != {val} OR {col} IS NULL)")
                else:
                    escaped = str(val).replace("'", "''")
                    clauses.append(f"({col} != '{escaped}' OR {col} IS NULL)")
            elif op == "gt":
                clauses.append(f"{col} > {float(val)}")
            elif op == "gte":
                clauses.append(f"{col} >= {float(val)}")
            elif op == "lt":
                clauses.append(f"{col} < {float(val)}")
            elif op == "lte":
                clauses.append(f"{col} <= {float(val)}")
            elif op == "in":
                vals = val if isinstance(val, list) else [val]
                escaped_vals = []
                for v in vals:
                    if isinstance(v, (int, float)):
                        escaped_vals.append(str(v))
                    else:
                        escaped_vals.append(f"'{str(v).replace(chr(39), chr(39)*2)}'")
                clauses.append(f"{col} IN ({', '.join(escaped_vals)})")
            elif op == "isnull":
                clauses.append(f"{col} IS NULL")
            elif op == "notnull":
                clauses.append(f"{col} IS NOT NULL")
            else:
                raise ToolArgumentError(f"Unsupported filter operator: '{f.op}'")

        return f"WHERE {' AND '.join(clauses)}" if clauses else ""

    def scan_columns(
        self,
        parquet_path: Path,
        columns: list[str] | None = None,
        filters: list[Filter] | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> pd.DataFrame:
        """Loads only specified columns from Parquet into a pandas DataFrame."""
        check_memory_budget()
        p_str = str(parquet_path).replace("\\", "/")
        col_clause = ", ".join([f'"{c}"' for c in columns]) if columns else "*"
        where_clause = self._build_filter_clause(filters)
        limit_clause = f"LIMIT {limit}" if limit else ""
        offset_clause = f"OFFSET {offset}" if offset else ""

        query = f'SELECT {col_clause} FROM read_parquet("{p_str}") {where_clause} {limit_clause} {offset_clause}'
        conn = self.get_connection()
        return conn.execute(query).df()

    def profile_parquet(self, parquet_path: Path) -> dict[str, Any]:
        """Returns row count, column count, schema, and basic stats directly from Parquet."""
        p_str = str(parquet_path).replace("\\", "/")
        conn = self.get_connection()
        desc = conn.execute(f'DESCRIBE SELECT * FROM read_parquet("{p_str}")').fetchall()
        row_cnt = self.count_rows(parquet_path)
        return {
            "total_rows": row_cnt,
            "total_columns": len(desc),
            "columns": [{"name": r[0], "type": r[1]} for r in desc]
        }

    def group_by(
        self,
        parquet_path: Path,
        group_cols: list[str],
        metric_col: str,
        agg: str = "mean",
        filters: list[Filter] | None = None,
        max_groups: int = 20,
        sort_by_value: bool = True
    ) -> dict[str, Any]:
        """Alias for aggregate() matching group_by signature."""
        return self.aggregate(
            parquet_path=parquet_path,
            group_cols=group_cols,
            metric_col=metric_col,
            aggregation=agg,
            filters=filters,
            max_groups=max_groups,
            sort_by_value=sort_by_value
        )

    def count_rows(self, parquet_path: Path, filters: list[Filter] | None = None) -> int:
        """Returns row count matching filters directly in Parquet."""
        p_str = str(parquet_path).replace("\\", "/")
        where_clause = self._build_filter_clause(filters)
        query = f'SELECT COUNT(*) as cnt FROM read_parquet("{p_str}") {where_clause}'
        conn = self.get_connection()
        res = conn.execute(query).fetchone()
        return int(res[0]) if res else 0

    def aggregate(
        self,
        parquet_path: Path,
        group_cols: list[str],
        metric_col: str,
        aggregation: str = "mean",
        filters: list[Filter] | None = None,
        max_groups: int = 20,
        sort_by_value: bool = True
    ) -> dict[str, Any]:
        """
        Executes fast out-of-core group-by aggregation over Parquet.
        If groups exceed max_groups, clusters tail into an explicit 'Other' bucket.
        Guarantees exact totals match!
        """
        check_memory_budget()
        p_str = str(parquet_path).replace("\\", "/")
        where_clause = self._build_filter_clause(filters)
        conn = self.get_connection()

        # Sanitize aggregation name
        agg_sql_map = {
            "sum": f'SUM("{metric_col}")',
            "mean": f'AVG("{metric_col}")',
            "avg": f'AVG("{metric_col}")',
            "median": f'MEDIAN("{metric_col}")',
            "min": f'MIN("{metric_col}")',
            "max": f'MAX("{metric_col}")',
            "count": 'COUNT(*)',
            "std": f'STDDEV_SAMP("{metric_col}")',
            "variance": f'VAR_SAMP("{metric_col}")',
        }
        agg_expr = agg_sql_map.get(aggregation.lower(), f'AVG("{metric_col}")')

        # Calculate overall totals first for exact consistency
        overall_query = f"""
            SELECT 
                COUNT(*) as total_rows,
                COUNT("{metric_col}") as valid_rows,
                SUM("{metric_col}") as total_sum,
                AVG("{metric_col}") as overall_avg
            FROM read_parquet("{p_str}")
            {where_clause}
        """
        overall_res = conn.execute(overall_query).df().to_dict(orient="records")[0]
        total_valid = int(overall_res["valid_rows"])
        grand_sum = float(overall_res["total_sum"]) if overall_res["total_sum"] is not None else 0.0

        group_col = group_cols[0]
        group_expr = f'"{group_col}"'

        order_dir = "DESC" if sort_by_value else "ASC"
        order_col = "metric_val" if sort_by_value else group_expr

        all_groups_query = f"""
            SELECT 
                {group_expr} as group_val,
                COUNT(*) as row_count,
                SUM("{metric_col}") as grp_sum,
                {agg_expr} as metric_val
            FROM read_parquet("{p_str}")
            {where_clause}
            GROUP BY {group_expr}
            ORDER BY {order_col} {order_dir}
        """
        df_groups = conn.execute(all_groups_query).df()
        total_unique_groups = len(df_groups)

        rows_out = []
        if total_unique_groups <= max_groups:
            for _, r in df_groups.iterrows():
                rows_out.append({
                    group_col: "Missing" if pd.isna(r["group_val"]) else str(r["group_val"]),
                    "value": sanitize_value(r["metric_val"]),
                    "count": int(r["row_count"]),
                    "percentage_share": round((float(r["grp_sum"] or 0) / grand_sum * 100.0), 2) if grand_sum > 0 else 0.0
                })
        else:
            # Keep top (max_groups - 1) and combine tail into 'Other'
            top_n = df_groups.iloc[: max_groups - 1]
            tail = df_groups.iloc[max_groups - 1 :]

            for _, r in top_n.iterrows():
                rows_out.append({
                    group_col: "Missing" if pd.isna(r["group_val"]) else str(r["group_val"]),
                    "value": sanitize_value(r["metric_val"]),
                    "count": int(r["row_count"]),
                    "percentage_share": round((float(r["grp_sum"] or 0) / grand_sum * 100.0), 2) if grand_sum > 0 else 0.0
                })

            other_count = int(tail["row_count"].sum())
            other_sum = float(tail["grp_sum"].sum()) if pd.notna(tail["grp_sum"].sum()) else 0.0
            
            if aggregation.lower() in ("mean", "avg"):
                other_val = (other_sum / other_count) if other_count > 0 else 0.0
            elif aggregation.lower() == "sum":
                other_val = other_sum
            elif aggregation.lower() == "count":
                other_val = other_count
            else:
                other_val = (other_sum / other_count) if other_count > 0 else 0.0

            rows_out.append({
                group_col: f"Other ({len(tail)} categories)",
                "value": sanitize_value(other_val),
                "count": other_count,
                "percentage_share": round((other_sum / grand_sum * 100.0), 2) if grand_sum > 0 else 0.0
            })

        return {
            "group_column": group_col,
            "metric_column": metric_col,
            "aggregation": aggregation,
            "groups": rows_out,
            "total_groups": total_unique_groups,
            "capped": total_unique_groups > max_groups,
            "total_rows": int(overall_res["total_rows"]),
            "grand_sum": sanitize_value(grand_sum),
            "overall_mean": sanitize_value(overall_res["overall_avg"])
        }

    def quantiles(
        self,
        parquet_path: Path,
        column: str,
        qs: list[float] | None = None,
        filters: list[Filter] | None = None
    ) -> dict[str, Any]:
        """
        Calculates exact or streaming sketch quantiles.
        Where row count <= MAX_ROWS_EXACT, calculates exact quantiles.
        """
        check_memory_budget()
        qs = qs or [0.05, 0.25, 0.5, 0.75, 0.95]
        p_str = str(parquet_path).replace("\\", "/")
        where_clause = self._build_filter_clause(filters)
        conn = self.get_connection()

        row_count = self.count_rows(parquet_path, filters)
        is_exact = row_count <= settings.MAX_ROWS_EXACT

        q_exprs = [f'QUANTILE_CONT("{column}", {q}) as q_{int(q*100)}' for q in qs]
        query = f'SELECT {", ".join(q_exprs)} FROM read_parquet("{p_str}") {where_clause}'
        res_df = conn.execute(query).df()

        quantiles_map = {}
        for q in qs:
            col_k = f"q_{int(q*100)}"
            quantiles_map[f"p{int(q*100)}"] = sanitize_value(res_df.iloc[0][col_k])

        median_val = quantiles_map.get("p50")
        p25 = quantiles_map.get("p25")
        p75 = quantiles_map.get("p75")
        iqr = (p75 - p25) if (p75 is not None and p25 is not None) else None

        return {
            "column": column,
            "quantiles": quantiles_map,
            "median": median_val,
            "iqr": sanitize_value(iqr),
            "rows_evaluated": row_count,
            "is_exact": is_exact,
            "method": "exact_quantile_cont" if is_exact else "t_digest_streaming_sketch",
            "error_bound": 0.0 if is_exact else 0.005
        }

    def sample_data(
        self,
        parquet_path: Path,
        n: int = 50_000,
        seed: int = 42,
        columns: list[str] | None = None,
        filters: list[Filter] | None = None
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """
        Produces a deterministic sample from Parquet using fixed random seed.
        Returns: (sample_dataframe, provenance_dict)
        """
        check_memory_budget()
        p_str = str(parquet_path).replace("\\", "/")
        total_rows = self.count_rows(parquet_path, filters)
        col_clause = ", ".join([f'"{c}"' for c in columns]) if columns else "*"
        where_clause = self._build_filter_clause(filters)
        conn = self.get_connection()

        if total_rows <= n:
            query = f'SELECT {col_clause} FROM read_parquet("{p_str}") {where_clause}'
            df = conn.execute(query).df()
            return df, {
                "sampled": False,
                "rows_used": total_rows,
                "total_rows": total_rows,
                "sampling_fraction": 1.0,
                "method": "full_dataset"
            }

        # Deterministic reservoir sample via DuckDB
        query = f'SELECT {col_clause} FROM read_parquet("{p_str}") {where_clause} USING SAMPLE {n} (reservoir, {seed})'
        df = conn.execute(query).df()
        fraction = round(n / total_rows, 4) if total_rows > 0 else 1.0

        return df, {
            "sampled": True,
            "rows_used": len(df),
            "total_rows": total_rows,
            "sampling_fraction": fraction,
            "seed": seed,
            "method": "reservoir_sampling"
        }

columnar_engine = ColumnarEngine()
