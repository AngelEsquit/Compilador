"""Diagnosticos del analizador semantico -- version minima del walking
skeleton (ver docs/Compiscript_Diseno_Semantico.md, seccion 7).

En vez de lanzar una excepcion en el primer error (lo que cortaria el
analisis y solo mostraria un problema a la vez), el analizador acumula
una lista de Diagnostic y sigue recorriendo el arbol.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()} {self.code}] linea {self.line}:{self.column} -- {self.message}"


class DiagnosticList:
    """Contenedor simple de diagnosticos acumulados durante un analisis."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def error(self, code: str, message: str, line: int, column: int) -> None:
        self._items.append(Diagnostic(Severity.ERROR, code, message, line, column))

    def warning(self, code: str, message: str, line: int, column: int) -> None:
        self._items.append(Diagnostic(Severity.WARNING, code, message, line, column))

    @property
    def items(self) -> list[Diagnostic]:
        return list(self._items)

    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self._items)

    def codes(self) -> list[str]:
        return [d.code for d in self._items]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)
