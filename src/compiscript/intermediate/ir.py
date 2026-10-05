"""Estructuras de datos para codigo de tres direcciones."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Instruction:
    """Una instruccion TAC con hasta tres direcciones."""

    op: str
    arg1: str = ""
    arg2: str = ""
    result: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"op": self.op, "arg1": self.arg1, "arg2": self.arg2, "result": self.result}

    def to_text(self) -> str:
        if self.op == "label":
            return f"{self.result}:"
        if self.op == "goto":
            return f"goto {self.result}"
        if self.op in {"if", "ifFalse"}:
            return f"{self.op} {self.arg1} goto {self.result}"
        if self.op == "if_rel":
            return f"if {self.arg1} {self.arg2} goto {self.result}"
        if self.op in {"param", "param_decl", "return", "print", "read", "throw"}:
            return f"{self.op} {self.arg1}".rstrip()
        if self.op == "try":
            return f"try goto {self.result}"
        if self.op == "call":
            return f"call {self.arg1}, {self.arg2}"
        if self.op == "call_result":
            return f"{self.result} = call {self.arg1}, {self.arg2}"
        if self.op == "env_load":
            return f"{self.result} = up({self.arg1}).{self.arg2}"
        if self.op == "env_store":
            return f"up({self.arg2}).{self.result} = {self.arg1}"
        if self.op == "link":
            return f"link {self.arg1}"
        if self.op == "invoke":
            return f"{self.result} = invoke {self.arg1}, {self.arg2}"
        if self.op == "index_load":
            return f"{self.result} = {self.arg1}[{self.arg2}]"
        if self.op == "index_store":
            return f"{self.result}[{self.arg1}] = {self.arg2}"
        if self.op == "member_load":
            return f"{self.result} = {self.arg1}.{self.arg2}"
        if self.op == "member_store":
            return f"{self.result}.{self.arg1} = {self.arg2}"
        if self.op == "new":
            return f"{self.result} = new {self.arg1}, {self.arg2}"
        if self.op == "unary":
            return f"{self.result} = {self.arg1}{self.arg2}"
        if self.op == "binary":
            return f"{self.result} = {self.arg1} {self.arg2}"
        if self.op == "array":
            return f"{self.result} = array {self.arg1}"
        if self.op == "function":
            return f"function {self.result}"
        if self.op == "end_function":
            return f"end function {self.result}"
        if self.op == "copy":
            return f"{self.result} = {self.arg1}"
        return " ".join(part for part in (self.result, self.op, self.arg1, self.arg2) if part)


@dataclass
class TACProgram:
    instructions: list[Instruction] = field(default_factory=list)
    # Temporales distintos que uso cada funcion (`main` es el codigo de nivel superior).
    temp_counts: dict[str, int] = field(default_factory=dict)

    def emit(self, op: str, arg1: str = "", arg2: str = "", result: str = "") -> Instruction:
        instruction = Instruction(op, arg1, arg2, result)
        self.instructions.append(instruction)
        return instruction

    def to_text(self) -> str:
        return "\n".join(instruction.to_text() for instruction in self.instructions)


class TempAllocator:
    """Asigna temporales y recicla los que ya no necesita una expresion.

    `reserved` contiene los identificadores del programa fuente: un temporal
    nunca recibe uno de esos nombres, y `release` solo recicla temporales que
    este allocator entrego (una variable de usuario llamada `t1` no se recicla).
    """

    def __init__(self, reserved: frozenset[str] | set[str] = frozenset()) -> None:
        self._reserved = reserved
        self._free: list[str] = []
        self._live: set[str] = set()
        self._next = 0

    def acquire(self) -> str:
        if self._free:
            name = self._free.pop()
        else:
            name = f"t{self._next}"
            self._next += 1
            while name in self._reserved:
                name = f"t{self._next}"
                self._next += 1
        self._live.add(name)
        return name

    def release(self, name: str) -> None:
        if name in self._live:
            self._live.discard(name)
            self._free.append(name)

    @property
    def count(self) -> int:
        """Cantidad de temporales distintos creados hasta ahora."""
        return self._next
