"""Reglas semanticas de clases y objetos (Seccion 2.5).

Valida:
- Existencia de la superclase y ausencia de ciclos de herencia (SEM-CLASS-003)
- Acceso a miembros (campos y metodos) existentes, incluyendo herencia (SEM-CLASS-001)
- Uso de `this` solo dentro de metodos de una clase (SEM-CLASS-002, en analyzer.py)
- Instanciacion con `new` validando aridad y tipos del constructor (SEM-CLASS-004)
- Asignacion a propiedades de objetos (reutiliza SEM-TYPE-003/006)
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.semantic.rules_types import check_assignment_compatibility
from compiscript.symbols.scope import Scope
from compiscript.symbols.symbol import ClassSymbol, FunctionSymbol, Symbol
from compiscript.typesystem.types import (
    ERROR,
    ClassType,
    ErrorType,
    Type,
    is_assignable,
)


def _class_symbol_for(obj_type: Type, scope: Scope) -> Optional[ClassSymbol]:
    """Resuelve el ClassSymbol correspondiente a un ClassType, si existe."""
    if not isinstance(obj_type, ClassType):
        return None
    symbol = scope.resolve(obj_type.class_name)
    return symbol if isinstance(symbol, ClassSymbol) else None


def link_superclass(class_sym: ClassSymbol, scope: Scope, diag: DiagnosticList) -> None:
    """Resuelve `superclass_name` a su ClassSymbol y detecta ciclos de herencia.

    Se ejecuta durante la pre-declaracion, una vez que todas las clases del
    mismo ambito ya fueron registradas (`declarations_pass.predeclare_classes`),
    para poder aceptar herencia hacia clases declaradas mas abajo.
    """
    if class_sym.superclass_name is None:
        return

    super_sym = scope.resolve(class_sym.superclass_name)
    if not isinstance(super_sym, ClassSymbol):
        diag.error(
            "SEM-CLASS-003",
            f"La superclase '{class_sym.superclass_name}' de la clase "
            f"'{class_sym.name}' no esta declarada.",
            class_sym.line,
            class_sym.column,
        )
        return

    # Deteccion de ciclos: recorrer la cadena de superclases de `super_sym`
    # buscando si se vuelve a llegar a `class_sym` (directa o indirectamente).
    seen = {class_sym.name}
    curr: Optional[ClassSymbol] = super_sym
    while curr is not None:
        if curr.name in seen:
            diag.error(
                "SEM-CLASS-003",
                f"Ciclo de herencia detectado: la clase '{class_sym.name}' "
                f"termina heredando de si misma a traves de '{curr.name}'.",
                class_sym.line,
                class_sym.column,
            )
            return
        seen.add(curr.name)
        curr = curr.superclass

    class_sym.superclass = super_sym


def check_member_access(
    obj_type: Type,
    member_name: str,
    scope: Scope,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Valida `obj.member` (lectura o preparacion para llamada) y devuelve su tipo."""
    if isinstance(obj_type, ErrorType):
        return ERROR

    class_sym = _class_symbol_for(obj_type, scope)
    if class_sym is None:
        diag.error(
            "SEM-CLASS-001",
            f"No se puede acceder a la propiedad '{member_name}': el valor "
            f"no es un objeto (es de tipo '{obj_type.name}').",
            line,
            col,
        )
        return ERROR

    member = class_sym.resolve_member(member_name)
    if member is None:
        diag.error(
            "SEM-CLASS-001",
            f"La clase '{class_sym.name}' no tiene la propiedad o metodo '{member_name}'.",
            line,
            col,
        )
        return ERROR

    return member.decl_type


def check_property_assignment(
    obj_type: Type,
    member_name: str,
    val_type: Type,
    scope: Scope,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> None:
    """Valida `obj.member = val`: existencia, mutabilidad y compatibilidad de tipo."""
    if isinstance(obj_type, ErrorType):
        return

    class_sym = _class_symbol_for(obj_type, scope)
    if class_sym is None:
        diag.error(
            "SEM-CLASS-001",
            f"No se puede asignar la propiedad '{member_name}': el valor "
            f"no es un objeto (es de tipo '{obj_type.name}').",
            line,
            col,
        )
        return

    member: Optional[Symbol] = class_sym.resolve_member(member_name)
    if member is None:
        diag.error(
            "SEM-CLASS-001",
            f"La clase '{class_sym.name}' no tiene la propiedad '{member_name}'.",
            line,
            col,
        )
        return

    if isinstance(member, FunctionSymbol):
        diag.error(
            "SEM-CLASS-001",
            f"'{member_name}' es un metodo de '{class_sym.name}' y no se puede reasignar.",
            line,
            col,
        )
        return

    check_assignment_compatibility(
        member.decl_type, val_type, member.is_const, line, col, diag, symbol_name=member_name
    )


def _find_constructor(class_sym: ClassSymbol) -> Optional[FunctionSymbol]:
    """Busca el constructor propio o heredado de la clase (el mas cercano en la jerarquia)."""
    curr: Optional[ClassSymbol] = class_sym
    while curr is not None:
        if curr.constructor is not None:
            return curr.constructor
        curr = curr.superclass
    return None


def check_new_expression(
    class_name: str,
    arg_types: list[Type],
    scope: Scope,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> Type:
    """Valida `new ClassName(args)`: existencia de la clase y firma del constructor."""
    class_sym = scope.resolve(class_name)
    if not isinstance(class_sym, ClassSymbol):
        diag.error(
            "SEM-CLASS-003",
            f"La clase '{class_name}' no esta declarada.",
            line,
            col,
        )
        return ERROR

    constructor = _find_constructor(class_sym)
    expected = [p.decl_type for p in constructor.parameters] if constructor is not None else []

    if len(arg_types) != len(expected):
        diag.error(
            "SEM-CLASS-004",
            f"El constructor de '{class_name}' espera {len(expected)} argumento(s) "
            f"pero recibio {len(arg_types)}.",
            line,
            col,
        )
        return ClassType(class_name)

    for index, (actual, declared) in enumerate(zip(arg_types, expected), start=1):
        if not is_assignable(actual, declared):
            diag.error(
                "SEM-CLASS-004",
                f"El argumento {index} del constructor de '{class_name}' debe ser de "
                f"tipo '{declared.name}' (se recibio '{actual.name}').",
                line,
                col,
            )

    return ClassType(class_name)
