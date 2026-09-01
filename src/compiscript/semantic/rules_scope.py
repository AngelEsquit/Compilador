"""Reglas semanticas de ambito (Seccion 2.2).

Valida:
- Variables y constantes no declaradas (SEM-SCOPE-001)
- Prohibicion de redeclaracion en el mismo ambito (SEM-SCOPE-002)
- Inicializacion obligatoria de constantes (SEM-TYPE-005)
- Resolucion adecuada en ambitos anidados y permisos de shadowing
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.symbols.scope import Scope
from compiscript.symbols.symbol import ConstSymbol, Symbol, VariableSymbol
from compiscript.typesystem.types import ERROR, Type


def declare_variable(
    name: str,
    decl_type: Type,
    *,
    is_const: bool,
    initialized: bool,
    line: int,
    col: int,
    scope: Scope,
    diag: DiagnosticList,
) -> Optional[Symbol]:
    """Registra una variable o constante en el ambito actual."""
    if is_const and not initialized:
        diag.error(
            "SEM-TYPE-005",
            f"La constante '{name}' debe ser inicializada en su declaracion.",
            line,
            col,
        )

    if is_const:
        sym: Symbol = ConstSymbol(
            name=name,
            decl_type=decl_type,
            initialized=initialized,
            line=line,
            column=col,
        )
    else:
        sym = VariableSymbol(
            name=name,
            decl_type=decl_type,
            is_const=False,
            initialized=initialized,
            line=line,
            column=col,
        )

    if not scope.define(sym):
        diag.error(
            "SEM-SCOPE-002",
            f"El identificador '{name}' ya fue declarado en este ambito.",
            line,
            col,
        )
        return None

    return sym


def resolve_variable(
    name: str,
    line: int,
    col: int,
    scope: Scope,
    diag: DiagnosticList,
) -> tuple[Optional[Symbol], Type]:
    """Resuelve un identificador en el ambito lexico actual o sus padres."""
    symbol = scope.resolve(name)
    if symbol is None:
        diag.error(
            "SEM-SCOPE-001",
            f"Uso de variable no declarada: '{name}'.",
            line,
            col,
        )
        return None, ERROR

    return symbol, symbol.decl_type
