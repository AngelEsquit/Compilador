"""Simbolos que puede guardar un Scope."""
from __future__ import annotations

from dataclasses import dataclass

from compiscript.typesystem.types import Type


@dataclass
class VariableSymbol:
    name: str
    decl_type: Type
    is_const: bool = False
    initialized: bool = False
    line: int = 0
    column: int = 0
