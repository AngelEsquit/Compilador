"""Aritmetica de punto flotante en MIPS.

Un `float` de Compiscript es un numero IEEE 754 de precision simple. Sus 32 bits viajan
por los mismos registros y casillas que un entero, asi que el asignador de registros no
distingue tipos. Solo al operar se pasan al coprocesador 1 (`$f0`, `$f2`), se calcula y
el resultado vuelve a un registro general.

El TAC no trae conversiones: cuando un entero llega a un lugar de tipo `float`
(operando, variable, argumento o valor de retorno) se convierte aqui con `cvt.s.w`.
"""
from __future__ import annotations

from compiscript.backend.asm import label
from compiscript.backend.operands import Const, UnsupportedFeature, float_bits
from compiscript.typesystem.types import FLOAT, INTEGER

_ARITHMETIC = {"+": "add.s", "-": "sub.s", "*": "mul.s", "/": "div.s"}
# operador -> (comparacion, operandos invertidos, salta si la condicion es verdadera)
_COMPARISON = {
    "<": ("c.lt.s", False, True),
    "<=": ("c.le.s", False, True),
    ">": ("c.lt.s", True, True),
    ">=": ("c.le.s", True, True),
    "==": ("c.eq.s", False, True),
    "!=": ("c.eq.s", False, False),
}


class FloatOps:
    _float_labels = 0

    def to_fp(self, token: str, fp_register: str) -> None:
        """Deja el operando en un registro de punto flotante, convirtiendolo si es entero."""
        operand = self.operand(token)
        is_integer = self.type_of(token) == INTEGER
        if isinstance(operand, Const):
            bits = float_bits(operand.text) if is_integer else operand.value
            self.emit("li", "$a0", str(bits))
            self.emit("mtc1", "$a0", fp_register)
            return
        self.emit("mtc1", self.regs.use(operand), fp_register)
        if is_integer:
            self.emit("cvt.s.w", fp_register, fp_register, comment="entero a float")

    def int_to_float(self, token: str, register: str) -> None:
        """Deja en `register` (auxiliar) los bits de float de un operando entero."""
        self.to_fp(token, "$f0")
        self.emit("mfc1", register, "$f0")

    def needs_widening(self, token: str, expected) -> bool:
        return expected == FLOAT and self.type_of(token) == INTEGER

    def _float_binary(self, ins) -> None:
        self.to_fp(ins.arg1, "$f0")
        self.to_fp(ins.arg2, "$f2")
        target = self.regs.define(self.operand(ins.result))
        if ins.op in _ARITHMETIC:
            self.emit(_ARITHMETIC[ins.op], "$f0", "$f0", "$f2")
            self.emit("mfc1", target, "$f0")
            return
        if ins.op not in _COMPARISON:
            raise UnsupportedFeature("float", ins.to_text())
        mnemonic, swapped, when_true = _COMPARISON[ins.op]
        done = f"_fc{FloatOps._float_labels}"
        FloatOps._float_labels += 1
        self.emit("li", target, "1")
        self.emit(mnemonic, *(("$f2", "$f0") if swapped else ("$f0", "$f2")))
        self.emit("bc1t" if when_true else "bc1f", done)
        self.emit("li", target, "0")
        self.asm.text.append(label(done))

    def _float_neg(self, ins) -> None:
        self.to_fp(ins.arg1, "$f0")
        self.emit("neg.s", "$f0", "$f0")
        self.emit("mfc1", self.regs.define(self.operand(ins.result)), "$f0")

    def _float_print(self, ins) -> None:
        self.to_fp(ins.arg1, "$f12")
        self.call_runtime("_print_float")
