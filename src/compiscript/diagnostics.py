"""Errores y warnings acumulados durante el analisis semantico.

El analizador no lanza excepciones: junta diagnosticos y sigue recorriendo
el arbol, para reportar varios problemas en una sola pasada.
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
        return f"[{self.severity.value.upper()} {self.code}] linea {self.line}:{self.column}: {self.message}"


class DiagnosticList:
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
