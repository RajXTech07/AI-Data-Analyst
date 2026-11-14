import math
from typing import Any
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

from app.core.errors import InvalidColumnError, UnsupportedChartError
from app.schemas.anomaly import (
    AnomalyFlaggedRecord,
    AnomalyImpactComparison,
    AnomalyImpactMetric,
    AnomalyWorkbenchResponse,
)
from app.services.columnar_engine import sanitize_value

class AnomalyEngine:
    """
    Comprehensive anomaly detection and impact assessment engine.
    Supports 9 statistical, temporal, and ML methods with domain classification
    and before/after impact tracking.
    """

    @staticmethod
    def detect_anomalies(
        df: pd.DataFrame,
        column: str,
        method: str = "iqr",
        threshold: float | None = None,
        contamination: float = 0.05,
        dataset_id: str = "default"
    ) -> AnomalyWorkbenchResponse:
        if column not in df.columns:
            raise InvalidColumnError(f"Column '{column}' not found in dataset.")

        s = df[column].dropna()
        n_eval = len(s)
        if n_eval < 5:
            raise UnsupportedChartError(f"Need at least 5 valid observations in '{column}' for anomaly detection.")

        method = method.lower()
        flagged_indices: list[int] = []
        scores: dict[int, float] = {}
        resolved_threshold = threshold
        params: dict[str, Any] = {"method": method, "contamination": contamination}

        # 1. IQR (Tukey's Fences)
        if method == "iqr":
            mult = threshold if threshold is not None else 1.5
            resolved_threshold = mult
            params["multiplier"] = mult
            q25 = float(s.quantile(0.25))
            q75 = float(s.quantile(0.75))
            iqr = q75 - q25
            lb = q25 - (mult * iqr)
            ub = q75 + (mult * iqr)

            mask = (s < lb) | (s > ub)
            flagged_indices = list(s[mask].index)
            for idx in flagged_indices:
                val = float(s.loc[idx])
                dist = abs(val - s.median()) / (iqr if iqr > 0 else 1.0)
                scores[idx] = round(dist, 3)

        # 2. Z-Score (Parametric)
        elif method == "zscore":
            z_cut = threshold if threshold is not None else 3.0
            resolved_threshold = z_cut
            params["z_cutoff"] = z_cut
            mean_val = float(s.mean())
            std_val = float(s.std(ddof=1)) if n_eval > 1 else 1.0
            if std_val == 0.0:
                std_val = 1.0

            z_scores = ((s - mean_val) / std_val).abs()
            flagged_indices = list(s[z_scores > z_cut].index)
            for idx in flagged_indices:
                scores[idx] = round(float(z_scores.loc[idx]), 3)

        # 3. MAD (Median Absolute Deviation)
        elif method == "mad":
            mad_thresh = threshold if threshold is not None else 3.5
            resolved_threshold = mad_thresh
            params["mad_threshold"] = mad_thresh
            median_val = float(s.median())
            raw_mad = float(np.median(np.abs(s.to_numpy() - median_val)))
            mad = raw_mad if raw_mad > 0 else (float(s.std(ddof=1)) * 0.6745 or 1.0)

            mod_z = (0.6745 * (s - median_val).abs()) / mad
            flagged_indices = list(s[mod_z > mad_thresh].index)
            for idx in flagged_indices:
                scores[idx] = round(float(mod_z.loc[idx]), 3)

        # 4. Percentile Bounds
        elif method == "percentile":
            p_low = 1.0
            p_high = 99.0
            params["lower_percentile"] = p_low
            params["upper_percentile"] = p_high
            lb = float(np.percentile(s, p_low))
            ub = float(np.percentile(s, p_high))
            resolved_threshold = ub

            mask = (s < lb) | (s > ub)
            flagged_indices = list(s[mask].index)
            for idx in flagged_indices:
                scores[idx] = 1.0

        # 5. Rolling Window (Time Series)
        elif method == "rolling":
            window = 7
            params["window_size"] = window
            k_sig = threshold if threshold is not None else 2.5
            resolved_threshold = k_sig
            params["k_sigma"] = k_sig

            roll_mean = s.rolling(window, min_periods=3, center=True).mean()
            roll_std = s.rolling(window, min_periods=3, center=True).std().fillna(s.std())
            roll_std = roll_std.replace(0.0, s.std() if s.std() > 0 else 1.0)

            dev = ((s - roll_mean).abs()) / roll_std
            flagged_indices = list(s[dev > k_sig].index)
            for idx in flagged_indices:
                scores[idx] = round(float(dev.loc[idx]), 3)

        # 6. Seasonal Residuals
        elif method == "seasonal":
            period = 7 if n_eval >= 28 else 4
            params["assumed_period"] = period
            trend_comp = s.rolling(period, center=True, min_periods=2).mean()
            detrended = s - trend_comp
            res_std = detrended.std() if detrended.std() > 0 else 1.0
            cut = threshold if threshold is not None else 2.5
            resolved_threshold = cut

            seasonal_z = (detrended.abs()) / res_std
            flagged_indices = list(s[seasonal_z > cut].index)
            for idx in flagged_indices:
                scores[idx] = round(float(seasonal_z.loc[idx]), 3)

        # 7. Isolation Forest (Multi-column / bounded sample)
        elif method == "isolation_forest":
            sample_df = df.select_dtypes(include=[np.number]).dropna()
            if sample_df.empty:
                sample_df = pd.DataFrame({column: s})
            n_sub = min(len(sample_df), 10_000)
            sub = sample_df.sample(n=n_sub, random_state=42)

            contam = max(0.005, min(0.20, contamination))
            params["contamination"] = contam
            iso = IsolationForest(contamination=contam, random_state=42, n_estimators=100)
            preds = iso.fit_predict(sub)
            iso_scores = -iso.score_samples(sub)

            flagged_indices = list(sub.iloc[np.where(preds == -1)[0]].index)
            for idx in flagged_indices:
                scores[idx] = round(float(iso_scores[sub.index.get_loc(idx)]), 3)

        # 8. Local Outlier Factor (LOF)
        elif method == "lof":
            sample_df = df.select_dtypes(include=[np.number]).dropna()
            if sample_df.empty:
                sample_df = pd.DataFrame({column: s})
            n_sub = min(len(sample_df), 5_000)
            sub = sample_df.sample(n=n_sub, random_state=42)

            contam = max(0.01, min(0.15, contamination))
            params["contamination"] = contam
            k_neighbors = min(20, len(sub) - 1)
            lof = LocalOutlierFactor(n_neighbors=k_neighbors, contamination=contam)
            preds = lof.fit_predict(sub)
            neg_factor = -lof.negative_outlier_factor_

            flagged_indices = list(sub.iloc[np.where(preds == -1)[0]].index)
            for idx in flagged_indices:
                scores[idx] = round(float(neg_factor[sub.index.get_loc(idx)]), 3)

        # 9. Rule-Based (Impossible Domain Errors)
        elif method == "rule_based":
            col_l = column.lower()
            mask = pd.Series(False, index=s.index)
            if "age" in col_l:
                mask = (s < 0) | (s > 130)
            elif any(k in col_l for k in ["price", "cost", "salary", "revenue", "income"]):
                mask = s < 0
            elif any(k in col_l for k in ["pct", "percent", "percentage", "rate"]):
                mask = (s < 0) | (s > 100)
            else:
                # Fallback to extreme IQR 3.0
                q25 = float(s.quantile(0.25))
                q75 = float(s.quantile(0.75))
                iqr = q75 - q25
                mask = (s < q25 - 3.0 * iqr) | (s > q75 + 3.0 * iqr)

            flagged_indices = list(s[mask].index)
            for idx in flagged_indices:
                scores[idx] = 10.0

        # Classify each flagged record
        flagged_records: list[AnomalyFlaggedRecord] = []
        for idx in flagged_indices[:100]:  # Limit preview to 100
            val = float(s.loc[idx])
            score = scores.get(idx, 1.0)
            cls, conf, reason = AnomalyEngine._classify_record(column, val, s, method)
            flagged_records.append(
                AnomalyFlaggedRecord(
                    row_index=int(idx),
                    value=sanitize_value(val),
                    score=score,
                    classification=cls,
                    confidence=conf,
                    reason=reason
                )
            )

        # Before & After Impact Analysis
        impact = AnomalyEngine._compute_impact(df, column, flagged_indices)

        n_flagged = len(flagged_indices)
        pct_flagged = round((n_flagged / n_eval * 100.0) if n_eval > 0 else 0.0, 2)

        explain = {
            "method": method,
            "evaluated_rows": n_eval,
            "anomalies_detected": n_flagged,
            "impact_summary": impact.summary
        }

        return AnomalyWorkbenchResponse(
            dataset_id=dataset_id,
            column=column,
            method=method,
            threshold=resolved_threshold,
            parameters=params,
            total_evaluated=n_eval,
            flagged_count=n_flagged,
            flagged_percentage=pct_flagged,
            flagged_records=flagged_records,
            impact_comparison=impact,
            explain=explain
        )

    @staticmethod
    def _classify_record(
        column: str,
        value: float,
        series: pd.Series,
        method: str
    ) -> tuple[str, str, str]:
        col_l = column.lower()

        # Check for physically impossible data errors
        if "age" in col_l and (value < 0 or value > 130):
            return "impossible (data error)", "High", f"Age value {value} is outside valid human lifespan (0-130)."
        if any(k in col_l for k in ["price", "cost", "salary", "revenue"]) and value < 0:
            return "impossible (data error)", "High", f"Financial measure {value} cannot be negative."
        if any(k in col_l for k in ["pct", "percent", "percentage"]) and (value < 0 or value > 100):
            return "impossible (data error)", "High", f"Percentage value {value}% violates bounded 0-100 scale."

        # Check for contextual anomalies
        if method in ("rolling", "seasonal"):
            return "contextual anomaly (unusual for its group/time)", "Medium", f"Value {value:.2f} deviates significantly from its local time window/seasonality."

        # Statistical outlier
        std_val = float(series.std()) if series.std() > 0 else 1.0
        z = abs(value - float(series.mean())) / std_val
        confidence = "High" if z > 4.0 else "Medium"
        return "statistical outlier (may be real)", confidence, f"Value {value:.2f} is {z:.1f} standard deviations from the dataset mean."

    @staticmethod
    def _compute_impact(
        df: pd.DataFrame,
        column: str,
        flagged_indices: list[int]
    ) -> AnomalyImpactComparison:
        s_base = df[column].dropna()
        s_clean = s_base.drop(index=[idx for idx in flagged_indices if idx in s_base.index])

        metrics: list[AnomalyImpactMetric] = []
        substantive = False

        # Mean
        base_mean = float(s_base.mean()) if len(s_base) > 0 else None
        clean_mean = float(s_clean.mean()) if len(s_clean) > 0 else None
        if base_mean is not None and clean_mean is not None:
            abs_chg = clean_mean - base_mean
            pct_chg = round((abs_chg / abs(base_mean) * 100.0) if base_mean != 0 else 0.0, 2)
            if abs(pct_chg) >= 5.0:
                substantive = True
            metrics.append(AnomalyImpactMetric(
                metric="Mean",
                baseline=round(base_mean, 4),
                scenario_without_anomalies=round(clean_mean, 4),
                absolute_change=round(abs_chg, 4),
                percentage_change=pct_chg
            ))

        # Median
        base_med = float(s_base.median()) if len(s_base) > 0 else None
        clean_med = float(s_clean.median()) if len(s_clean) > 0 else None
        if base_med is not None and clean_med is not None:
            abs_chg = clean_med - base_med
            pct_chg = round((abs_chg / abs(base_med) * 100.0) if base_med != 0 else 0.0, 2)
            metrics.append(AnomalyImpactMetric(
                metric="Median",
                baseline=round(base_med, 4),
                scenario_without_anomalies=round(clean_med, 4),
                absolute_change=round(abs_chg, 4),
                percentage_change=pct_chg
            ))

        # Std Dev
        base_std = float(s_base.std(ddof=1)) if len(s_base) > 1 else None
        clean_std = float(s_clean.std(ddof=1)) if len(s_clean) > 1 else None
        if base_std is not None and clean_std is not None:
            abs_chg = clean_std - base_std
            pct_chg = round((abs_chg / abs(base_std) * 100.0) if base_std != 0 else 0.0, 2)
            if abs(pct_chg) >= 15.0:
                substantive = True
            metrics.append(AnomalyImpactMetric(
                metric="Standard Deviation",
                baseline=round(base_std, 4),
                scenario_without_anomalies=round(clean_std, 4),
                absolute_change=round(abs_chg, 4),
                percentage_change=pct_chg
            ))

        n_diff = len(s_base) - len(s_clean)
        summary = (
            f"Excluding {n_diff} anomaly record(s) moves the mean from {base_mean:.2f} to {clean_mean:.2f} "
            f"({metrics[0].percentage_change:+.1f}%), materially stabilizing variance."
            if substantive and metrics
            else f"Excluding {n_diff} anomaly record(s) causes minor shifts (< 5%) in central tendency."
        )

        return AnomalyImpactComparison(
            column=column,
            metrics=metrics,
            substantive_impact=substantive,
            summary=summary
        )

anomaly_engine = AnomalyEngine()
