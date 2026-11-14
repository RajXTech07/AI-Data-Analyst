"""CI Test: Enforce no hardcoded mock data or technical jargon in production source and bundle.

Checks both frontend/src and built frontend/dist (if present) for:
- Banned mock data / fixtures: 'marks', 'department', 'homework', 'exam', 'student',
  '1,200', '184 KB', '1196', '124ms', '480ms', '310ms', 'tool-exec-'
- Banned technical jargon in user-facing text: 'Zero Hallucination', 'Verified Pure Function',
  'Verification Trail', 'Deterministic', 'Tabular Grounding', 'Row height',
  'scipy', 'f_oneway', 'groupby(', 'DataFrame'
"""

import os
import re
import pytest

BANNED_MOCK_STRINGS = [
    "marks",
    "department",
    "homework",
    "exam",
    "student",
    "1,200",
    "184 KB",
    "1196",
    "124ms",
    "480ms",
    "310ms",
    "tool-exec-",
]

BANNED_JARGON_STRINGS = [
    "Zero Hallucination",
    "Verified Pure Function",
    "Verification Trail",
    "Deterministic",
    "Tabular Grounding",
    "Row height",
    "scipy",
    "f_oneway",
    "groupby(",
    "DataFrame",
]

FRONTEND_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
)
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)


def _scan_directory(directory: str, banned_list: list[str], case_sensitive: bool = False):
    violations = []
    if not os.path.exists(directory):
        return violations

    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith((".js", ".jsx", ".ts", ".tsx", ".html", ".css")):
                file_path = os.path.join(root, f)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    for term in banned_list:
                        flags = 0 if case_sensitive else re.IGNORECASE
                        # Avoid matching partial words when scanning for words like 'exam' in 'example'
                        if term.isalpha() and len(term) <= 5:
                            pattern = rf"\b{re.escape(term)}\b"
                        else:
                            pattern = re.escape(term)

                        matches = list(re.finditer(pattern, content, flags))
                        if matches:
                            rel_path = os.path.relpath(file_path, directory)
                            violations.append(
                                f"{rel_path}: '{term}' found {len(matches)} time(s) (line {content[:matches[0].start()].count(chr(10)) + 1})"
                            )
    return violations


def test_no_banned_mock_strings_in_frontend_src():
    """Verify frontend/src does not contain any banned mock data or numbers."""
    violations = _scan_directory(FRONTEND_SRC, BANNED_MOCK_STRINGS, case_sensitive=False)
    assert not violations, (
        f"Found {len(violations)} banned mock string violation(s) in frontend/src:\n"
        + "\n".join(violations)
    )


def test_no_banned_jargon_in_frontend_src():
    """Verify frontend/src does not contain banned technical jargon or exposed code."""
    violations = _scan_directory(FRONTEND_SRC, BANNED_JARGON_STRINGS, case_sensitive=False)
    assert not violations, (
        f"Found {len(violations)} banned jargon violation(s) in frontend/src:\n"
        + "\n".join(violations)
    )


def test_no_banned_strings_in_frontend_dist():
    """Verify production bundle frontend/dist (if built) does not leak banned mock strings."""
    if not os.path.exists(FRONTEND_DIST):
        pytest.skip("frontend/dist does not exist; run npm run build first")

    # In bundled code, inspect for specific mock tokens
    violations = _scan_directory(FRONTEND_DIST, BANNED_MOCK_STRINGS + ["Zero Hallucination", "Verified Pure Function"], case_sensitive=False)
    assert not violations, (
        f"Found {len(violations)} banned violation(s) in frontend/dist:\n"
        + "\n".join(violations)
    )
