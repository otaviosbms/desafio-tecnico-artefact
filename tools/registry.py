"""Registro central das ferramentas (preenchido em `ToolsConfig.ready`)."""

from typing import Any

from .contracts import ToolHandler

_tools: dict[str, ToolHandler] = {}


def register_tool(handler: ToolHandler) -> None:
    _tools[handler.name] = handler


def get_tool(name: str) -> ToolHandler | None:
    return _tools.get(name)


def all_tools() -> list[ToolHandler]:
    return list(_tools.values())


def definitions(names: list[str] | None = None) -> list[dict[str, Any]]:
    """Schemas para o function calling; `names` limita às ferramentas liberadas (ordem do registro)."""
    return [tool.definition() for tool in _tools.values() if names is None or tool.name in names]
