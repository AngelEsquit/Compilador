"""Pasada 1: pre-declara firmas de funciones y clases antes de validar cuerpos.

Sin esta pasada, una funcion que llama a otra definida mas abajo en el
archivo fallaria por "no declarada". Solo registra firmas: no baja a los
cuerpos, eso es trabajo del SemanticAnalyzer.
"""
from __future__ import annotations

from compiscript.diagnostics import DiagnosticList
from compiscript.semantic.rules_functions import build_function_symbol, declare_function
from compiscript.symbols.scope import Scope


def _function_declaration_of(node):
    """Devuelve la functionDeclaration de un statement o classMember, si la tiene."""
    getter = getattr(node, "functionDeclaration", None)
    return getter() if getter is not None else None


def predeclare_functions(
    nodes,
    scope: Scope,
    diag: DiagnosticList,
    *,
    are_methods: bool = False,
) -> dict:
    """Registra en `scope` la firma de cada funcion declarada en `nodes`.

    Devuelve el mapa nodo -> FunctionSymbol. Se indexa por el nodo y no por el
    nombre para que una funcion duplicada conserve su propia firma: asi su
    cuerpo se analiza con sus propios parametros y no arrastra errores de
    ambito ajenos.
    """
    predeclared: dict = {}

    for node in nodes:
        func_ctx = _function_declaration_of(node)
        if func_ctx is None:
            continue

        symbol = build_function_symbol(func_ctx, diag, is_method=are_methods)
        declare_function(symbol, scope, diag)
        predeclared[func_ctx] = symbol

    return predeclared
