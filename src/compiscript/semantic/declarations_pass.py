"""Pasada 1: pre-declara firmas de funciones y clases antes de validar cuerpos.

Sin esta pasada, una funcion que llama a otra definida mas abajo en el
archivo fallaria por "no declarada". Solo registra firmas: no baja a los
cuerpos, eso es trabajo del SemanticAnalyzer.
"""
from __future__ import annotations

from compiscript.diagnostics import DiagnosticList
from compiscript.semantic.rules_functions import build_function_symbol, declare_function
from compiscript.symbols.scope import Scope
from compiscript.symbols.symbol import ClassSymbol
from compiscript.typesystem.types import ClassType


def _function_declaration_of(node):
    """Devuelve la functionDeclaration de un statement o classMember, si la tiene."""
    getter = getattr(node, "functionDeclaration", None)
    return getter() if getter is not None else None


def _class_declaration_of(node):
    """Devuelve la classDeclaration de un statement, si la tiene."""
    getter = getattr(node, "classDeclaration", None)
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


def predeclare_classes(nodes, scope: Scope, diag: DiagnosticList) -> dict:
    """Registra en `scope` el nombre y superclase de cada clase declarada en `nodes`.

    Al igual que `predeclare_functions`, solo registra la firma (nombre y
    superclase) antes de bajar a los cuerpos: esto permite que una clase
    herede de otra declarada mas abajo en el mismo ambito y que los metodos
    referencien libremente cualquier clase del archivo. Los miembros
    (campos y metodos) se completan cuando el analizador visita el cuerpo.
    Devuelve el mapa nodo -> ClassSymbol.
    """
    predeclared: dict = {}

    for node in nodes:
        class_ctx = _class_declaration_of(node)
        if class_ctx is None:
            continue

        idents = class_ctx.Identifier()
        class_name = idents[0].getText()
        line, col = idents[0].symbol.line, idents[0].symbol.column
        super_name = idents[1].getText() if len(idents) > 1 else None

        class_sym = ClassSymbol(
            name=class_name,
            decl_type=ClassType(class_name),
            superclass_name=super_name,
            line=line,
            column=col,
        )

        if not scope.define(class_sym):
            diag.error(
                "SEM-SCOPE-002",
                f"La clase '{class_name}' ya fue declarada en este ambito.",
                line,
                col,
            )
            continue

        predeclared[class_ctx] = class_sym

    return predeclared
