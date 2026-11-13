import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from app.context import ToolContext
from app.registry import registry, tool


class AddInput(BaseModel):
    a: int
    b: int


class AddOutput(BaseModel):
    total: int


@tool(
    name="test.add",
    version="1.0.0",
    title="Sumar",
    permissions=["test.add"],
    data_classification="public",
    mcp_description="Suma dos enteros.",
    examples=[{"a": 1, "b": 2}],
)
async def add(params: AddInput, ctx: ToolContext) -> AddOutput:
    return AddOutput(total=params.a + params.b)


def test_tool_registers_validated_spec() -> None:
    spec = registry.get("test.add")

    assert spec.name == "test.add"
    assert spec.version == "1.0.0"
    assert spec.title == "Sumar"
    assert spec.description == "Suma dos enteros."
    assert spec.permissions == ("test.add",)
    assert spec.input_model is AddInput
    assert spec.output_model is AddOutput
    assert spec.examples == ({"a": 1, "b": 2},)
    assert spec.input_schema()["properties"].keys() == {"a", "b"}
    assert spec.output_schema()["properties"].keys() == {"total"}


def test_tool_annotations_reflect_flags() -> None:
    spec = registry.get("test.add")

    assert spec.mcp_annotations() == {
        "title": "Sumar",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def test_registered_handler_is_callable() -> None:
    spec = registry.get("test.add")
    result = asyncio.run(spec.handler(AddInput(a=2, b=3), ToolContext(request_id="req-test")))

    assert result == AddOutput(total=5)


def test_duplicate_tool_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @tool(name="test.add", version="1.0.0", mcp_description="Duplicada.")
        async def duplicate(params: AddInput, ctx: ToolContext) -> AddOutput:
            return AddOutput(total=0)


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [
        ("TestAdd", "1.0.0", "Invalid tool name"),
        ("test", "1.0.0", "Invalid tool name"),
        ("test.add", "1.0", "Invalid SemVer"),
        ("test.add", "1.0.0", "Invalid data_classification"),
    ],
)
def test_invalid_metadata_is_rejected(name: str, version: str, message: str) -> None:
    classification = "secret" if message.startswith("Invalid data_classification") else "public"

    with pytest.raises(ValueError, match=message):

        @tool(
            name=name,
            version=version,
            data_classification=classification,
            mcp_description="Prueba.",
        )
        async def invalid(params: AddInput, ctx: ToolContext) -> AddOutput:
            return AddOutput(total=0)


def test_missing_annotations_are_rejected() -> None:
    with pytest.raises(TypeError, match="input parameter"):

        @tool(name="test.untyped", version="1.0.0", mcp_description="Sin tipos.")
        async def untyped(params: Any, ctx: ToolContext) -> AddOutput:
            return AddOutput(total=0)


def test_unknown_tool_raises_key_error() -> None:
    with pytest.raises(KeyError, match="not registered"):
        registry.get("test.missing")
