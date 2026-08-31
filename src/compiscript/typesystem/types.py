"""Sistema de tipos de Compiscript -- version minima del walking skeleton.

Solo cubre los tipos primitivos que hacen falta para las dos primeras
reglas semanticas (variable no declarada / redeclaracion). Los tipos
compuestos (ArrayType, ClassType, FunctionType) se agregan cuando se
implementen las reglas que los necesitan (ver docs/Compiscript_Diseno_Semantico.md,
seccion 4), no antes -- evita diseniar de mas sobre requisitos que
todavia no se conocen bien.
"""
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
    """Tipo 'comodin': se devuelve despues de reportar un error ya
    diagnosticado, para no generar una cascada de errores derivados
    del mismo problema (ver diseno, seccion 7)."""

    name = "<error>"

    def __eq__(self, other: object) -> bool:
        # ErrorType es compatible con cualquier cosa a proposito: una vez
        # que ya se reporto un error sobre este símbolo, no queremos que
        # las comparaciones de tipo generen un segundo error en cascada.
        return True

    def __hash__(self) -> int:
        return hash(ErrorType)


# Instancias compartidas (los tipos primitivos no llevan estado propio,
# no hace falta crear una instancia nueva cada vez).
INTEGER = IntegerType()
STRING = StringType()
BOOLEAN = BooleanType()
ERROR = ErrorType()


def is_assignable(source: Type, target: Type) -> bool:
    """¿Se puede asignar/inicializar un valor de tipo `source` en algo
    declarado de tipo `target`? Version minima: solo identidad de tipo,
    mas la regla comodin de ErrorType. Cuando se agreguen ClassType y
    herencia, esta funcion es el lugar donde se agrega covarianza simple
    (ver diseno, seccion 4)."""
    if isinstance(source, ErrorType) or isinstance(target, ErrorType):
        return True
    return source == target
