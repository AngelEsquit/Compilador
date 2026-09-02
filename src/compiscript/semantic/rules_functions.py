"""Reglas semanticas de funciones y procedimientos (Seccion 2.3).

Valida:
- Nombres de funcion duplicados en el mismo ambito (SEM-FUNC-001)
- Parametros duplicados en una firma (SEM-FUNC-002)
- Aridad de las llamadas (SEM-FUNC-003)
- Tipos de los argumentos (SEM-FUNC-004)
- Tipo de retorno contra la firma declarada (SEM-FUNC-005)
- Invocacion de algo que no es invocable (SEM-FUNC-006)
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser
from compiscript.semantic.type_resolution import resolve_type_node
from compiscript.symbols.scope import Scope
from compiscript.symbols.symbol import FunctionSymbol, ParameterSymbol
from compiscript.typesystem.types import (
    ERROR,
    VOID,
    ErrorType,
    FunctionType,
    Type,
    VoidType,
    is_assignable,
)


def build_function_symbol(
    ctx: CompiscriptParser.FunctionDeclarationContext,
    diag: DiagnosticList,
    *,
    is_method: bool = False,
) -> FunctionSymbol:
    """Construye el FunctionSymbol de una declaracion, sin registrarlo.

    Reporta SEM-FUNC-002 si la firma repite un nombre de parametro.
    """
    ident = ctx.Identifier()
    name = ident.getText()

    return_type = resolve_type_node(ctx.type_()) if ctx.type_() is not None else VOID

    parameters: list[ParameterSymbol] = []
    seen: set[str] = set()
    if ctx.parameters() is not None:
        for param in ctx.parameters().parameter():
            p_ident = param.Identifier()
            p_name = p_ident.getText()
            p_type = resolve_type_node(param.type_()) if param.type_() is not None else ERROR

            if p_name in seen:
                diag.error(
                    "SEM-FUNC-002",
                    f"Parametro duplicado '{p_name}' en la firma de la funcion '{name}'.",
                    p_ident.symbol.line,
                    p_ident.symbol.column,
                )
                continue

            seen.add(p_name)
            parameters.append(
                ParameterSymbol(
                    name=p_name,
                    decl_type=p_type,
                    line=p_ident.symbol.line,
                    column=p_ident.symbol.column,
                )
            )

    return FunctionSymbol(
        name=name,
        decl_type=ERROR,
        parameters=parameters,
        return_type=return_type,
        is_method=is_method,
        line=ident.symbol.line,
        column=ident.symbol.column,
    )


def declare_function(symbol: FunctionSymbol, scope: Scope, diag: DiagnosticList) -> bool:
    """Registra la firma en el ambito. SEM-FUNC-001 si el nombre ya existe."""
    if scope.define(symbol):
        return True

    diag.error(
        "SEM-FUNC-001",
        f"La funcion '{symbol.name}' ya fue declarada en este ambito.",
        symbol.line,
        symbol.column,
    )
    return False


def check_call(
    callee_type: Type,
    callee_name: str,
    arg_types: list[Type],
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Valida una invocacion y devuelve el tipo de retorno de la funcion."""
    if isinstance(callee_type, ErrorType):
        return ERROR

    if not isinstance(callee_type, FunctionType):
        diag.error(
            "SEM-FUNC-006",
            f"La expresion '{callee_name}' no es invocable (es de tipo '{callee_type.name}').",
            line,
            col,
        )
        return ERROR

    expected = callee_type.param_types
    if len(arg_types) != len(expected):
        diag.error(
            "SEM-FUNC-003",
            f"La funcion '{callee_name}' espera {len(expected)} argumento(s) "
            f"pero recibio {len(arg_types)}.",
            line,
            col,
        )
        return callee_type.return_type

    for index, (actual, declared) in enumerate(zip(arg_types, expected), start=1):
        if not is_assignable(actual, declared):
            diag.error(
                "SEM-FUNC-004",
                f"El argumento {index} de '{callee_name}' debe ser de tipo "
                f"'{declared.name}' (se recibio '{actual.name}').",
                line,
                col,
            )

    return callee_type.return_type


def check_return_type(
    function: Optional[FunctionSymbol],
    returned_type: Optional[Type],
    line: int,
    col: int,
    diag: DiagnosticList,
) -> None:
    """Valida `return` contra el tipo declarado en la firma (SEM-FUNC-005)."""
    if function is None:
        return

    declared = function.return_type or VOID

    if returned_type is None:
        # `return;` sin valor: solo valido si la funcion no promete un tipo.
        if not isinstance(declared, (VoidType, ErrorType)):
            diag.error(
                "SEM-FUNC-005",
                f"La funcion '{function.name}' declara retorno '{declared.name}' "
                "pero tiene un 'return' sin valor.",
                line,
                col,
            )
        return

    if isinstance(declared, VoidType) and not isinstance(returned_type, (VoidType, ErrorType)):
        diag.error(
            "SEM-FUNC-005",
            f"La funcion '{function.name}' no declara tipo de retorno "
            f"pero devuelve un valor de tipo '{returned_type.name}'.",
            line,
            col,
        )
        return

    if not is_assignable(returned_type, declared):
        diag.error(
            "SEM-FUNC-005",
            f"La funcion '{function.name}' declara retorno '{declared.name}' "
            f"pero devuelve '{returned_type.name}'.",
            line,
            col,
        )
