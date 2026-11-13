"""Tool registration and discovery.

The code is the source of truth (ADR-004): the decorator validates each tool and
builds the specs used to generate MCP schemas, docs and tests.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar, cast, get_type_hints

from pydantic import BaseModel

from app.context import ToolContext

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CLASSIFICATIONS = frozenset({"public", "business", "personal", "sensitive"})

ParamsT = TypeVar("ParamsT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)
ToolHandler = Callable[[BaseModel, ToolContext], Coroutine[Any, Any, BaseModel]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Everything the server needs to advertise and execute a tool."""

    name: str
    version: str
    title: str
    description: str
    permissions: tuple[str, ...]
    data_classification: str
    read_only: bool
    idempotent: bool
    requires_confirmation: bool
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler
    examples: tuple[dict[str, Any], ...] = ()
    open_world: bool = False

    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    def output_schema(self) -> dict[str, Any]:
        return self.output_model.model_json_schema()

    def mcp_annotations(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "readOnlyHint": self.read_only,
            "destructiveHint": not self.read_only and self.requires_confirmation,
            "idempotentHint": self.idempotent,
            "openWorldHint": self.open_world,
        }


class ToolRegistry:
    """In-memory registry populated at import time by `@tool`."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Tool not registered: {name}") from None

    def all(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools[name] for name in sorted(self._tools))

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


registry = ToolRegistry()


def tool(
    *,
    name: str,
    version: str,
    title: str | None = None,
    permissions: Sequence[str] = (),
    data_classification: str = "public",
    read_only: bool = True,
    idempotent: bool = True,
    requires_confirmation: bool = False,
    mcp_description: str | None = None,
    examples: Sequence[Mapping[str, Any]] = (),
    open_world: bool = False,
) -> Callable[
    [Callable[[ParamsT, ToolContext], Coroutine[Any, Any, ResultT]]],
    Callable[[ParamsT, ToolContext], Coroutine[Any, Any, ResultT]],
]:
    """Register a typed async tool in the global registry."""

    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid tool name: {name!r} (expected 'domain.action')")
    if not _VERSION_RE.fullmatch(version):
        raise ValueError(f"Invalid SemVer version: {version!r}")
    if data_classification not in _CLASSIFICATIONS:
        raise ValueError(f"Invalid data_classification: {data_classification!r}")

    def decorator(
        func: Callable[[ParamsT, ToolContext], Coroutine[Any, Any, ResultT]],
    ) -> Callable[[ParamsT, ToolContext], Coroutine[Any, Any, ResultT]]:
        hints = get_type_hints(func)
        parameters = list(inspect.signature(func).parameters.values())
        if len(parameters) != 2:
            raise TypeError(f"{name} must accept exactly (params, ctx)")

        input_annotation = hints.get(parameters[0].name)
        output_annotation = hints.get("return")
        if not _is_model(input_annotation):
            raise TypeError(f"{name} input parameter must be annotated with a BaseModel")
        if not _is_model(output_annotation):
            raise TypeError(f"{name} return value must be annotated with a BaseModel")

        description = (mcp_description or inspect.getdoc(func) or "").strip()
        if not description:
            raise ValueError(f"{name} requires an MCP description or docstring")

        registry.register(
            ToolSpec(
                name=name,
                version=version,
                title=title or name,
                description=description,
                permissions=tuple(permissions),
                data_classification=data_classification,
                read_only=read_only,
                idempotent=idempotent,
                requires_confirmation=requires_confirmation,
                input_model=cast("type[BaseModel]", input_annotation),
                output_model=cast("type[BaseModel]", output_annotation),
                handler=cast(ToolHandler, func),
                examples=tuple(dict(example) for example in examples),
                open_world=open_world,
            )
        )
        return func

    return decorator


def _is_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)
