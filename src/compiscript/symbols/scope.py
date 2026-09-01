"""Tabla de simbolos como arbol de ambitos (scopes) encadenados.

Soporta:
- Insercion (define)
- Recuperacion (resolve, resolve_local)
- Actualizacion (update)
- Manejo de alcances jerarquicos (GLOBAL, BLOCK, FUNCTION, CLASS, LOOP)
- Serializacion a estructura JSON para integracion con IDE y fases futuras.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from compiscript.symbols.symbol import Symbol


class ScopeKind(Enum):
    GLOBAL = "global"
    BLOCK = "block"
    FUNCTION = "function"
    CLASS = "class"
    LOOP = "loop"


class Scope:
    """Representa un ambito en el arbol lexico de la tabla de simbolos."""

    def __init__(
        self,
        kind: ScopeKind,
        parent: Optional["Scope"] = None,
        name: str = "",
    ) -> None:
        self.kind = kind
        self.parent = parent
        self.name = name or kind.value
        self._symbols: dict[str, Symbol] = {}
        self.children: list[Scope] = []

    # 1. Insercion
    def define(self, symbol: Symbol) -> bool:
        """Declara un nuevo simbolo en este ambito. Devuelve False si ya existe aqui."""
        if symbol.name in self._symbols:
            return False
        self._symbols[symbol.name] = symbol
        return True

    # 2. Recuperacion
    def resolve(self, name: str) -> Optional[Symbol]:
        """Busca `name` en este ambito y sube recursivamente por la cadena de padres."""
        scope: Optional[Scope] = self
        while scope is not None:
            symbol = scope._symbols.get(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        return None

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """Busca `name` unicamente en este ambito, sin consultar a los padres."""
        return self._symbols.get(name)

    # 3. Actualizacion
    def update(self, name: str, **kwargs: Any) -> bool:
        """Actualiza atributos del simbolo `name` en el ambito donde este declarado."""
        symbol = self.resolve(name)
        if symbol is None:
            return False
        for key, value in kwargs.items():
            if hasattr(symbol, key):
                setattr(symbol, key, value)
            else:
                return False
        return True

    # 4. Manejo de alcances
    def child(self, kind: ScopeKind = ScopeKind.BLOCK, name: str = "") -> "Scope":
        """Crea y registra un nuevo ambito hijo en el arbol."""
        child_scope = Scope(kind, parent=self, name=name)
        self.children.append(child_scope)
        return child_scope

    def get_enclosing_function(self) -> Optional["Scope"]:
        """Encuentra el ambito de funcion mas cercano hacia arriba."""
        curr: Optional[Scope] = self
        while curr is not None:
            if curr.kind is ScopeKind.FUNCTION:
                return curr
            curr = curr.parent
        return None

    def is_inside_loop(self) -> bool:
        """Determina si este ambito se encuentra dentro de un bucle."""
        curr: Optional[Scope] = self
        while curr is not None:
            if curr.kind is ScopeKind.LOOP:
                return True
            # Si entramos en una funcion anidada dentro del bucle, los break/continue no cruzan la frontera
            if curr.kind is ScopeKind.FUNCTION:
                return False
            curr = curr.parent
        return False

    def get_enclosing_class(self) -> Optional["Scope"]:
        """Encuentra el ambito de clase mas cercano hacia arriba."""
        curr: Optional[Scope] = self
        while curr is not None:
            if curr.kind is ScopeKind.CLASS:
                return curr
            curr = curr.parent
        return None

    # 5. Serializacion para IDE y exportacion
    def to_dict(self) -> dict:
        """Exporta la jerarquia del ambito a un diccionario JSON-serializable."""
        return {
            "kind": self.kind.value,
            "name": self.name,
            "symbols": {k: v.to_dict() for k, v in self._symbols.items()},
            "children": [c.to_dict() for c in self.children],
        }

    def __repr__(self) -> str:
        names = ", ".join(self._symbols.keys())
        return f"Scope({self.kind.value}:{self.name}, [{names}])"
