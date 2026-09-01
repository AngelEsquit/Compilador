"""Reglas semanticas de tipos (Seccion 2.1).

Valida:
- Operaciones aritmeticas (+, -, *, /, %)
- Operaciones logicas (&&, ||, !)
- Operaciones relacionales (<, <=, >, >=) e igualdad (==, !=)
- Expresion condicional ternaria (?:)
- Compatibilidad en asignaciones
- Proteccion contra reasignacion de constantes
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.typesystem.types import (
    BOOLEAN,
    ERROR,
    INTEGER,
    NULL,
    STRING,
    ArrayType,
    ClassType,
    ErrorType,
    NullType,
    Type,
    is_assignable,
)


def check_arithmetic_binary_op(
    left: Type,
    right: Type,
    op: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Verifica operandos de operaciones aritmeticas (+, -, *, /, %)."""
    if isinstance(left, ErrorType) or isinstance(right, ErrorType):
        return ERROR

    # Concatenacion de cadenas con '+'
    if op == "+" and left == STRING and right == STRING:
        return STRING

    if left == INTEGER and right == INTEGER:
        return INTEGER

    diag.error(
        "SEM-TYPE-001",
        f"Los operandos de la operacion aritmetica '{op}' deben ser de tipo integer (se recibio '{left.name}' y '{right.name}').",
        line,
        col,
    )
    return ERROR


def check_logical_binary_op(
    left: Type,
    right: Type,
    op: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Verifica operandos de operaciones logicas (&&, ||)."""
    if isinstance(left, ErrorType) or isinstance(right, ErrorType):
        return ERROR

    if left == BOOLEAN and right == BOOLEAN:
        return BOOLEAN

    diag.error(
        "SEM-TYPE-002",
        f"Los operandos de la operacion logica '{op}' deben ser de tipo boolean (se recibio '{left.name}' y '{right.name}').",
        line,
        col,
    )
    return ERROR


def check_relational_op(
    left: Type,
    right: Type,
    op: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Verifica comparaciones relacionales (<, <=, >, >=)."""
    if isinstance(left, ErrorType) or isinstance(right, ErrorType):
        return BOOLEAN

    if left == INTEGER and right == INTEGER:
        return BOOLEAN

    diag.error(
        "SEM-TYPE-004",
        f"Los operandos de la comparacion relacional '{op}' deben ser de tipo integer (se recibio '{left.name}' y '{right.name}').",
        line,
        col,
    )
    return BOOLEAN


def check_equality_op(
    left: Type,
    right: Type,
    op: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Verifica comparaciones de igualdad (==, !=)."""
    if isinstance(left, ErrorType) or isinstance(right, ErrorType):
        return BOOLEAN

    # Mismo tipo exacto
    if left == right:
        return BOOLEAN

    # Comparacion de objetos o arreglos con null
    if (isinstance(left, NullType) and (isinstance(right, ClassType) or isinstance(right, ArrayType))) or (
        isinstance(right, NullType) and (isinstance(left, ClassType) or isinstance(left, ArrayType))
    ):
        return BOOLEAN

    diag.error(
        "SEM-TYPE-004",
        f"Comparacion de igualdad '{op}' entre tipos incompatibles ('{left.name}' y '{right.name}').",
        line,
        col,
    )
    return BOOLEAN


def check_unary_op(
    operand: Type,
    op: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Verifica operaciones unarias (- para enteros, ! para booleanos)."""
    if isinstance(operand, ErrorType):
        return ERROR

    if op == "-":
        if operand == INTEGER:
            return INTEGER
        diag.error(
            "SEM-TYPE-001",
            f"El operando del unario '-' debe ser de tipo integer (se recibio '{operand.name}').",
            line,
            col,
        )
        return ERROR

    if op == "!":
        if operand == BOOLEAN:
            return BOOLEAN
        diag.error(
            "SEM-TYPE-002",
            f"El operando del unario '!' debe ser de tipo boolean (se recibio '{operand.name}').",
            line,
            col,
        )
        return ERROR

    return ERROR


def check_ternary_op(
    cond: Type,
    left: Type,
    right: Type,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Verifica operador ternario (cond ? left : right)."""
    if not isinstance(cond, ErrorType) and cond != BOOLEAN:
        diag.error(
            "SEM-FLOW-001",
            f"La condicion del operador ternario debe ser de tipo boolean (se recibio '{cond.name}').",
            line,
            col,
        )

    if isinstance(left, ErrorType) or isinstance(right, ErrorType):
        return ERROR

    if is_assignable(right, left):
        return left
    if is_assignable(left, right):
        return right

    diag.error(
        "SEM-TYPE-003",
        f"Las ramas del operador ternario tienen tipos incompatibles ('{left.name}' y '{right.name}').",
        line,
        col,
    )
    return ERROR


def check_assignment_compatibility(
    target_type: Type,
    value_type: Type,
    is_const: bool,
    line: int,
    col: int,
    diag: DiagnosticList,
    symbol_name: str = "",
) -> None:
    """Verifica si un valor puede asignarse a una variable o propiedad."""
    if is_const:
        diag.error(
            "SEM-TYPE-006",
            f"No se puede reasignar un valor a la constante '{symbol_name}'.",
            line,
            col,
        )
        return

    if not is_assignable(value_type, target_type):
        diag.error(
            "SEM-TYPE-003",
            f"Tipo incompatible en asignacion: no se puede asignar '{value_type.name}' a '{target_type.name}'.",
            line,
            col,
        )
