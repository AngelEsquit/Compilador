"""Reglas semanticas de arreglos y listas (Seccion 2.6).

Valida:
- Indice de acceso de tipo integer (SEM-ARR-001)
- Homogeneidad de los elementos de un literal (SEM-ARR-002)
- foreach solo sobre arreglos (SEM-ARR-003)
- Indexacion solo sobre arreglos (SEM-ARR-004)
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.typesystem.types import (
    ERROR,
    INTEGER,
    ArrayType,
    ClassType,
    ErrorType,
    Type,
    common_superclass,
)


def element_type_of(array_type: ArrayType) -> Type:
    """Tipo que resulta de quitarle una dimension al arreglo."""
    if array_type.dimensions <= 1:
        return array_type.element_type
    return ArrayType(array_type.element_type, array_type.dimensions - 1)


def _unify(first: Type, second: Type) -> Optional[Type]:
    """Tipo comun de dos elementos de un literal, o None si no existe.

    Tipos iguales se unifican en si mismos; instancias de clases emparentadas, en su ancestro
    comun; arreglos de igual dimension, segun sus elementos (una matriz de Animal puede mezclar
    filas de Perro y de Gato).
    """
    if first == second:
        return first
    if isinstance(first, ClassType) and isinstance(second, ClassType):
        ancestor = common_superclass(first.class_name, second.class_name)
        return ClassType(ancestor) if ancestor is not None else None
    if (
        isinstance(first, ArrayType)
        and isinstance(second, ArrayType)
        and first.dimensions == second.dimensions
    ):
        element = _unify(first.element_type, second.element_type)
        return ArrayType(element, first.dimensions) if element is not None else None
    return None


def check_array_literal(
    element_types: list[Type],
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Unifica los elementos de un literal y devuelve su ArrayType (SEM-ARR-002)."""
    if not element_types:
        # `[]` no aporta informacion: el tipo lo fija la anotacion del destino.
        return ArrayType(ERROR, 1)

    known = [t for t in element_types if not isinstance(t, ErrorType)]
    if not known:
        return ArrayType(ERROR, 1)

    unified = known[0]
    for candidate in known[1:]:
        common = _unify(unified, candidate)
        if common is not None:
            unified = common
            continue
        if candidate != unified:
            diag.error(
                "SEM-ARR-002",
                "Los elementos del arreglo deben ser del mismo tipo "
                f"(se encontro '{unified.name}' y '{candidate.name}').",
                line,
                col,
            )
            return ArrayType(ERROR, 1)

    if isinstance(unified, ArrayType):
        return ArrayType(unified.element_type, unified.dimensions + 1)
    return ArrayType(unified, 1)


def check_index_access(
    target_type: Type,
    index_type: Type,
    target_name: str,
    line: int,
    col: int,
    diag: DiagnosticList,
    *,
    report_non_array: bool = True,
) -> Type:
    """Valida `expr[indice]` y devuelve el tipo del elemento accedido."""
    if not isinstance(index_type, ErrorType) and index_type != INTEGER:
        diag.error(
            "SEM-ARR-001",
            "El indice de acceso a arreglo debe ser de tipo integer "
            f"(se recibio '{index_type.name}').",
            line,
            col,
        )

    if isinstance(target_type, ArrayType):
        return element_type_of(target_type)

    if isinstance(target_type, ErrorType):
        return ERROR

    if report_non_array:
        diag.error(
            "SEM-ARR-004",
            f"No se puede indexar '{target_name}': no es un arreglo "
            f"(es de tipo '{target_type.name}').",
            line,
            col,
        )
    return ERROR


def check_foreach_collection(
    collection_type: Type,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Valida la coleccion de un foreach y devuelve el tipo de la variable de iteracion."""
    if isinstance(collection_type, ArrayType):
        return element_type_of(collection_type)

    if not isinstance(collection_type, ErrorType):
        diag.error(
            "SEM-ARR-003",
            "La expresion sobre la que itera foreach debe ser un arreglo "
            f"(se recibio '{collection_type.name}').",
            line,
            col,
        )
    return ERROR
