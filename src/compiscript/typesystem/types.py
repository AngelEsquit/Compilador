"""Sistema de tipos de Compiscript."""
from __future__ import annotations


class Type:
    """Clase base de todos los tipos de Compiscript."""

    name: str = "type"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self))

    def __hash__(self) -> int:
        return hash(type(self))

    def __repr__(self) -> str:
        return self.name


class IntegerType(Type):
    name = "integer"


class StringType(Type):
    name = "string"


class BooleanType(Type):
    name = "boolean"


class ErrorType(Type):
    """Comodin devuelto tras un error ya reportado, para evitar cascadas."""

    name = "<error>"

    def __eq__(self, other: object) -> bool:
        # Compatible con todo a proposito: evita un segundo error derivado.
        return True

    def __hash__(self) -> int:
        return hash(ErrorType)


# Instancias compartidas: los tipos primitivos no llevan estado propio.
INTEGER = IntegerType()
STRING = StringType()
BOOLEAN = BooleanType()
ERROR = ErrorType()


def is_assignable(source: Type, target: Type) -> bool:
    """Indica si un valor de tipo `source` cabe en algo declarado `target`."""
    if isinstance(source, ErrorType) or isinstance(target, ErrorType):
        return True
    return source == target
