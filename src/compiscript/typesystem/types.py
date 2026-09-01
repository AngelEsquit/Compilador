"""Sistema de tipos de Compiscript."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class Type:
    """Clase base para todos los tipos de Compiscript."""

    name: str = "type"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self))

    def __hash__(self) -> int:
        return hash(type(self))

    def __repr__(self) -> str:
        return self.name

    def to_dict(self) -> dict:
        return {"kind": self.name}


class IntegerType(Type):
    name = "integer"


class StringType(Type):
    name = "string"


class BooleanType(Type):
    name = "boolean"


class NullType(Type):
    name = "null"


class VoidType(Type):
    name = "void"


class ErrorType(Type):
    """Comodin devuelto tras un error ya reportado, para evitar cascadas."""

    name = "<error>"

    def __eq__(self, other: object) -> bool:
        # Compatible con todo a proposito para no generar un segundo error.
        return True

    def __hash__(self) -> int:
        return hash(ErrorType)


@dataclass
class ArrayType(Type):
    """Tipo arreglo para T[] o matrices multidimensionales T[][]."""

    element_type: Type
    dimensions: int = 1

    @property
    def name(self) -> str:
        return f"{self.element_type.name}{'[]' * self.dimensions}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ErrorType):
            return True
        if not isinstance(other, ArrayType):
            return False
        return self.element_type == other.element_type and self.dimensions == other.dimensions

    def __hash__(self) -> int:
        return hash((self.element_type, self.dimensions))

    def __repr__(self) -> str:
        return self.name

    def to_dict(self) -> dict:
        return {
            "kind": "array",
            "elementType": self.element_type.to_dict(),
            "dimensions": self.dimensions,
        }


@dataclass
class ClassType(Type):
    """Tipo correspondiente a una instancia de una clase."""

    class_name: str

    @property
    def name(self) -> str:
        return self.class_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ErrorType):
            return True
        if not isinstance(other, ClassType):
            return False
        return self.class_name == other.class_name

    def __hash__(self) -> int:
        return hash(self.class_name)

    def __repr__(self) -> str:
        return self.class_name

    def to_dict(self) -> dict:
        return {"kind": "class", "className": self.class_name}


@dataclass
class FunctionType(Type):
    """Tipo de una funcion con sus parametros y tipo de retorno."""

    param_types: list[Type]
    return_type: Type

    @property
    def name(self) -> str:
        params_str = ", ".join(p.name for p in self.param_types)
        return f"({params_str}) => {self.return_type.name}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ErrorType):
            return True
        if not isinstance(other, FunctionType):
            return False
        return self.param_types == other.param_types and self.return_type == other.return_type

    def __hash__(self) -> int:
        return hash((tuple(self.param_types), self.return_type))

    def __repr__(self) -> str:
        return self.name

    def to_dict(self) -> dict:
        return {
            "kind": "function",
            "paramTypes": [p.to_dict() for p in self.param_types],
            "returnType": self.return_type.to_dict(),
        }


# Instancias singleton de tipos primitivos
INTEGER = IntegerType()
STRING = StringType()
BOOLEAN = BooleanType()
NULL = NullType()
VOID = VoidType()
ERROR = ErrorType()


def is_assignable(source: Type, target: Type) -> bool:
    """Indica si un valor de tipo `source` es asignable a un contenedor de tipo `target`."""
    if isinstance(source, ErrorType) or isinstance(target, ErrorType):
        return True

    # null es asignable a variables de tipo ClassType
    if isinstance(source, NullType) and isinstance(target, ClassType):
        return True

    if isinstance(source, ArrayType) and isinstance(target, ArrayType):
        if source.dimensions != target.dimensions:
            return False
        return is_assignable(source.element_type, target.element_type)

    if isinstance(source, FunctionType) and isinstance(target, FunctionType):
        if len(source.param_types) != len(target.param_types):
            return False
        params_ok = all(
            is_assignable(t_p, s_p)
            for s_p, t_p in zip(source.param_types, target.param_types)
        )
        ret_ok = is_assignable(source.return_type, target.return_type)
        return params_ok and ret_ok

    return source == target
