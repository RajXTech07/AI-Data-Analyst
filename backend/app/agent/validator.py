import re
from typing import Any, Literal
from uuid import UUID
from app.core.logging import logger
from app.schemas.finding import FindingDraft, StatEvidence

def extract_numbers_from_text(text: str) -> list[float]:
    """Extracts numeric values (integers, floats, percentages) from a string."""
    # Match numbers like 42, 3.14, -0.05, 85%, etc.
    matches = re.findall(r"[-+]?\d*\.?\d+", text)
    numbers = []
    for m in matches:
        try:
            val = float(m)
            # Filter out standalone zero/one if they are likely articles or list numbers
            numbers.append(val)
        except ValueError:
            continue
    return numbers

def collect_numbers_from_data(data: Any) -> list[float]:
    """Recursively collects all numeric values from tool execution result structures."""
    nums = []
    if isinstance(data, dict):
        for v in data.values():
            nums.extend(collect_numbers_from_data(v))
    elif isinstance(data, list):
        for item in data:
            nums.extend(collect_numbers_from_data(item))
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        nums.append(float(data))
    return nums

class GroundingValidator:
    @staticmethod
    def verify_grounding(
        finding: FindingDraft,
        tool_results_by_id: dict[UUID, dict[str, Any]],
        tolerance: float = 0.05
    ) -> tuple[bool, list[str]]:
        """
        Verifies that numeric claims in finding text exist in the cited tool outputs within tolerance.
        Returns: (is_grounded, warnings)
        """
        # Collect ground truth numbers from all cited execution IDs
        allowed_numbers: list[float] = []
        for eid in finding.evidence_execution_ids:
            t_res = tool_results_by_id.get(eid)
            if t_res and t_res.get("data"):
                allowed_numbers.extend(collect_numbers_from_data(t_res["data"]))

        # Extract claims from text
        text_numbers = extract_numbers_from_text(f"{finding.observation} {finding.title}")
        warnings: list[str] = []
        unmatched: list[float] = []

        for num in text_numbers:
            # Check if num matches any allowed number within relative or absolute tolerance
            matched = any(
                abs(num - ref) <= max(tolerance, abs(ref) * 0.02)
                for ref in allowed_numbers
            )
            if not matched:
                unmatched.append(num)

        if unmatched:
            # Deduplicate unmatched numbers for clean warning
            unique_unmatched = list(set(unmatched))[:5]
            warn = f"Unverified numbers in finding: {unique_unmatched}. Verify tool audit records."
            warnings.append(warn)
            logger.warning(f"Finding '{finding.title}' has ungrounded numbers: {unique_unmatched}")
            return False, warnings

        return True, []

    @staticmethod
    def verify_text_grounding(
        text: str,
        tool_results: list[dict[str, Any]],
        tolerance: float = 0.05
    ) -> tuple[bool, list[float]]:
        """Verifies numbers extracted from text against a list of tool result dictionaries."""
        allowed_numbers: list[float] = []
        for res in tool_results:
            if isinstance(res, dict):
                allowed_numbers.extend(collect_numbers_from_data(res))

        text_numbers = extract_numbers_from_text(text)
        unmatched: list[float] = []
        for num in text_numbers:
            # Common list indices or rank numbers (e.g. 1st, 2nd) are ignored
            if num in [1.0, 2.0, 3.0, 4.0, 5.0]:
                continue
            matched = any(
                abs(num - ref) <= max(tolerance, abs(ref) * 0.02)
                for ref in allowed_numbers
            )
            if not matched:
                unmatched.append(num)
        return len(unmatched) == 0, unmatched

    @staticmethod
    def compute_confidence(
        hypothesis_status: str,
        stat_evidence: StatEvidence | None,
        warnings: list[str]
    ) -> Literal["low", "medium", "high"]:
        """Computes statistical confidence score in code based on sample size and p-values."""
        if hypothesis_status in ["rejected", "inconclusive"]:
            return "low"

        if not stat_evidence or stat_evidence.p_value is None:
            # Descriptive finding without formal p-value
            if warnings:
                return "low"
            return "medium"

        p_val = stat_evidence.p_value
        n = stat_evidence.n or 0

        if p_val < 0.01 and n >= 30 and not warnings:
            return "high"
        elif p_val < 0.05 and n >= 15:
            return "medium"
        else:
            return "low"

validator = GroundingValidator()
