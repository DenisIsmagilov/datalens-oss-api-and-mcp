from app.tools.base import ToolRegistry
from app.tools.datalens import DATALENS_TOOLS
from app.tools.semantic_tools import SEMANTIC_TOOLS


def build_registry() -> ToolRegistry:
    return ToolRegistry([*DATALENS_TOOLS, *SEMANTIC_TOOLS])
