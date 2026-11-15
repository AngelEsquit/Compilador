"""Generador de ensamblador MIPS32 a partir del TAC.

Convenciones (compatibles con MARS y SPIM):

- `$t0`-`$t9` son los registros que reparte el asignador (`registers.py`). Ninguno
  sobrevive a una llamada: antes de `jal` se guardan los valores vivos.
- `$a0`-`$a3`, `$v0` y `$v1` son auxiliares del generador y de la biblioteca de ejecucion.
- `$gp` apunta al area estatica (variables globales) y `$fp` al registro de activacion,
  con los offsets que calculo `symbols/layout.py`.
- Llamada: el llamador apila los argumentos de izquierda a derecha (4 bytes cada uno),
  deja el access_link en `$v1` si la funcion es anidada, hace `jal` y desapila. El valor
  de retorno llega en `$v0`. El llamado reserva su registro, guarda `$fp` y `$ra` y copia
  los argumentos a sus casillas de parametro.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiscript.backend import runtime
from compiscript.backend.asm import AsmProgram, Line, comment, instr, label
from compiscript.backend.blocks import TERMINATORS, liveness, next_uses, split_blocks
from compiscript.backend.classes import ClassOps
from compiscript.backend.exceptions import ExceptionOps
from compiscript.backend.floats import FloatOps
from compiscript.backend.operands import (
    ARITHMETIC,
    CALLS,
    COMPARISON,
    Const,
    Resolver,
    UnsupportedFeature,
    Var,
    access_size,
)
from compiscript.backend.registers import ALLOCATABLE, RegisterAllocator
from compiscript.typesystem.types import BOOLEAN, FLOAT, STRING, NullType

SAVED_FP, RETURN_ADDRESS, ACCESS_LINK = 0, 8, 16  # area de control del registro
ARG_SIZE = 4
ARRAY_HEADER = 4  # palabra con la longitud
ELEMENT_SIZE = 4

_BINARY = {"+": "addu", "-": "subu", "*": "mul"}
_COMPARE = {"<": "slt", "<=": "sle", ">": "sgt", ">=": "sge", "==": "seq", "!=": "sne"}
_SILENT = frozenset({"function", "param_decl", "label"})


def fits_immediate(value: int) -> bool:
    return -32768 <= value <= 32767


@dataclass
class AsmResult:
    program: AsmProgram
    # etiqueta MIPS -> {name, params, frameSize}; lo usa el simulador para el arbol de activacion
    functions: dict[str, dict] = field(default_factory=dict)
    allocation: list[dict] = field(default_factory=list)  # bitacora del asignador de registros
    peephole: dict[str, int] = field(default_factory=dict)  # veces que se aplico cada transformacion
    registers: tuple[str, ...] = ALLOCATABLE

    @property
    def text(self) -> str:
        return self.program.to_text()


class MipsGenerator(ClassOps, ExceptionOps, FloatOps):
    def __init__(self, program, analyzer, registers=ALLOCATABLE) -> None:
        self.tac = program
        self.layout = analyzer.layout
        self.resolver = Resolver(self.layout, analyzer.global_scope)
        self.asm = AsmProgram()
        self.regs = RegisterAllocator(registers, self.emit)
        self.runtime: set[str] = set()
        self.functions: dict[str, dict] = {}
        self._labels: dict[str, str] = {}
        self.record = None
        self.ins = None
        self.uses: list[Var] = []
        self.defs: list[Var] = []
        self.live_out: set = set()
        self.label_live: dict[str, set] = {}  # etiqueta -> variables vivas al llegar a ella
        self.position = 0  # indice de la instruccion en curso dentro de su funcion
        self.argument_types: dict[int, object] = {}  # posicion de un `param` -> tipo del parametro formal
        self.return_label = ""

    # ------------------------------------------------------------------ utilidades
    def emit(self, op: str, *args: str, comment: str = "") -> None:
        self.asm.text.append(instr(op, *args, comment=comment))

    def call_runtime(self, name: str) -> None:
        self.runtime.add(name)
        self.emit("jal", name)

    def branch_runtime(self, op: str, *args: str) -> None:
        """Salto condicional a una rutina de error (`_div_zero`, `_index_error`, `_null_error`)."""
        self.runtime.add(args[-1])
        self.emit(op, *args)

    def function_label(self, name: str) -> str:
        """Etiqueta MIPS de una funcion del TAC (`Clase.metodo` pasa a `f_Clase_metodo`)."""
        if name not in self._labels:
            base = "f_" + name.replace(".", "_").replace("#", "_")
            candidate, copy = base, 2
            while candidate in self._labels.values():
                candidate, copy = f"{base}_{copy}", copy + 1
            self._labels[name] = candidate
        return self._labels[name]

    def operand(self, token: str):
        return self.resolver.operand(token, self.ins)

    def type_of(self, token: str):
        return self.resolver.type_of(token, self.ins)

    def load_const(self, reg: str, const: Const) -> None:
        if const.is_label:
            self.emit("la", reg, const.text)
        elif const.value == 0:
            self.emit("move", reg, "$zero")
        else:
            self.emit("li", reg, const.text)

    def move_to(self, reg: str, token: str) -> None:
        """Deja el valor de un operando en un registro auxiliar (`$a0`, `$v0`...)."""
        operand = self.operand(token)
        if isinstance(operand, Const):
            self.load_const(reg, operand)
        else:
            self.emit("move", reg, self.regs.use(operand))

    def result(self, token: str, source: str = "$v0") -> None:
        """Asigna a `token` el valor que una llamada o rutina dejo en `source`."""
        var = self.operand(token)
        if var in self.regs.after:
            self.emit("move", self.regs.define(var), source)

    def frame_pointer(self, hops: int) -> str:
        """Deja en `$a0` el `fp` del registro que esta `hops` niveles lexicos arriba."""
        if self.record.level - hops <= 0:
            self.emit("lw", "$a0", f"{self.resolver.main_fp_offset}($gp)", comment="registro de main")
            return "$a0"
        self.emit("lw", "$a0", f"{ACCESS_LINK}($fp)", comment="access_link")
        for _ in range(hops - 1):
            self.emit("lw", "$a0", f"{ACCESS_LINK}($a0)")
        return "$a0"

    # ------------------------------------------------------------------ programa
    def generate(self) -> AsmResult:
        units = self._units()
        self.resolver.mark_captured(self.tac.instructions)
        for name, instructions in units:
            self._unit(name, instructions)
        text, data = runtime.runtime_lines(self.runtime)
        self.asm.text += text
        self.asm.data = self._data() + data
        return AsmResult(self.asm, self.functions, self.regs.events, registers=self.regs.registers)

    def _units(self) -> list[tuple[str, list]]:
        """Separa el TAC en el programa principal y cada cuerpo de funcion."""
        units: list[tuple[str, list]] = []
        current: list = []
        name = "main"
        for ins in self.tac.instructions:
            if ins.op == "function":
                name, current = ins.result, []
            current.append(ins)
            if ins.op in ("halt", "end_function"):
                units.append((name, current))
                current = []
        return units

    def _data(self) -> list[Line]:
        lines = [label("_static"), Line("directive", ".space", (str(self.resolver.static_size),))]
        for literal, name in self.resolver.strings.items():
            lines += [label(name), Line("directive", ".asciiz", (literal,))]
        return lines + self.class_data()

    def _unit(self, name: str, instructions: list) -> None:
        record = self.layout.records[name]
        self.record = record
        self.resolver.enter(record)
        self.regs.context = name
        info = [self.resolver.uses_defs(ins) for ins in instructions]
        # Una llamada puede leer cualquier global o variable capturada: deben estar en memoria.
        shared = sorted(
            {v for uses, defs in info for v in (*uses, *defs) if v.kind == "global" or v.captured},
            key=lambda v: (v.base, v.offset),
        )
        for position, ins in enumerate(instructions):
            if ins.op in CALLS:
                info[position] = (info[position][0] + shared, info[position][1])
        blocks = split_blocks(instructions)
        liveness(blocks, info, {v for v in shared if v.kind == "global"})
        self.label_live = {
            instructions[block.start].result: block.live_in
            for block in blocks
            if instructions[block.start].op == "label"
        }

        self.argument_types = self._argument_types(instructions)
        self._prologue(name, record, instructions)
        for block in blocks:
            after = next_uses(block, info)
            self.regs.reset()
            self.live_out = block.live_out
            for position in range(block.start, block.end):
                self.position = position
                self.ins = ins = instructions[position]
                self.uses, self.defs = info[position]
                self.regs.begin(after[position - block.start], self.uses)
                if ins.op not in _SILENT:
                    self.asm.text.append(comment(ins.to_text()))
                self._translate(ins)
                self.resolver.observe(ins)
            if instructions[block.end - 1].op not in TERMINATORS:
                self.regs.flush(self.live_out)

    def _argument_types(self, instructions) -> dict[int, object]:
        """Tipo que espera el llamado para cada `param`: sirve para convertir enteros a float."""
        expected: dict[int, object] = {}
        pending: list[int] = []
        for position, ins in enumerate(instructions):
            if ins.op == "param":
                pending.append(position)
            elif ins.op in CALLS:
                count = int(ins.arg2)
                arguments = pending[len(pending) - count :] if count else []
                del pending[len(pending) - count :]
                for argument, formal in zip(arguments, self._formal_types(ins)):
                    expected[argument] = formal
        return expected

    def _formal_types(self, ins) -> list:
        if ins.op == "call_result":
            function = self.resolver.functions.get(ins.arg1)
        elif ins.op == "new":
            cls = self.resolver.classes.get(ins.arg1)
            while cls is not None and cls.constructor is None:
                cls = cls.superclass
            function = cls.constructor if cls is not None else None
        else:
            receiver, method = ins.arg1.rsplit(".", 1)
            owner = self.resolver.type_of(receiver, ins)
            cls = self.resolver.classes.get(getattr(owner, "class_name", ""))
            function = cls.resolve_member(method) if cls is not None else None
            if function is not None:
                return [owner] + [p.decl_type for p in getattr(function, "parameters", [])]
        return [p.decl_type for p in function.parameters] if function is not None else []

    def _translate(self, ins) -> None:
        if ins.op in ARITHMETIC or ins.op in COMPARISON:
            self._op_binary(ins)
        else:
            getattr(self, f"_op_{ins.op}")(ins)

    # ------------------------------------------------------------------ registro de activacion
    def _prologue(self, name: str, record, instructions) -> None:
        size = record.frame_size
        if name == "main":
            self.asm.text.append(label("main"))
            self.emit("la", "$gp", "_static", comment="area estatica")
            self.emit("addiu", "$sp", "$sp", str(-size), comment=f"registro de main: {size} bytes")
            self.emit("move", "$fp", "$sp")
            self.emit("sw", "$fp", f"{self.resolver.main_fp_offset}($gp)")
            self.functions["main"] = {"name": "main", "params": [], "frameSize": size}
            return
        mips_label = self.function_label(name)
        self.return_label = f"{mips_label}_fin"
        self.asm.text.append(label(mips_label))
        self.emit("addiu", "$sp", "$sp", str(-size), comment=f"registro de {name}: {size} bytes")
        self.emit("sw", "$fp", f"{SAVED_FP}($sp)", comment="saved_fp")
        self.emit("sw", "$ra", f"{RETURN_ADDRESS}($sp)", comment="return_address")
        if record.level >= 2:
            self.emit("sw", "$v1", f"{ACCESS_LINK}($sp)", comment="access_link")
        self.emit("move", "$fp", "$sp")
        params = [ins.arg1 for ins in instructions if ins.op == "param_decl"]
        slots = {slot.name: slot for slot in record.params}
        for position, param in enumerate(params):
            slot = slots[param]
            incoming = size + ARG_SIZE * (len(params) - 1 - position)
            self.emit("lw", "$a0", f"{incoming}($fp)")
            store = "sb" if access_size(slot.size) == 1 else "sw"
            self.emit(store, "$a0", f"{slot.offset}($fp)", comment=f"parametro {param}")
        symbol = self.resolver.functions.get(name)
        returns = symbol.return_type if symbol is not None and symbol.return_type is not None else None
        self.functions[mips_label] = {
            "name": name,
            "params": [{"name": p, "type": slots[p].type_name} for p in params],
            "returns": returns.name if returns is not None else "void",
            "frameSize": size,
        }

    def _op_function(self, ins) -> None:
        pass

    def _op_param_decl(self, ins) -> None:
        pass

    def _op_end_function(self, ins) -> None:
        self.regs.flush(self.live_out)
        self.asm.text.append(label(self.return_label))
        self.emit("lw", "$ra", f"{RETURN_ADDRESS}($fp)")
        self.emit("lw", "$fp", f"{SAVED_FP}($fp)")
        self.emit("addiu", "$sp", "$sp", str(self.record.frame_size))
        self.emit("jr", "$ra")

    def _op_return(self, ins) -> None:
        if ins.arg1:
            function = self.resolver.functions.get(self.record.name)
            if function is not None and self.needs_widening(ins.arg1, function.return_type):
                self.int_to_float(ins.arg1, "$v0")
            else:
                self.move_to("$v0", ins.arg1)
        self.regs.flush(self.live_out)
        self.emit("j", self.return_label)

    def _op_halt(self, ins) -> None:
        self.emit("li", "$v0", "10")
        self.emit("syscall")

    # ------------------------------------------------------------------ llamadas
    def _op_param(self, ins) -> None:
        if self.needs_widening(ins.arg1, self.argument_types.get(self.position)):
            reg = "$a0"
            self.int_to_float(ins.arg1, reg)
        else:
            reg = self.regs.use(self.operand(ins.arg1))
        self.emit("addiu", "$sp", "$sp", str(-ARG_SIZE))
        self.emit("sw", reg, "0($sp)", comment=f"argumento {ins.arg1}")

    def _op_link(self, ins) -> None:
        hops = int(ins.arg1)
        if hops == 0:
            self.emit("move", "$v1", "$fp", comment="access_link: este registro")
            return
        self.emit("lw", "$v1", f"{ACCESS_LINK}($fp)", comment="access_link")
        for _ in range(hops - 1):
            self.emit("lw", "$v1", f"{ACCESS_LINK}($v1)")

    def save_for_call(self) -> None:
        """Antes de `jal`: guarda lo que sigue vivo y lo que el llamado puede leer."""
        live = (set(self.regs.after) - set(self.defs)) | set(self.uses)
        self.regs.flush(live)

    def pop_arguments(self, count: int) -> None:
        if count:
            self.emit("addiu", "$sp", "$sp", str(ARG_SIZE * count))

    def _op_call_result(self, ins) -> None:
        self.save_for_call()
        self.emit("jal", self.function_label(ins.arg1))
        self.pop_arguments(int(ins.arg2))
        self.result(ins.result)

    # ------------------------------------------------------------------ datos
    def _op_copy(self, ins) -> None:
        source, target = self.operand(ins.arg1), self.operand(ins.result)
        symbol = self.resolver.symbol(ins.result, ins)
        if symbol is not None and self.needs_widening(ins.arg1, symbol.decl_type):
            self.int_to_float(ins.arg1, "$a0")
            self.emit("move", self.regs.define(target), "$a0")
        elif isinstance(source, Const):
            self.load_const(self.regs.define(target), source)
        else:
            self.regs.alias(target, self.regs.use(source))

    def _op_binary(self, ins) -> None:
        kinds = (self.type_of(ins.arg1), self.type_of(ins.arg2))
        if STRING in kinds:
            return self._string_binary(ins)
        if FLOAT in kinds:
            return self._float_binary(ins)
        op = ins.op
        left, right = self.operand(ins.arg1), self.operand(ins.arg2)
        if op == "+" and isinstance(left, Const) and not isinstance(right, Const):
            left, right = right, left
        target = self.operand(ins.result)
        if op in "+-" and isinstance(right, Const) and not right.is_label:
            value = right.value if op == "+" else -right.value
            if fits_immediate(value):
                source = self.regs.use(left)
                self.emit("addiu", self.regs.define(target), source, str(value))
                return
        first, second = self.regs.use(left), self.regs.use(right)
        if op in "/%":
            if not (isinstance(right, Const) and right.value != 0):
                self.before_throwing()
                self.branch_runtime("beqz", second, "_div_zero")
            self.emit("div", first, second)
            self.emit("mflo" if op == "/" else "mfhi", self.regs.define(target))
        else:
            mnemonic = _BINARY.get(op) or _COMPARE[op]
            self.emit(mnemonic, self.regs.define(target), first, second)

    def _string_binary(self, ins) -> None:
        routines = {"+": "_concat", "==": "_streq", "!=": "_streq"}
        if ins.op not in routines:
            raise UnsupportedFeature("cadenas", ins.to_text())
        self.move_to("$a0", ins.arg1)
        self.move_to("$a1", ins.arg2)
        self.call_runtime(routines[ins.op])
        target = self.operand(ins.result)
        if ins.op == "!=":
            self.emit("xori", self.regs.define(target), "$v0", "1")
        else:
            self.emit("move", self.regs.define(target), "$v0")

    def _op_neg(self, ins) -> None:
        if self.type_of(ins.arg1) == FLOAT:
            return self._float_neg(ins)
        source = self.regs.use(self.operand(ins.arg1))
        self.emit("subu", self.regs.define(self.operand(ins.result)), "$zero", source)

    def _op_not(self, ins) -> None:
        source = self.regs.use(self.operand(ins.arg1))
        self.emit("xori", self.regs.define(self.operand(ins.result)), source, "1")

    def _op_print(self, ins) -> None:
        kind = self.type_of(ins.arg1)
        if kind == FLOAT:
            return self._float_print(ins)
        if kind == STRING or isinstance(kind, NullType):
            routine = "_print_str"
        elif kind == BOOLEAN:
            routine = "_print_bool"
        else:
            routine = "_print_int"
        self.move_to("$a0", ins.arg1)
        self.call_runtime(routine)

    # ------------------------------------------------------------------ control de flujo
    def _op_label(self, ins) -> None:
        self.asm.text.append(label(ins.result))

    def _op_goto(self, ins) -> None:
        self.regs.flush(self.live_out)
        self.emit("j", ins.result)

    def _conditional(self, ins, when_true: bool) -> None:
        operand = self.operand(ins.arg1)
        if isinstance(operand, Const):
            self.regs.flush(self.live_out)
            if (operand.value != 0) == when_true:
                self.emit("j", ins.result)
            return
        reg = self.regs.use(operand)
        self.regs.flush(self.live_out)
        self.emit("bnez" if when_true else "beqz", reg, ins.result)

    def _op_if(self, ins) -> None:
        self._conditional(ins, True)

    def _op_ifFalse(self, ins) -> None:
        self._conditional(ins, False)

    # ------------------------------------------------------------------ closures
    def _op_env_load(self, ins) -> None:
        symbol = self.resolver.symbol(ins.arg2, ins)
        base = self.frame_pointer(int(ins.arg1))
        load = "lbu" if access_size(symbol.size) == 1 else "lw"
        self.emit(load, self.regs.define(self.operand(ins.result)), f"{symbol.offset}({base})", comment=ins.arg2)

    def _op_env_store(self, ins) -> None:
        symbol = self.resolver.symbol(ins.result, ins)
        value = self.regs.use(self.operand(ins.arg1))
        base = self.frame_pointer(int(ins.arg2))
        store = "sb" if access_size(symbol.size) == 1 else "sw"
        self.emit(store, value, f"{symbol.offset}({base})", comment=ins.result)

    # ------------------------------------------------------------------ arreglos
    # Un arreglo es un bloque del monticulo: la longitud en la primera palabra y despues
    # los elementos, de 4 bytes cada uno.
    def _op_array(self, ins) -> None:
        items = ins.arg1.split(", ") if ins.arg1 else []
        self.emit("li", "$a0", str(ARRAY_HEADER + ELEMENT_SIZE * len(items)))
        self.call_runtime("_alloc")
        self.emit("li", "$a0", str(len(items)))
        self.emit("sw", "$a0", "0($v0)", comment="longitud")
        for position, item in enumerate(items):
            reg = self.regs.use(self.operand(item))
            self.emit("sw", reg, f"{ARRAY_HEADER + ELEMENT_SIZE * position}($v0)")
            self.regs.unpin()
        self.emit("move", self.regs.define(self.operand(ins.result)), "$v0")

    def _op_length(self, ins) -> None:
        array = self.regs.use(self.operand(ins.arg1))
        self.before_throwing()
        self.branch_runtime("beqz", array, "_null_error")
        self.emit("lw", self.regs.define(self.operand(ins.result)), f"0({array})")

    def _element(self, array: str, index: str) -> str:
        """Comprueba null e indice y devuelve la direccion del elemento como `4($a1)`."""
        self.before_throwing()
        self.branch_runtime("beqz", array, "_null_error")
        self.emit("lw", "$a0", f"0({array})", comment="longitud")
        self.branch_runtime("bgeu", index, "$a0", "_index_error")  # sin signo: tambien rechaza negativos
        self.emit("sll", "$a1", index, "2")
        self.emit("addu", "$a1", "$a1", array)
        return f"{ARRAY_HEADER}($a1)"

    def _op_index_load(self, ins) -> None:
        array, index = self.regs.use(self.operand(ins.arg1)), self.regs.use(self.operand(ins.arg2))
        address = self._element(array, index)
        self.emit("lw", self.regs.define(self.operand(ins.result)), address)

    def _op_index_store(self, ins) -> None:
        array, index = self.regs.use(self.operand(ins.result)), self.regs.use(self.operand(ins.arg1))
        value = self.regs.use(self.operand(ins.arg2))
        self.emit("sw", value, self._element(array, index))


def generate_mips(program, analyzer, registers=ALLOCATABLE) -> AsmResult:
    """Traduce un `TACProgram` ya generado. `analyzer` aporta ambitos y registros de activacion."""
    analyzer.layout.apply_temps(program.temp_counts)
    return MipsGenerator(program, analyzer, registers).generate()

