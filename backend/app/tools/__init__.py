# Import all tools to ensure @tool decorators register in REGISTRY
import app.tools.profile  # noqa: F401
import app.tools.missing  # noqa: F401
import app.tools.duplicates  # noqa: F401
import app.tools.statistics  # noqa: F401
import app.tools.groupby  # noqa: F401
import app.tools.correlation  # noqa: F401
import app.tools.outliers  # noqa: F401
import app.tools.trend  # noqa: F401
import app.tools.tests  # noqa: F401
import app.tools.charts  # noqa: F401

from app.tools.registry import REGISTRY, get_tool, list_tools, llm_tool_schemas, run_tool

__all__ = [
    "REGISTRY",
    "get_tool",
    "list_tools",
    "llm_tool_schemas",
    "run_tool",
]
