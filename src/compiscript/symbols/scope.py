"""Tabla de simbolos como arbol de ambitos -- version minima del walking
skeleton (ver docs/Compiscript_Diseno_Semantico.md, seccion 5).

Solo existen los ambitos GLOBAL y BLOCK por ahora. FUNCTION y CLASS se
agregan cuando se implementen las reglas de funciones y clases (cada
uno necesita guardar datos propios -- tipo de retorno esperado,
superclase, etc. -- que todavia no existen en este walking skeleton).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from compiscript.symbols.symbol import VariableSymbol


class ScopeKind(Enum):
    GLOBAL = "global"
    BLOCK = "block"


class Scope:
    def __init__(self, kind: ScopeKind, parent: Optional["Scope"] = None) -> None:
        self.kind = kind
        self.parent = parent
        self._symbols: dict[str, VariableSymbol] = {}

    def define(self, symbol: VariableSymbol) -> bool:
        """Declara `symbol` en ESTE scope. Devuelve False (sin agregarlo)
        si el nombre ya existe en este mismo ambito -- el llamador decide
        que hacer con eso (reportar el diagnostico de redeclaracion)."""
        if symbol.name in self._symbols:
            return False
        self._symbols[symbol.name] = symbol
        return True

    def resolve(self, name: str) -> Optional[VariableSymbol]:
        """Busca `name` en este scope y, si no esta, sube por la cadena
        de padres hasta el scope GLOBAL. Devuelve None si no aparece en
        ningun nivel (variable no declarada)."""
        scope: Optional[Scope] = self
        while scope is not None:
            symbol = scope._symbols.get(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        return None

    def resolve_local(self, name: str) -> Optional[VariableSymbol]:
        """Busca `name` solo en este scope, sin subir a los padres."""
        return self._symbols.get(name)

    def child(self, kind: ScopeKind = ScopeKind.BLOCK) -> "Scope":
        return Scope(kind, parent=self)

    def __repr__(self) -> str:
        names = ", ".join(self._symbols.keys())
        return f"Scope({self.kind.value}, [{names}])"
