import csv
import io
import re
from pathlib import Path
from typing import Any
import uuid
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError, UnsupportedFile, ValidationFailed
from app.core.logging import logger
from app.db.models.dataset import Dataset
from app.schemas.dataset import ColumnProfile, DatasetOut, DatasetPreview, DatasetProfile
from app.services.data_cleaner import apply_clean_fixes
from app.services.issue_detector import detect_all_dataset_issues
from app.services.safe_loader import detect_delimiter, detect_encoding, load_csv_safely
from app.services.storage import storage_service
from app.services.columnar_engine import columnar_engine
from app.services.calc_cache import calc_cache
from app.services.type_inference import (
    NULL_TOKENS,
    ColumnInferenceResult,
    infer_column_type,
    is_null_token,
    parse_tolerant_number,
    parse_boolean,
    sanitize_for_json,
)

CUSTOM_NA_VALUES = list(NULL_TOKENS)

def validate_csv_content(content: bytes, filename: str) -> tuple[str, str]:
    """Validate that uploaded content is valid text-based CSV and return (decoded_text, encoding)."""
    if not filename.lower().endswith(".csv") and not filename.lower().endswith(".txt"):
        raise UnsupportedFile("Only .csv and .txt files are supported")
    
    # Check for binary null bytes
    if b"\x00" in content[:1024]:
        # Check if UTF-16
        try:
            content[:1024].decode("utf-16")
        except Exception:
            raise UnsupportedFile("Binary file detected. Please upload a valid text CSV.")

    encoding, _ = detect_encoding(content)
    try:
        decoded = content.decode(encoding)
        return decoded, encoding
    except UnicodeDecodeError:
        pass

    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
        try:
            decoded = content.decode(enc)
            return decoded, enc
        except UnicodeDecodeError:
            continue
    raise ValidationFailed("Could not decode CSV text. Please check encoding.")

def parse_csv_to_dataframe(text_or_path: str | Path, limit_rows: int | None = None) -> pd.DataFrame:
    """Robust CSV parser loading via safe loader and preserving data faithfully."""
    max_r = limit_rows or settings.MAX_ROWS
    if isinstance(text_or_path, (str, Path)) and Path(str(text_or_path)).is_file():
        content = Path(str(text_or_path)).read_bytes()
        filename = Path(str(text_or_path)).name
        res = load_csv_safely(content, filename=filename, max_rows=max_r)
        return res.df
    else:
        content = str(text_or_path).encode("utf-8")
        res = load_csv_safely(content, filename="input.csv", max_rows=max_r)
        return res.df

def profile_dataframe(
    df: pd.DataFrame,
    schema_overrides: dict[str, Any] | None = None,
    loading_report: dict[str, Any] | None = None
) -> DatasetProfile:
    """Computes comprehensive deterministic profile and type/role inference."""
    n_rows, n_cols = df.shape
    duplicate_rows = int(df.duplicated().sum()) if n_rows > 0 else 0
    total_cells = n_rows * n_cols if n_rows > 0 and n_cols > 0 else 1
    
    # Vectorized fast total missing count
    isna = df.isna()
    str_cols = df.select_dtypes(include=['object', 'string'])
    tokens_cnt = 0
    for col in str_cols.columns:
        s = str_cols[col].dropna().astype(str).str.strip().str.lower()
        tokens_cnt += int(s.isin(NULL_TOKENS).sum())
    total_missing = int(isna.sum().sum()) + tokens_cnt
    missing_total_pct = round((total_missing / total_cells) * 100.0, 2)

    overrides = schema_overrides or {}
    col_profiles: list[ColumnProfile] = []

    for col in df.columns:
        col_name = str(col)
        series = df[col]
        inf: ColumnInferenceResult = infer_column_type(series, col_name, n_rows)

        # Apply user overrides if present
        if col_name in overrides:
            ov = overrides[col_name]
            if "dtype" in ov:
                inf.legacy_dtype = ov["dtype"]
            if "storage_type" in ov:
                inf.storage_type = ov["storage_type"]
            if "semantic_role" in ov:
                inf.semantic_role = ov["semantic_role"]
            inf.confidence = "high"
            inf.confidence_reason = "Explicit user override applied."
            inf.needs_review = False
            inf.review_question = None

        col_profiles.append(
            ColumnProfile(
                name=col_name,
                dtype=inf.legacy_dtype,
                storage_type=inf.storage_type,
                semantic_role=inf.semantic_role,
                confidence=inf.confidence,
                confidence_reason=inf.confidence_reason,
                null_pct=round(inf.null_count / max(1, n_rows) * 100.0, 2),
                unique=inf.parsed_series.nunique(dropna=True) if hasattr(inf.parsed_series, "nunique") else len(set(inf.parsed_series.dropna())),
                invalid_count=inf.invalid_count,
                invalid_pct=inf.invalid_pct,
                invalid_samples=inf.invalid_samples,
                needs_review=inf.needs_review,
                review_question=inf.review_question,
                stats=inf.stats,
                top_values=inf.top_values,
                flags=inf.flags,
            )
        )

    return DatasetProfile(
        n_rows=n_rows,
        n_cols=n_cols,
        columns=col_profiles,
        duplicate_rows=duplicate_rows,
        missing_total_pct=missing_total_pct,
        loading_report=loading_report,
        schema_overrides=overrides,
    )

