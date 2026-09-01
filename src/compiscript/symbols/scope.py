"""Tabla de simbolos como arbol de ambitos encadenados."""
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
        """Declara `symbol` aqui. False si el nombre ya existe en este ambito."""
        if symbol.name in self._symbols:
            return False
        self._symbols[symbol.name] = symbol
        return True

    def resolve(self, name: str) -> Optional[VariableSymbol]:
        """Busca `name` aqui y sube por la cadena de padres. None si no existe."""
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
