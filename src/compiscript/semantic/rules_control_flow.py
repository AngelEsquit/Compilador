"""Reglas semanticas de control de flujo (Seccion 2.4).

Valida:
- Expresiones condicionales de tipo boolean en if, while, do-while, for (SEM-FLOW-001)
- Uso de break y continue exclusivamente dentro de bucles (SEM-FLOW-002)
- Uso de return exclusivamente dentro del cuerpo de funciones (SEM-FLOW-003)
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.symbols.scope import Scope
from compiscript.typesystem.types import BOOLEAN, ErrorType, Type


def check_condition(
    cond_type: Type,
    stmt_name: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> None:
    """Verifica que la condicion de una sentencia de control sea booleana."""
    if isinstance(cond_type, ErrorType):
        return

    if cond_type != BOOLEAN:
        diag.error(
            "SEM-FLOW-001",
            f"La condicion de la sentencia '{stmt_name}' debe ser de tipo boolean (se recibio '{cond_type.name}').",
            line,
            col,
        )


def check_break_continue(
    scope: Scope,
    keyword: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> None:
    """Verifica que break o continue solo se utilicen dentro de bucles."""
    if not scope.is_inside_loop():
        diag.error(
            "SEM-FLOW-002",
            f"La sentencia '{keyword}' solo se permite dentro del cuerpo de un bucle (while, do-while, for, foreach).",
            line,
            col,
        )


def check_return_in_function(
    scope: Scope,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Optional[Scope]:
    """Verifica que return solo se utilice dentro de una funcion o metodo."""
    func_scope = scope.get_enclosing_function()
    if func_scope is None:
        diag.error(
            "SEM-FLOW-003",
            "La sentencia 'return' solo se permite dentro del cuerpo de una funcion o metodo.",
            line,
            col,
        )
        return None
    return func_scope
