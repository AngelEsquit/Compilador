"""Traduccion de nodos `type` de la gramatica a la jerarquia `Type`.

Vive en su propio modulo porque lo necesitan tanto el analizador como la
pasada de pre-declaracion, que corre antes que el.
"""
from __future__ import annotations

from typing import Optional

from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser
from compiscript.typesystem.types import (
    BOOLEAN,
    ERROR,
    INTEGER,
    STRING,
    ArrayType,
    ClassType,
    Type,
)

_PRIMITIVES: dict[str, Type] = {
    "integer": INTEGER,
    "string": STRING,
    "boolean": BOOLEAN,
}


def resolve_type_node(type_ctx: Optional[CompiscriptParser.TypeContext]) -> Type:
    """Traduce un nodo `type` a un Type. Sin anotacion devuelve ERROR."""
    if type_ctx is None:
        return ERROR

    base_ctx = type_ctx.baseType()
    if base_ctx is None:
        return ERROR

    base_name = base_ctx.getText()
    base_type = _PRIMITIVES.get(base_name) or ClassType(base_name)

    dimensions = type_ctx.getText().count("[]")
    if dimensions > 0:
        return ArrayType(base_type, dimensions)
    return base_type
