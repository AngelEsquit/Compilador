"""Reglas que aprovechan una constante recien cargada con `li` para usar la forma con inmediato."""
from __future__ import annotations

from dataclasses import replace

from compiscript.backend.asm import INSTR, Line
from compiscript.backend.peephole.analysis import int_value, is_dead, next_instr

ORDER = 3

_IMMEDIATE_RANGE = range(-32768, 32768)


def _constant_pairs(lines: list[Line]):
    """Pares (indice del `li`, indice de la instruccion siguiente) con un `li $r, constante`."""
    for index, line in enumerate(lines):
        if line.kind == INSTR and line.op == "li" and len(line.args) == 2 and int_value(line.args[1]) is not None:
            following = next_instr(lines, index)
            if following is not None:
                yield index, following


def _rewrite(lines: list[Line], rewrite) -> tuple[list[Line], int]:
    """Aplica `rewrite(li, siguiente, valor)`, que devuelve la instruccion nueva o None.

    El `li` se elimina cuando su registro ya no se lee: es el destino de la instruccion nueva o esta muerto.
    """
    out = list(lines)
    removed: set[int] = set()
    count = 0
    for load, following in _constant_pairs(lines):
        if load in removed or following in removed:
            continue
        register, value = lines[load].args[0], int_value(lines[load].args[1])
        new = rewrite(lines[following], register, value)
        if new is None:
            continue
        out[following] = new
        count += 1
        if new.args[0] == register or is_dead(lines, following + 1, register):
            removed.add(load)
    return [line for index, line in enumerate(out) if index not in removed], count


def strength_reduction(lines: list[Line]):
    """`li $t1, 8` / `mul $t0, $t0, $t1` se convierte en `sll $t0, $t0, 3`."""

    def rewrite(line: Line, register: str, value: int):
        if line.op != "mul" or len(line.args) != 3:
            return None
        dest, first, second = line.args
        if register not in (first, second) or first == second:
            return None
        other = first if second == register else second
        if value == 0:
            return replace(line, op="li", args=(dest, "0"))
        if value == 1:
            return replace(line, op="move", args=(dest, other))
        if value > 1 and value & (value - 1) == 0:
            return replace(line, op="sll", args=(dest, other, str(value.bit_length() - 1)))
        return None

    return _rewrite(lines, rewrite)


def compare_immediate(lines: list[Line]):
    """`li $t1, 3` / `slt $t0, $t0, $t1` se convierte en `slti $t0, $t0, 3`; `sle` usa `c + 1`."""

    def rewrite(line: Line, register: str, value: int):
        if line.op not in ("slt", "sle") or len(line.args) != 3:
            return None
        dest, left, right = line.args
        if right != register or left == register:
            return None
        bound = value + 1 if line.op == "sle" else value
        if bound not in _IMMEDIATE_RANGE:
            return None
        return replace(line, op="slti", args=(dest, left, str(bound)))

    return _rewrite(lines, rewrite)


def arithmetic_immediate(lines: list[Line]):
    """`li $t1, 5` / `addu $t0, $t0, $t1` se convierte en `addiu $t0, $t0, 5` (y `subu` en `addiu` con `-5`)."""

    def rewrite(line: Line, register: str, value: int):
        if line.op not in ("addu", "subu") or len(line.args) != 3:
            return None
        dest, left, right = line.args
        if line.op in ("addu",) and left == register and right != register:
            left, right = right, left
        if right != register or left == register:
            return None
        amount = value if line.op in ("addu",) else -value
        if amount not in _IMMEDIATE_RANGE:
            return None
        return replace(line, op="addiu", args=(dest, left, str(amount)))

    return _rewrite(lines, rewrite)


RULES = [
    ("reduccion de fuerza", strength_reduction),
    ("comparacion con inmediato", compare_immediate),
    ("aritmetica con inmediato", arithmetic_immediate),
]
