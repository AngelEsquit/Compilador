"""Operandos del TAC vistos desde el backend: donde vive cada nombre y de que tipo es.

El TAC nombra las variables sin calificar, asi que cada instruccion lleva el ambito con
el que se emitio (`Instruction.scope`). Con ese ambito se llega al simbolo, y el simbolo
ya trae la ubicacion que calculo `symbols/layout.py`.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from compiscript.symbols.layout import CONTROL_SIZE, TEMP_SIZE
from compiscript.symbols.scope import Scope
from compiscript.symbols.symbol import (
    ClassSymbol,
    ConstSymbol,
    FunctionSymbol,
    ParameterSymbol,
    VariableSymbol,
)
from compiscript.typesystem.types import (
    BOOLEAN,
    FLOAT,
    INTEGER,
    NULL,
    STRING,
    VOID,
    ArrayType,
    ClassType,
    NullType,
    Type,
)

_STORABLE = (VariableSymbol, ConstSymbol, ParameterSymbol)
_INT = re.compile(r"\d+")
_FLOAT = re.compile(r"\d+\.\d+")
_TEMP = re.compile(r"t(\d+)")

ARITHMETIC = frozenset({"+", "-", "*", "/", "%"})
COMPARISON = frozenset({"<", "<=", ">", ">=", "==", "!="})
CALLS = frozenset({"call_result", "invoke", "new"})


class UnsupportedFeature(NotImplementedError):
    """El backend todavia no traduce esta construccion."""

    def __init__(self, feature: str, detail: str = "") -> None:
        super().__init__(f"{feature}: {detail}" if detail else feature)
        self.feature = feature


@dataclass(frozen=True, eq=False)
class Var:
    """Un valor con casa en memoria: variable global, local, parametro o temporal."""

    name: str
    base: str  # `$gp` (area estatica) o `$fp` (registro de activacion)
    offset: int
    size: int  # bytes que se leen o escriben: 1 (boolean) o 4
    kind: str  # global | local | param | temp
    captured: bool = False  # la usa una funcion anidada por access_link

    @property
    def home(self) -> str:
        return f"{self.offset}({self.base})"

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Const:
    """Un valor inmediato: entero (`li`) o direccion de una etiqueta (`la`)."""

    text: str
    is_label: bool = False

    @property
    def value(self) -> int:
        return int(self.text)


def float_bits(text: str) -> int:
    """Patron de bits IEEE 754 de precision simple, como entero con signo."""
    return struct.unpack("<i", struct.pack("<f", float(text)))[0]


def access_size(size: int) -> int:
    """El layout reserva 8 bytes para referencias y float; en MIPS32 se usan 4."""
    return 1 if size == 1 else 4


class Resolver:
    """Traduce los nombres del TAC a operandos y lleva el tipo de cada temporal."""

    def __init__(self, layout, global_scope: Scope) -> None:
        self.layout = layout
        self.exception_offset = layout.data_size  # celda del mensaje del error capturado
        self.main_fp_offset = layout.data_size + 4  # fp del programa principal
        self.static_size = layout.data_size + 8
        self.strings: dict[str, str] = {}
        self.functions: dict[str, FunctionSymbol] = {}
        self.classes: dict[str, ClassSymbol] = {}
        self._captured: set[int] = set()
        self._vars: dict[int, Var] = {}
        self._temps: dict[str, Var] = {}
        self._temp_types: dict[str, Type] = {}
        self._exception = Var("exception", "$gp", self.exception_offset, 4, "global")
        self.record = None
        self._collect(global_scope)

    def _collect(self, scope: Scope) -> None:
        for symbol in scope.symbols():
            if isinstance(symbol, FunctionSymbol) and symbol.label:
                self.functions[symbol.label] = symbol
            elif isinstance(symbol, ClassSymbol):
                self.classes.setdefault(symbol.name, symbol)
        for child in scope.children:
            self._collect(child)

    def mark_captured(self, instructions) -> None:
        """Las variables que una funcion anidada lee o escribe deben estar en memoria en cada llamada."""
        for ins in instructions:
            if ins.op in ("env_load", "env_store"):
                symbol = self.symbol(ins.arg2 if ins.op == "env_load" else ins.result, ins)
                if symbol is not None:
                    self._captured.add(id(symbol))

    def enter(self, record) -> None:
        """Empieza una funcion: sus temporales y sus tipos son propios."""
        self.record = record
        self._temps = {}
        self._temp_types = {}

    # ------------------------------------------------------------------ operandos
    def symbol(self, token: str, ins):
        symbol = ins.scope.resolve(token) if ins.scope is not None else None
        return symbol if isinstance(symbol, _STORABLE) else None

    def string_label(self, literal: str) -> str:
        return self.strings.setdefault(literal, f"_str{len(self.strings)}")

    def operand(self, token: str, ins):
        """`Const` para literales; `Var` para todo lo que tiene casa en memoria."""
        if token == "true":
            return Const("1")
        if token in ("false", "null"):
            return Const("0")
        if token.startswith('"'):
            return Const(self.string_label(token), is_label=True)
        if _INT.fullmatch(token):
            return Const(token)
        if _FLOAT.fullmatch(token):
            return Const(str(float_bits(token)))
        if token == "this":
            return self._this()
        if token == "exception":
            return self._exception
        symbol = self.symbol(token, ins)
        if symbol is not None:
            return self._variable(symbol)
        match = _TEMP.fullmatch(token)
        if match:
            return self._temp(token, int(match.group(1)))
        raise UnsupportedFeature("operando", f"no se puede ubicar '{token}'")

    def _this(self) -> Var:
        return self._temps.setdefault("this", Var("this", "$fp", CONTROL_SIZE, 4, "param"))

    def _temp(self, name: str, number: int) -> Var:
        if name not in self._temps:
            offset = self.record.temps_offset + number * TEMP_SIZE
            self._temps[name] = Var(name, "$fp", offset, 4, "temp")
        return self._temps[name]

    def _variable(self, symbol) -> Var:
        var = self._vars.get(id(symbol))
        if var is None:
            if symbol.storage == "global":
                base = "$gp"
            elif symbol.storage in ("local", "param"):
                base = "$fp"
            else:
                raise UnsupportedFeature("clases", f"'{symbol.name}' es un campo: se accede con this")
            var = Var(
                symbol.name,
                base,
                symbol.offset,
                access_size(symbol.size),
                symbol.storage,
                id(symbol) in self._captured,
            )
            self._vars[id(symbol)] = var
        return var

    # ------------------------------------------------------------------ tipos
    def type_of(self, token: str, ins) -> Type:
        if token in ("true", "false"):
            return BOOLEAN
        if token == "null":
            return NULL
        if token.startswith('"') or token == "exception":
            return STRING
        if _INT.fullmatch(token):
            return INTEGER
        if _FLOAT.fullmatch(token):
            return FLOAT
        if token == "this":
            return ClassType(self.record.name.rsplit(".", 1)[0])
        symbol = self.symbol(token, ins)
        if symbol is not None:
            return symbol.decl_type
        return self._temp_types.get(token, INTEGER)

    def member_type(self, owner: Type, member: str) -> Type:
        cls = self.classes.get(owner.class_name) if isinstance(owner, ClassType) else None
        symbol = cls.resolve_member(member) if cls is not None else None
        if isinstance(symbol, FunctionSymbol):
            return symbol.return_type or VOID
        return symbol.decl_type if symbol is not None else INTEGER

    def result_type(self, ins) -> Type:
        """Tipo del valor que deja la instruccion en `result`."""
        op = ins.op
        if op == "copy":
            return self.type_of(ins.arg1, ins)
        if op in COMPARISON or op == "not":
            return BOOLEAN
        if op in ARITHMETIC:
            left, right = self.type_of(ins.arg1, ins), self.type_of(ins.arg2, ins)
            if STRING in (left, right):
                return STRING
            return FLOAT if FLOAT in (left, right) else INTEGER
        if op == "neg":
            return self.type_of(ins.arg1, ins)
        if op == "length":
            return INTEGER
        if op == "array":
            items = ins.arg1.split(", ") if ins.arg1 else []
            element = self.type_of(items[0], ins) if items else NULL
            if isinstance(element, ArrayType):
                return ArrayType(element.element_type, element.dimensions + 1)
            return ArrayType(element)
        if op == "index_load":
            array = self.type_of(ins.arg1, ins)
            if not isinstance(array, ArrayType):
                return INTEGER
            if array.dimensions > 1:
                return ArrayType(array.element_type, array.dimensions - 1)
            return array.element_type
        if op == "member_load":
            return self.member_type(self.type_of(ins.arg1, ins), ins.arg2)
        if op == "env_load":
            return self.type_of(ins.arg2, ins)
        if op == "new":
            return ClassType(ins.arg1)
        if op == "call_result":
            function = self.functions.get(ins.arg1)
            return (function.return_type if function is not None else None) or VOID
        if op == "invoke":
            receiver, method = ins.arg1.rsplit(".", 1)
            return self.member_type(self.type_of(receiver, ins), method)
        return INTEGER

    def observe(self, ins) -> None:
        """Registra el tipo del temporal que define la instruccion (se llama en orden de emision)."""
        if ins.op not in _DEFINING or not _TEMP.fullmatch(ins.result) or self.symbol(ins.result, ins) is not None:
            return
        new_type = self.result_type(ins)
        previous = self._temp_types.get(ins.result)
        # `cond ? objeto : null`: la rama null no debe borrar el tipo de la otra rama
        if isinstance(new_type, NullType) and isinstance(previous, (ClassType, ArrayType, type(STRING))):
            return
        self._temp_types[ins.result] = new_type

    # ------------------------------------------------------------------ usos y definiciones
    def uses_defs(self, ins) -> tuple[list[Var], list[Var]]:
        """Variables que la instruccion lee y la que escribe (las constantes no cuentan)."""
        op = ins.op
        used: list[str] = []
        defined = ins.result if op in _DEFINING else ""
        if op in ARITHMETIC or op in COMPARISON or op == "index_load":
            used = [ins.arg1, ins.arg2]
        elif op in ("copy", "neg", "not", "if", "ifFalse", "param", "print", "length", "member_load", "env_store"):
            used = [ins.arg1]
        elif op == "return" and ins.arg1:
            used = [ins.arg1]
        elif op == "array" and ins.arg1:
            used = ins.arg1.split(", ")
        elif op == "index_store":
            used = [ins.result, ins.arg1, ins.arg2]
        elif op == "member_store":
            used = [ins.result, ins.arg2]
        elif op == "invoke":
            used = [ins.arg1.rsplit(".", 1)[0]]
        uses = [v for v in (self.operand(token, ins) for token in used) if isinstance(v, Var)]
        defs = [self.operand(defined, ins)] if defined else []
        return uses, defs


_DEFINING = (
    ARITHMETIC
    | COMPARISON
    | CALLS
    | {"copy", "neg", "not", "array", "length", "index_load", "member_load", "env_load"}
)