def detect_dataset_issues(
    df: pd.DataFrame,
    profile: DatasetProfile,
    loading_report: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Dynamically detects all 12 classes of data issues without redundant re-inference."""
    n_rows, n_cols = df.shape
    inferred_cols: dict[str, ColumnInferenceResult] = {}

    for c in profile.columns:
        series = df[c.name] if c.name in df.columns else pd.Series(dtype=object)
        if c.dtype == "numeric" or c.storage_type in ["integer", "decimal"]:
            parsed_s = pd.to_numeric(series, errors="coerce")
            if parsed_s.notna().sum() < max(1, int(len(series) * 0.5)):
                # Handle European decimal commas or currency symbols
                cleaned_str = series.astype(str).str.replace(r"[^\d.,\-+]", "", regex=True)
                comma_dec = cleaned_str.str.replace(r"\.(?=\d{3}(?:[.,]|$))", "", regex=True).str.replace(",", ".")
                parsed_s = pd.to_numeric(comma_dec, errors="coerce")
        elif c.dtype == "datetime" or c.storage_type in ["date", "datetime"]:
            parsed_s = pd.to_datetime(series, errors="coerce", format="mixed")
        else:
            parsed_s = series

        null_cnt = int(round((c.null_pct or 0.0) * n_rows / 100.0))
        valid_cnt = max(0, n_rows - null_cnt)

        inf = ColumnInferenceResult(
            storage_type=c.storage_type,
            semantic_role=c.semantic_role,
            legacy_dtype=c.dtype,
            confidence=c.confidence,
            confidence_reason=c.confidence_reason,
            parsed_series=parsed_s,
            valid_count=valid_cnt,
            null_count=null_cnt,
            invalid_count=c.invalid_count or 0,
            invalid_pct=c.invalid_pct or 0.0,
            invalid_samples=c.invalid_samples or [],
            detected_format=getattr(c, "detected_format", None),
            needs_review=getattr(c, "needs_review", False),
            review_question=getattr(c, "review_question", None),
            stats=c.stats,
            top_values=c.top_values,
            flags=c.flags or []
        )
        inferred_cols[c.name] = inf

    report = loading_report or getattr(profile, "loading_report", None)
    return detect_all_dataset_issues(df, inferred_cols, loading_report=report)

class DatasetService:
    @staticmethod
    def upload_dataset(
        db: Session,
        user_id: uuid.UUID,
        filename: str,
        content: bytes
    ) -> Dataset:
        # Safe load and analysis
        safe_res = load_csv_safely(content, filename=filename)
        df = safe_res.df

        if df.empty and safe_res.raw_shape[0] == 0 and len(df.columns) == 0:
            raise ValidationFailed("CSV is empty or contains no columns")

        # Save raw content to storage
        storage_path, sha256_hash, size_bytes = storage_service.save_file(content, extension="csv")

        # Convert to columnar Parquet for scalable execution
        parquet_path = Path(storage_path).with_suffix(".parquet")
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception as pe:
            logger.warning(f"Could not dump df to parquet, falling back to streaming converter: {pe}")
            try:
                columnar_engine.csv_to_parquet(
                    Path(storage_path),
                    parquet_path,
                    delimiter=safe_res.delimiter,
                    encoding=safe_res.encoding
                )
            except Exception as e:
                logger.warning(f"Could not convert to Parquet: {e}")

        # Profile dataset with loading report
        profile = profile_dataframe(df, loading_report=safe_res.loading_report)

        dataset = Dataset(
            user_id=user_id,
            filename=filename,
            storage_path=storage_path,
            size_bytes=size_bytes,
            sha256=sha256_hash,
            n_rows=profile.n_rows,
            n_cols=profile.n_cols,
            profile=profile.model_dump(),
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        # Pre-compute and cache dataset issues for instantaneous frontend response
        try:
            issues_res = sanitize_for_json(detect_dataset_issues(df, profile, loading_report=safe_res.loading_report))
            calc_cache.set(dataset.id, sha256_hash, "dataset_issues", {}, issues_res)
        except Exception as ie:
            logger.warning(f"Could not pre-cache dataset issues: {ie}")

        logger.info(f"Uploaded dataset {dataset.id} ({filename}) with {profile.n_rows} rows, {profile.n_cols} cols")
        return dataset

    @staticmethod
    def get_dataset(db: Session, dataset_id: uuid.UUID, user_id: uuid.UUID) -> Dataset:
        stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == user_id)
        dataset = db.scalar(stmt)
        if not dataset:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        return dataset

    @staticmethod
    def list_datasets(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[Dataset]:
        stmt = select(Dataset).where(Dataset.user_id == user_id).order_by(Dataset.created_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def apply_profile_types(df: pd.DataFrame, profile: dict[str, Any] | DatasetProfile | None) -> pd.DataFrame:
        """
        Coerces DataFrame columns to appropriate types based on dataset profile / inferred schema.
        Converts numeric columns to numeric (float/int), dates to datetime, booleans to bool,
        while strictly preserving identifiers and raw text codes as strings.
        """
        if not profile:
            return df

        typed_df = df.copy()
        cols_meta = profile.get("columns", []) if isinstance(profile, dict) else [c.model_dump() for c in profile.columns]
        for c in cols_meta:
            col_name = c.get("name")
            if not col_name or col_name not in typed_df.columns:
                continue
            legacy_dtype = c.get("dtype")
            storage_type = c.get("storage_type")
            semantic_role = c.get("semantic_role")

            # Check if numeric
            is_num = (
                legacy_dtype == "numeric" or
                storage_type in ("integer", "decimal") or
                semantic_role in ("measure", "amount/currency", "count", "percentage", "rate", "duration", "year")
            )
            # Never coerce identifiers (keep codes, zip codes, ids as strings)
            if semantic_role == "identifier":
                is_num = False

            if is_num:
                s = typed_df[col_name].replace(NULL_TOKENS, np.nan)
                try:
                    typed_df[col_name] = pd.to_numeric(s)
                except (ValueError, TypeError):
                    def _parse_val(v):
                        if is_null_token(v):
                            return np.nan
                        val, _ = parse_tolerant_number(str(v))
                        return val if val is not None else np.nan
                    typed_df[col_name] = pd.to_numeric(typed_df[col_name].apply(_parse_val), errors="coerce")

            elif legacy_dtype == "datetime" or storage_type in ("date", "datetime"):
                s = typed_df[col_name].replace(NULL_TOKENS, np.nan)
                try:
                    typed_df[col_name] = pd.to_datetime(s, errors="coerce")
                except Exception:
                    pass

            elif legacy_dtype == "boolean" or storage_type == "boolean":
                def _parse_b(v):
                    if is_null_token(v):
                        return np.nan
                    b = parse_boolean(str(v))
                    return b if b is not None else np.nan
                typed_df[col_name] = typed_df[col_name].apply(_parse_b)

        return typed_df

    @staticmethod
    def load_dataframe(dataset: Dataset, cleaned: bool = False, limit_rows: int | None = None, typed: bool = True) -> pd.DataFrame:
        """Loads stored CSV into a pandas DataFrame (original or cleaned copy)."""
        path = Path(dataset.storage_path)
        if cleaned:
            clean_path = Path(f"{dataset.storage_path}_cleaned.csv")
            if clean_path.is_file():
                path = clean_path
        if not path.is_file():
            raise NotFoundError("Dataset file not found in storage")
        df = parse_csv_to_dataframe(path, limit_rows=limit_rows)
        if typed and dataset.profile:
            df = DatasetService.apply_profile_types(df, dataset.profile)
        return df

    @staticmethod
    def get_preview(dataset: Dataset, rows: int = 20) -> DatasetPreview:
        df = DatasetService.load_dataframe(dataset, limit_rows=rows)
        clean_df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        records = clean_df.to_dict(orient="records")
        return DatasetPreview(
            columns=[str(c) for c in df.columns],
            rows=records,
            total_rows=dataset.n_rows
        )

    @staticmethod
    def get_issues(dataset: Dataset) -> dict[str, Any]:
        """Calculates dynamic issues and data health summary for this dataset with cache support."""
        cached = calc_cache.get(dataset.id, dataset.sha256, "dataset_issues", {})
        if cached is not None:
            return cached
        df = DatasetService.load_dataframe(dataset, typed=False)
        profile = DatasetProfile.model_validate(dataset.profile)
        res = sanitize_for_json(detect_dataset_issues(df, profile))
        calc_cache.set(dataset.id, dataset.sha256, "dataset_issues", {}, res)
        return res

    @staticmethod
    def update_schema(
        db: Session,
        dataset: Dataset,
        overrides: dict[str, Any]
        
    ) -> DatasetProfile:
        """Updates inferred schema with user-provided overrides and re-profiles."""
        df = DatasetService.load_dataframe(dataset, typed=False)
        existing_profile = DatasetProfile.model_validate(dataset.profile)
        loading_report = existing_profile.loading_report

        new_profile = profile_dataframe(df, schema_overrides=overrides, loading_report=loading_report)
        dataset.profile = new_profile.model_dump()
        db.commit()
        db.refresh(dataset)
        logger.info(f"Updated schema overrides for dataset {dataset.id}: {overrides}")
        return new_profile

    @staticmethod
    def clean_dataset(
        db: Session,
        dataset: Dataset,
        selected_fixes: list[str]
    ) -> tuple[str, list[dict[str, Any]]]:

        """Creates a separate cleaned CSV and change log. The original file is never modified."""
        df = DatasetService.load_dataframe(dataset, typed=False)
        profile = DatasetProfile.model_validate(dataset.profile)

        inferred_cols: dict[str, ColumnInferenceResult] = {}
        n_rows = len(df)
        for c in profile.columns:
            series = df[c.name] if c.name in df.columns else pd.Series(dtype=object)
            if c.dtype == "numeric" or c.storage_type in ["integer", "decimal"]:
                parsed_s = pd.to_numeric(series, errors="coerce")
            elif c.dtype == "datetime" or c.storage_type in ["date", "datetime"]:
                parsed_s = pd.to_datetime(series, errors="coerce", format="mixed")
            else:
                parsed_s = series

            inferred_cols[c.name] = ColumnInferenceResult(
                storage_type=c.storage_type,
                semantic_role=c.semantic_role,
                legacy_dtype=c.dtype,
                confidence=c.confidence,
                confidence_reason=c.confidence_reason,
                parsed_series=parsed_s,
                valid_count=n_rows,
                null_count=int(round((c.null_pct or 0.0) * n_rows / 100.0)),
                invalid_count=c.invalid_count or 0,
                invalid_pct=c.invalid_pct or 0.0,
                flags=c.flags or []
            )

        clean_df, changelog = apply_clean_fixes(df, inferred_cols, selected_fixes)

        # Save separate cleaned CSV file and Parquet columnar representation
        cleaned_path = Path(f"{dataset.storage_path}_cleaned.csv")
        clean_df.to_csv(cleaned_path, index=False)

        cleaned_parquet = Path(f"{dataset.storage_path}_cleaned.parquet")
        try:
            clean_df.to_parquet(cleaned_parquet, index=False)
        except Exception as pe:
            logger.warning(f"Could not write cleaned parquet: {pe}")

        # Invalidate computation cache for this dataset
        calc_cache.invalidate(dataset.id)

        logger.info(f"Cleaned dataset {dataset.id} saved to {cleaned_path} with {len(changelog)} steps")
        return str(cleaned_path), sanitize_for_json(changelog)

    @staticmethod
    def get_parquet_path(dataset: Dataset, version: str = "cleaned") -> Path:
        """
        Returns Path to the Parquet columnar file for the dataset.
        Generates Parquet on-the-fly from CSV if not already present.
        """
        raw_csv = Path(dataset.storage_path)
        raw_parquet = raw_csv.with_suffix(".parquet")
        clean_csv = Path(f"{dataset.storage_path}_cleaned.csv")
        clean_parquet = Path(f"{dataset.storage_path}_cleaned.parquet")

        if version in ("cleaned", "default") and clean_csv.exists():
            if not clean_parquet.exists():
                try:
                    df = pd.read_csv(clean_csv, low_memory=False)
                    df.to_parquet(clean_parquet, index=False)
                except Exception as e:
                    logger.warning(f"Failed to generate cleaned parquet: {e}")
            if clean_parquet.exists():
                return clean_parquet

        if not raw_parquet.exists() and raw_csv.exists():
            try:
                columnar_engine.csv_to_parquet(raw_csv, raw_parquet)
            except Exception:
                try:
                    df = pd.read_csv(raw_csv, low_memory=False)
                    df.to_parquet(raw_parquet, index=False)
                except Exception as e:
                    logger.warning(f"Failed to generate raw parquet: {e}")

        return raw_parquet if raw_parquet.exists() else raw_csv

    @staticmethod
    def delete_dataset(db: Session, dataset_id: uuid.UUID, user_id: uuid.UUID) -> None:
        dataset = DatasetService.get_dataset(db, dataset_id, user_id)
        storage_service.delete_file(dataset.storage_path)
        clean_path = Path(f"{dataset.storage_path}_cleaned.csv")
        if clean_path.exists():
            clean_path.unlink()
        raw_parquet = Path(dataset.storage_path).with_suffix(".parquet")
        if raw_parquet.exists():
            raw_parquet.unlink()
        clean_parquet = Path(f"{dataset.storage_path}_cleaned.parquet")
        if clean_parquet.exists():
            clean_parquet.unlink()
        calc_cache.invalidate(dataset.id)
        db.delete(dataset)
        db.commit()
        logger.info(f"Deleted dataset {dataset_id}")

dataset_service = DatasetService()
