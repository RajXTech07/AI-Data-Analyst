"""
Hermetic test suite verifying all 7 core data cleaning operations:
1. Deduplication (Exact, Near-duplicates, Repeated IDs)
2. Standardize Missing Values (Sentinels, Universal Tokens, Smart Imputation)
3. Clean Categorical Typos (Fuzzy variant merging, whitespace, casing)
4. Fix Mixed Data Types (Formatted currency/percent, invalid tokens, durations)
5. Handle Outliers & Impossible Values (Negative clipping, scale violations, Tukey capping)
6. Standardize Dates and Times (ISO-8601, chronological inversion swap)
7. Boolean & Scale Standardization (Truthy/falsy normalization, percentage scaling)
"""
import pytest
import pandas as pd
import numpy as np
from app.services.data_cleaner import apply_clean_fixes, preview_fix_operation
from app.services.type_inference import infer_column_type

def test_deduplication():
    # Setup dataframe with exact duplicates, near duplicates, and repeated ID
    df = pd.DataFrame({
        "customer_id": ["ID-101", "ID-101", "ID-102", "ID-103", "ID-104", "ID-104"],
        "name": ["Alice", "Alice", "Bob", "Charlie", "David", "David  "],
        "city": ["New York", "New York", "Chicago", "Boston", "Austin", "austin!"]
    })
    
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    # 1. Exact duplicates
    clean_df, changelog = apply_clean_fixes(df, inferred_cols, ["drop_duplicates"])
    assert len(clean_df) == 5 # 1 exact duplicate dropped
    
    # 2. Near duplicates
    clean_df2, changelog2 = apply_clean_fixes(clean_df, inferred_cols, ["standardize_text_hygiene"])
    assert len(clean_df2) == 4 # David / Austin near-duplicate dropped
    
    # 3. Repeated ID
    clean_df3, changelog3 = apply_clean_fixes(df, inferred_cols, ["flag_id_duplicates-customer_id"])
    assert len(clean_df3) == 4 # Repeated IDs dropped

def test_standardize_missing_values_and_sentinels():
    df = pd.DataFrame({
        "age": [25, -1, 30, 999, 45, None],
        "status": ["Active", "N/A", "?", "Pending", "-", "Active"]
    })
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    clean_df, changelog = apply_clean_fixes(df, inferred_cols, ["missing-age", "missing-status"])
    # Sentinel values should be replaced and imputed
    assert -1 not in clean_df["age"].values
    assert 999 not in clean_df["age"].values
    assert clean_df["age"].isna().sum() == 0
    assert "N/A" not in clean_df["status"].values
    assert "?" not in clean_df["status"].values
    assert "-" not in clean_df["status"].values

def test_clean_categorical_typos():
    df = pd.DataFrame({
        "department": ["Marketing", "marketing", "Marketng", "Sales", " sales ", "Engineering"]
    })
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    clean_df, changelog = apply_clean_fixes(df, inferred_cols, ["cat-fuzzy-department", "standardize_text_hygiene-department"])
    # Whitespace trimmed and casing normalized
    assert " sales " not in clean_df["department"].values
    assert "Sales" in clean_df["department"].values
    # Fuzzy typo "Marketng" merged into "Marketing"
    assert "Marketng" not in clean_df["department"].values

def test_fix_mixed_data_types():
    df = pd.DataFrame({
        "revenue": ["$1,500.50", "USD 2,000", "€3,200", "500k", "INVALID", "400.00"],
        "rate": ["15%", "25.5%", "10.0%", "5%", "corrupt", "30%"],
        "session_duration": ["1h 30m", "45m", "2h", "15m", "N/A", "1h"]
    })
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    clean_df, changelog = apply_clean_fixes(
        df, inferred_cols, 
        ["mixed-type-revenue", "mixed-type-rate", "mixed-type-session_duration"]
    )
    # Revenue should be strictly numeric
    assert pd.api.types.is_numeric_dtype(clean_df["revenue"])
    assert clean_df["revenue"].iloc[0] == 1500.50
    assert clean_df["revenue"].iloc[3] == 500000.0
    
    # Rate should be numeric
    assert pd.api.types.is_numeric_dtype(clean_df["rate"])
    assert clean_df["rate"].iloc[0] == 15.0
    
    # Duration converted to minutes
    assert pd.api.types.is_numeric_dtype(clean_df["session_duration"])
    assert clean_df["session_duration"].iloc[0] == 90.0 # 1h 30m -> 90 mins
    assert clean_df["session_duration"].iloc[1] == 45.0

def test_handle_outliers_and_impossible_values():
    df = pd.DataFrame({
        "item_count": [5, -10, 15, 20, -2, 30],
        "satisfaction_score": [85, 95, 150, -20, 70, 60], # bounded [0, 100]
        "salary": [50000, 52000, 51000, 49000, 53000, 10000000] # Extreme outlier
    })
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    clean_df, changelog = apply_clean_fixes(
        df, inferred_cols,
        ["invalid-neg-item_count", "invalid-scale-satisfaction_score", "cap_outliers-salary"]
    )
    # Impossible negative counts clipped to 0
    assert (clean_df["item_count"] < 0).sum() == 0
    
    # Scale bounds clipped to [0, 100]
    assert (clean_df["satisfaction_score"] < 0).sum() == 0
    assert (clean_df["satisfaction_score"] > 100).sum() == 0
    
    # Extreme outlier capped at upper fence
    assert clean_df["salary"].max() < 10000000

def test_standardize_dates_and_times():
    df = pd.DataFrame({
        "signup_date": ["2023/05/12", "12-05-2023", "2023.05.12", "May 12, 2023"],
        "start_date": ["2023-01-01", "2023-06-01", "2023-12-01", "2023-03-01"],
        "end_date": ["2023-01-10", "2023-05-01", "2023-12-15", "2023-03-15"] # Row 1 has inverted dates (end < start)
    })
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    clean_df, changelog = apply_clean_fixes(
        df, inferred_cols,
        ["standardize_iso_date-signup_date", "chronology_inversion"]
    )
    # Check ISO-8601 format YYYY-MM-DD
    assert all(str(val).startswith("2023-") for val in clean_df["signup_date"])
    
    # Check inverted chronology correction
    # For row 1, original was start=2023-06-01, end=2023-05-01. Now start should be <= end.
    assert clean_df.loc[1, "start_date"] <= clean_df.loc[1, "end_date"]

def test_boolean_and_scale_standardization():
    df = pd.DataFrame({
        "is_subscriber": ["yes", "No", "Y", "N", "1", "0"],
        "discount_pct": [0.05, 0.20, 15.0, 50.0, 0.10, 30.0] # Mixed proportions (0.05 vs 15.0)
    })
    inferred_cols = {c: infer_column_type(df[c], c, len(df)) for c in df.columns}
    
    clean_df, changelog = apply_clean_fixes(
        df, inferred_cols,
        ["bool_standardize-is_subscriber", "scale_standardize-discount_pct"]
    )
    # Truthy/falsy normalized to boolean
    assert clean_df["is_subscriber"].tolist() == [True, False, True, False, True, False]
    
    # Discount percentage standardized to 0-100% scale
    # 0.05 was normalized to 5.0, 0.20 to 20.0
    assert clean_df["discount_pct"].tolist() == [5.0, 20.0, 15.0, 50.0, 10.0, 30.0]
