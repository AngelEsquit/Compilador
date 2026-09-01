"""Simbolos que se almacenan en la tabla de simbolos (Scope)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from compiscript.typesystem.types import ClassType, FunctionType, Type


@dataclass
class Symbol:
    """Clase base de cualquier simbolo en el compilador."""

    name: str
    decl_type: Type
    is_const: bool = False
    initialized: bool = False
    line: int = 0
    column: int = 0

    def to_dict(self) -> dict:
        return {
            "kind": "symbol",
            "name": self.name,
            "type": self.decl_type.name,
            "isConst": self.is_const,
            "initialized": self.initialized,
            "line": self.line,
            "column": self.column,
        }


@dataclass
class VariableSymbol(Symbol):
    """Simbolo para variables declaradas con `let` o `var`."""

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["kind"] = "variable"
        return data


@dataclass
class ConstSymbol(Symbol):
    """Simbolo para constantes declaradas con `const`."""

    is_const: bool = True
    initialized: bool = True

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["kind"] = "constant"
        return data


@dataclass
class ParameterSymbol(Symbol):
    """Simbolo para parametros formales de funciones o metodos."""

    initialized: bool = True

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["kind"] = "parameter"
        return data


@dataclass
class FunctionSymbol(Symbol):
    """Simbolo para funciones y metodos."""

    parameters: list[ParameterSymbol] = field(default_factory=list)
    return_type: Optional[Type] = None
    is_method: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.decl_type, FunctionType):
            self.return_type = self.decl_type.return_type
        elif self.return_type is not None:
            param_types = [p.decl_type for p in self.parameters]
            self.decl_type = FunctionType(param_types, self.return_type)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["kind"] = "method" if self.is_method else "function"
        data["parameters"] = [p.to_dict() for p in self.parameters]
        data["returnType"] = self.return_type.name if self.return_type else "void"
        return data


@dataclass
class ClassSymbol(Symbol):
    """Simbolo para clases y sus miembros."""

    superclass_name: Optional[str] = None
    fields: dict[str, VariableSymbol] = field(default_factory=dict)
    methods: dict[str, FunctionSymbol] = field(default_factory=dict)
    constructor: Optional[FunctionSymbol] = None

    def __post_init__(self) -> None:
        if not isinstance(self.decl_type, ClassType):
            self.decl_type = ClassType(self.name)

    def define_field(self, field_sym: VariableSymbol) -> bool:
        if field_sym.name in self.fields:
            return False
        self.fields[field_sym.name] = field_sym
        return True

    def define_method(self, method_sym: FunctionSymbol) -> bool:
        if method_sym.name in self.methods:
            return False
        self.methods[method_sym.name] = method_sym
        if method_sym.name == "constructor":
            self.constructor = method_sym
        return True

    def resolve_member(self, name: str) -> Optional[Symbol]:
        if name in self.fields:
            return self.fields[name]
        if name in self.methods:
            return self.methods[name]
        return None

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["kind"] = "class"
        data["superclassName"] = self.superclass_name
        data["fields"] = {k: v.to_dict() for k, v in self.fields.items()}
        data["methods"] = {k: v.to_dict() for k, v in self.methods.items()}
        return data
