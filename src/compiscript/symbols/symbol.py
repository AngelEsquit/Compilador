"""Simbolos que puede guardar un Scope -- version minima del walking
skeleton (ver docs/Compiscript_Diseno_Semantico.md, seccion 5).

Por ahora solo existe VariableSymbol, que cubre tanto `let`/`var` como
`const` (con la bandera is_const). FunctionSymbol y ClassSymbol se
agregan cuando se implementen las reglas de funciones y clases -- no
antes.
"""
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
