"""Simulador de MIPS32 para ejecutar el ensamblador generado.

Acepta el subconjunto de instrucciones, pseudoinstrucciones, directivas y llamadas al
sistema de MARS y SPIM que usa el backend, de modo que el mismo archivo `.asm` corre
aqui y en esos simuladores. Sirve para las pruebas automaticas y para el IDE, y
registra las llamadas a funciones para construir el arbol de activacion.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from compiscript.backend.asm import DIRECTIVE, INSTR, LABEL, parse_lines

TEXT_BASE = 0x00400000
DATA_BASE = 0x10010000
HEAP_BASE = 0x10040000
STACK_TOP = 0x7FFFEFFC
STACK_SIZE = 1 << 20
HEAP_LIMIT = 1 << 24

REGISTER_NAMES = (
    "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
    "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra"
).split()
_REG = {f"${name}": number for number, name in enumerate(REGISTER_NAMES)}
_REG.update({f"${number}": number for number in range(32)})
V0, V1, A0, SP, FP, RA = _REG["$v0"], _REG["$v1"], _REG["$a0"], _REG["$sp"], _REG["$fp"], _REG["$ra"]

_MEMORY = re.compile(r"^(?P<offset>[^()]*)\((?P<base>\$\w+)\)$")
_ESCAPES = {"n": "\n", "t": "\t", "0": "\0", "\\": "\\", '"': '"', "'": "'", "r": "\r"}


class SimulatorError(Exception):
    """Fallo de la maquina: instruccion desconocida, memoria invalida o limite de pasos."""


def _signed(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _unsigned(value: int) -> int:
    return value & 0xFFFFFFFF


def _truncated_division(a: int, b: int) -> tuple[int, int]:
    quotient = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        quotient = -quotient
    return quotient, a - quotient * b


def _unescape(literal: str) -> bytes:
    body = literal[1:-1]
    out, position = [], 0
    while position < len(body):
        char = body[position]
        if char == "\\" and position + 1 < len(body):
            position += 1
            char = _ESCAPES.get(body[position], body[position])
        out.append(char)
        position += 1
    return "".join(out).encode("utf-8")


@dataclass
class Activation:
    """Nodo del arbol de activacion: una llamada a funcion durante la ejecucion."""

    name: str
    arguments: list[str] = field(default_factory=list)
    result: str | None = None
    frame_size: int = 0
    children: list["Activation"] = field(default_factory=list)
    returns: str = "void"  # tipo de retorno, para dar formato al resultado
    return_address: int = 0
    stack_pointer: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "frameSize": self.frame_size,
            "children": [child.to_dict() for child in self.children],
        }

    def to_text(self, depth: int = 0) -> str:
        call = f"{self.name}({', '.join(self.arguments)})"
        if self.result is not None:
            call += f" = {self.result}"
        lines = ["  " * depth + call]
        lines += [child.to_text(depth + 1) for child in self.children]
        return "\n".join(lines)


_ARITHMETIC = {
    "add": lambda a, b: a + b,
    "addu": lambda a, b: a + b,
    "addi": lambda a, b: a + b,
    "addiu": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "subu": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "and": lambda a, b: a & b,
    "andi": lambda a, b: a & b,
    "or": lambda a, b: a | b,
    "ori": lambda a, b: a | b,
    "xor": lambda a, b: a ^ b,
    "xori": lambda a, b: a ^ b,
    "nor": lambda a, b: ~(a | b),
    "slt": lambda a, b: int(a < b),
    "slti": lambda a, b: int(a < b),
    "sltu": lambda a, b: int(_unsigned(a) < _unsigned(b)),
    "sltiu": lambda a, b: int(_unsigned(a) < _unsigned(b)),
    "seq": lambda a, b: int(a == b),
    "sne": lambda a, b: int(a != b),
    "sgt": lambda a, b: int(a > b),
    "sge": lambda a, b: int(a >= b),
    "sle": lambda a, b: int(a <= b),
    "sll": lambda a, b: a << (b & 31),
    "sllv": lambda a, b: a << (b & 31),
    "srl": lambda a, b: _unsigned(a) >> (b & 31),
    "srlv": lambda a, b: _unsigned(a) >> (b & 31),
    "sra": lambda a, b: a >> (b & 31),
    "srav": lambda a, b: a >> (b & 31),
}

_BRANCH2 = {
    "beq": lambda a, b: a == b,
    "bne": lambda a, b: a != b,
    "blt": lambda a, b: a < b,
    "ble": lambda a, b: a <= b,
    "bgt": lambda a, b: a > b,
    "bge": lambda a, b: a >= b,
    "bltu": lambda a, b: _unsigned(a) < _unsigned(b),
    "bleu": lambda a, b: _unsigned(a) <= _unsigned(b),
    "bgtu": lambda a, b: _unsigned(a) > _unsigned(b),
    "bgeu": lambda a, b: _unsigned(a) >= _unsigned(b),
}

_BRANCH1 = {
    "beqz": lambda a: a == 0,
    "bnez": lambda a: a != 0,
    "bltz": lambda a: a < 0,
    "blez": lambda a: a <= 0,
    "bgtz": lambda a: a > 0,
    "bgez": lambda a: a >= 0,
}

_LOADS = {"lw": (4, True), "lb": (1, True), "lbu": (1, False), "lh": (2, True), "lhu": (2, False)}
_STORES = {"sw": 4, "sb": 1, "sh": 2}


class Simulator:
    def __init__(self, source: str, functions: dict[str, dict] | None = None, step_limit: int = 5_000_000) -> None:
        self.registers = [0] * 32
        self.hi = self.lo = 0
        self.pc = 0
        self.steps = 0
        self.step_limit = step_limit
        self.exit_code: int | None = None
        self._out = bytearray()
        self._data = bytearray()
        self._heap = bytearray()
        self._stack = bytearray(STACK_SIZE)
        self.labels: dict[str, int] = {}
        self.code: list = []  # (linea, operacion, argumentos ya decodificados)
        self._text_labels: dict[str, int] = {}
        # arbol de activacion: solo se registran las funciones del programa, no la biblioteca
        self.functions = functions or {}
        self.root = Activation("main", frame_size=self.functions.get("main", {}).get("frameSize", 0))
        self._calls: list[Activation] = [self.root]
        self._fixups: list[tuple[int, str]] = []  # `.word etiqueta` con la etiqueta aun sin definir
        self._assemble(source)

    @property
    def output(self) -> str:
        return self._out.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------ ensamblado
    def _assemble(self, source: str) -> None:
        lines = parse_lines(source)
        segment = "text"
        pending: list = []
        for line in lines:
            if line.kind == DIRECTIVE and line.op in (".data", ".text"):
                segment = line.op[1:]
            elif line.kind == LABEL:
                if line.op in self.labels:
                    raise SimulatorError(f"etiqueta repetida: {line.op}")
                if segment == "data":
                    self.labels[line.op] = DATA_BASE + len(self._data)
                else:
                    self.labels[line.op] = TEXT_BASE + 4 * len(pending)
                    self._text_labels[line.op] = len(pending)
            elif line.kind == DIRECTIVE:
                self._directive(line)
            elif line.kind == INSTR:
                if segment != "text":
                    raise SimulatorError(f"instruccion en .data: {line.to_text().strip()}")
                pending.append(line)
        for position, name in self._fixups:
            self._data[position : position + 4] = struct.pack("<I", _unsigned(self._number_or_label(name)))
        self.code = [self._decode(line) for line in pending]
        if "main" not in self._text_labels:
            raise SimulatorError("falta la etiqueta main")
        self.pc = self._text_labels["main"]
        self.registers[SP] = STACK_TOP

    def _directive(self, line) -> None:
        op, args = line.op, line.args
        if op == ".globl":
            return
        if op == ".space":
            self._data += bytes(int(args[0]))
        elif op == ".align":
            size = 1 << int(args[0])
            self._data += bytes(-len(self._data) % size)
        elif op == ".word":
            self._data += bytes(-len(self._data) % 4)
            for arg in args:
                self._data += struct.pack("<I", _unsigned(self._number_or_label(arg, late=True)))
        elif op == ".byte":
            for arg in args:
                self._data.append(int(arg, 0) & 0xFF)
        elif op in (".asciiz", ".ascii"):
            for arg in args:
                self._data += _unescape(arg) + (b"\0" if op == ".asciiz" else b"")
        else:
            raise SimulatorError(f"directiva no soportada: {op}")

    def _number_or_label(self, text: str, late: bool = False) -> int:
        try:
            return int(text, 0)
        except ValueError:
            pass
        name, sign, offset = text.partition("+")
        if name.strip() in self.labels:
            return self.labels[name.strip()] + (int(offset, 0) if sign else 0)
        if late:
            self._fixups.append((len(self._data), text))
            return 0
        raise SimulatorError(f"simbolo no definido: {text}")

    def _reg(self, text: str) -> int:
        if text not in _REG:
            raise SimulatorError(f"registro desconocido: {text}")
        return _REG[text]

    def _value(self, text: str):
        """Operando que puede ser registro o inmediato: ('r', n) o ('i', valor)."""
        if text.startswith("$"):
            return ("r", self._reg(text))
        return ("i", self._number_or_label(text))

    def _address(self, text: str) -> tuple[int, int]:
        """Operando de memoria: (desplazamiento, registro base). `etiqueta` usa base $zero."""
        match = _MEMORY.match(text.replace(" ", ""))
        if match:
            offset = match.group("offset")
            return (self._number_or_label(offset) if offset else 0, self._reg(match.group("base")))
        return (self._number_or_label(text), 0)

    def _target(self, name: str) -> int:
        if name not in self._text_labels:
            raise SimulatorError(f"etiqueta de codigo no definida: {name}")
        return self._text_labels[name]

    def _decode(self, line):
        op, a = line.op, line.args
        try:
            if op in _ARITHMETIC:
                return (line, "arith", (_ARITHMETIC[op], self._reg(a[0]), self._reg(a[1]), self._value(a[2])))
            if op in _BRANCH2:
                return (line, "branch2", (_BRANCH2[op], self._reg(a[0]), self._value(a[1]), self._target(a[2])))
            if op in _BRANCH1:
                return (line, "branch1", (_BRANCH1[op], self._reg(a[0]), self._target(a[1])))
            if op in _LOADS:
                return (line, "load", (*_LOADS[op], self._reg(a[0]), self._address(a[1])))
            if op in _STORES:
                return (line, "store", (_STORES[op], self._reg(a[0]), self._address(a[1])))
            if op == "li":
                return (line, "li", (self._reg(a[0]), self._number_or_label(a[1])))
            if op == "la":
                return (line, "la", (self._reg(a[0]), self._address(a[1])))
            if op == "lui":
                return (line, "li", (self._reg(a[0]), int(a[1], 0) << 16))
            if op == "move":
                return (line, "move", (self._reg(a[0]), self._reg(a[1])))
            if op in ("neg", "negu"):
                return (line, "arith", (_ARITHMETIC["sub"], self._reg(a[0]), 0, ("r", self._reg(a[1]))))
            if op == "not":
                return (line, "arith", (_ARITHMETIC["nor"], self._reg(a[0]), self._reg(a[1]), ("i", 0)))
            if op in ("j", "b"):
                return (line, "jump", (self._target(a[0]),))
            if op == "jal":
                return (line, "jal", (self._target(a[0]), a[0]))
            if op == "jr":
                return (line, "jr", (self._reg(a[0]),))
            if op == "jalr":
                return (line, "jalr", (self._reg(a[-1]),))
            if op in ("div", "divu", "rem") and len(a) == 3:
                return (line, "div3", (op, self._reg(a[0]), self._reg(a[1]), self._value(a[2])))
            if op in ("div", "divu", "mult", "multu"):
                return (line, op, (self._reg(a[0]), self._reg(a[1])))
            if op in ("mfhi", "mflo", "mthi", "mtlo"):
                return (line, op, (self._reg(a[0]),))
            if op in ("syscall", "nop"):
                return (line, op, ())
        except IndexError:
            raise SimulatorError(f"faltan operandos: {line.to_text().strip()}") from None
        raise SimulatorError(f"instruccion no soportada: {line.to_text().strip()}")

    # ------------------------------------------------------------------ memoria
    def _locate(self, address: int, size: int) -> tuple[bytearray, int]:
        address = _unsigned(address)
        if size > 1 and address % size:
            raise SimulatorError(f"direccion no alineada: 0x{address:08x}")
        if DATA_BASE <= address and address + size <= DATA_BASE + len(self._data):
            return self._data, address - DATA_BASE
        if HEAP_BASE <= address and address + size <= HEAP_BASE + len(self._heap):
            return self._heap, address - HEAP_BASE
        stack_base = STACK_TOP + 4 - STACK_SIZE
        if stack_base <= address and address + size <= STACK_TOP + 4:
            return self._stack, address - stack_base
        raise SimulatorError(f"acceso a memoria invalido: 0x{address:08x}")

    def read(self, address: int, size: int = 4, signed: bool = True) -> int:
        memory, position = self._locate(address, size)
        return int.from_bytes(memory[position : position + size], "little", signed=signed)

    def write(self, address: int, value: int, size: int = 4) -> None:
        memory, position = self._locate(address, size)
        memory[position : position + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")

    def read_string(self, address: int) -> str:
        data = bytearray()
        while True:
            byte = self.read(address, 1, signed=False)
            if byte == 0:
                return data.decode("utf-8", errors="replace")
            data.append(byte)
            address += 1

    # ------------------------------------------------------------------ ejecucion
    def run(self) -> str:
        """Ejecuta hasta la llamada al sistema de salida y devuelve lo que se imprimio."""
        registers = self.registers
        code = self.code
        while self.exit_code is None:
            if self.pc >= len(code):
                raise SimulatorError("la ejecucion paso el final del programa sin terminar")
            self.steps += 1
            if self.steps > self.step_limit:
                raise SimulatorError("el programa no termina (limite de pasos)")
            _, kind, args = code[self.pc]
            self.pc += 1
            if kind == "arith":
                function, target, left, right = args
                value = registers[right[1]] if right[0] == "r" else right[1]
                registers[target] = _signed(function(registers[left], value))
            elif kind == "load":
                size, signed, target, (offset, base) = args
                registers[target] = self.read(registers[base] + offset, size, signed)
            elif kind == "store":
                size, source, (offset, base) = args
                self.write(registers[base] + offset, registers[source], size)
            elif kind == "branch1":
                test, reg, target = args
                if test(registers[reg]):
                    self.pc = target
            elif kind == "branch2":
                test, reg, right, target = args
                if test(registers[reg], registers[right[1]] if right[0] == "r" else right[1]):
                    self.pc = target
            elif kind == "li":
                registers[args[0]] = _signed(args[1])
            elif kind == "la":
                offset, base = args[1]
                registers[args[0]] = _signed(registers[base] + offset)
            elif kind == "move":
                registers[args[0]] = registers[args[1]]
            elif kind == "jump":
                self.pc = args[0]
            elif kind == "jal":
                registers[RA] = TEXT_BASE + 4 * self.pc
                self._enter(args[1])
                self.pc = args[0]
            elif kind == "jalr":
                target = registers[args[0]]
                registers[RA] = TEXT_BASE + 4 * self.pc
                self._enter(self._label_at(target))
                self.pc = self._index(target)
            elif kind == "jr":
                target = registers[args[0]]
                if args[0] == RA:
                    self._leave(target)
                self.pc = self._index(target)
            elif kind in ("div", "divu"):
                a, b = registers[args[0]], registers[args[1]]
                if kind == "divu":
                    a, b = _unsigned(a), _unsigned(b)
                if b != 0:  # con divisor cero HI y LO quedan indefinidos, como en el procesador
                    self.lo, self.hi = (_signed(x) for x in _truncated_division(a, b))
            elif kind == "div3":
                name, target, left, right = args
                a = registers[left]
                b = registers[right[1]] if right[0] == "r" else right[1]
                if b == 0:
                    raise SimulatorError("division por cero")
                quotient, remainder = _truncated_division(a, b)
                registers[target] = _signed(remainder if name == "rem" else quotient)
            elif kind in ("mult", "multu"):
                a, b = registers[args[0]], registers[args[1]]
                product = _unsigned(a) * _unsigned(b) if kind == "multu" else a * b
                self.lo, self.hi = _signed(product), _signed(product >> 32)
            elif kind == "mflo":
                registers[args[0]] = self.lo
            elif kind == "mfhi":
                registers[args[0]] = self.hi
            elif kind == "mtlo":
                self.lo = registers[args[0]]
            elif kind == "mthi":
                self.hi = registers[args[0]]
            elif kind == "syscall":
                self._syscall()
            registers[0] = 0
        return self.output

    def _index(self, address: int) -> int:
        index = (_unsigned(address) - TEXT_BASE) // 4
        if _unsigned(address) % 4 or not 0 <= index <= len(self.code):
            raise SimulatorError(f"salto a una direccion que no es codigo: 0x{_unsigned(address):08x}")
        return index

    def _label_at(self, address: int) -> str:
        index = self._index(address)
        return next((name for name, position in self._text_labels.items() if position == index), "")

    def _syscall(self) -> None:
        service = self.registers[V0]
        argument = self.registers[A0]
        if service == 1:
            self._out += str(argument).encode()
        elif service == 4:
            self._out += self.read_string(argument).encode("utf-8")
        elif service == 11:
            self._out.append(argument & 0xFF)
        elif service == 9:
            if argument < 0 or len(self._heap) + argument > HEAP_LIMIT:
                raise SimulatorError("no hay memoria para sbrk")
            self.registers[V0] = _signed(HEAP_BASE + len(self._heap))
            self._heap += bytes(argument + (-argument % 4))
        elif service == 10:
            self.exit_code = 0
        elif service == 17:
            self.exit_code = argument
        else:
            raise SimulatorError(f"llamada al sistema no soportada: {service}")

    # ------------------------------------------------------------------ arbol de activacion
    def _format(self, value: int, type_name: str) -> str:
        if type_name == "boolean":
            return "true" if value else "false"
        if type_name == "string":
            return "null" if value == 0 else '"' + self.read_string(value) + '"'
        if type_name == "integer":
            return str(value)
        return "null" if value == 0 else f"0x{_unsigned(value):08x}"

    def _enter(self, label: str) -> None:
        info = self.functions.get(label)
        if info is None:
            return
        stack = self.registers[SP]
        params = info["params"]
        arguments = [
            self._format(self.read(stack + 4 * (len(params) - 1 - position)), param["type"])
            for position, param in enumerate(params)
        ]
        node = Activation(
            info["name"], arguments, None, info["frameSize"], [], info.get("returns", "void"), self.registers[RA], stack
        )
        self._calls[-1].children.append(node)
        self._calls.append(node)

    def _leave(self, target: int) -> None:
        node = self._calls[-1]
        if len(self._calls) > 1 and node.return_address == target and node.stack_pointer == self.registers[SP]:
            if node.returns != "void":
                node.result = self._format(self.registers[V0], node.returns)
            self._calls.pop()

    def unwind(self, stack_pointer: int) -> None:
        """Cierra las activaciones cuyo registro quedo debajo de `stack_pointer` (lo usa try/catch)."""
        while len(self._calls) > 1 and self._calls[-1].stack_pointer < stack_pointer:
            self._calls.pop()


def run_mips(source: str, functions: dict[str, dict] | None = None, step_limit: int = 5_000_000) -> Simulator:
    """Ensambla y ejecuta; devuelve la maquina con `output`, `exit_code` y `root`."""
    machine = Simulator(source, functions, step_limit)
    machine.run()
    return machine
