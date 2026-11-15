"""Utilidades comunes de las reglas de mirilla: ventanas, efectos de las instrucciones y vida de registros."""
from __future__ import annotations

import re

from compiscript.backend.asm import COMMENT, INSTR, LABEL, Line

_REGISTER = re.compile(r"\$\w+")
_TEMPORARY = re.compile(r"\$t[0-9]")

INVERSE_BRANCH = {
    "beq": "bne", "bne": "beq", "beqz": "bnez", "bnez": "beqz", "bltz": "bgez", "bgez": "bltz",
    "blez": "bgtz", "bgtz": "blez", "blt": "bge", "bge": "blt", "ble": "bgt", "bgt": "ble",
    "bltu": "bgeu", "bgeu": "bltu", "bleu": "bgtu", "bgtu": "bleu", "bc1t": "bc1f", "bc1f": "bc1t",
}
BRANCHES = frozenset(INVERSE_BRANCH)

# Instrucciones cuyo primer argumento es el destino y el resto son fuentes.
_WRITES_FIRST = frozenset({
    "add", "addu", "sub", "subu", "mul", "and", "or", "xor", "nor", "slt", "sltu", "seq", "sne", "sgt",
    "sge", "sle", "sllv", "srlv", "srav", "addi", "addiu", "andi", "ori", "xori", "slti", "sltiu", "sll",
    "srl", "sra", "li", "la", "lui", "move", "neg", "negu", "not", "abs", "lw", "lb", "lbu", "lh", "lhu",
    "mfhi", "mflo", "mfc1",
})
_WRITES_NOTHING = frozenset({"sw", "sb", "sh", "j", "jr", "nop"} | BRANCHES)


def int_value(text: str):
    """El entero que representa `text`, o None si no es un literal."""
    try:
        return int(text, 0)
    except ValueError:
        return None


def registers_in(line: Line) -> set[str]:
    return {reg for reg in _REGISTER.findall(" ".join(line.args)) if reg != "$zero"}


def effects(line: Line):
    """(escribe, lee) de una instruccion conocida, o None si no se sabe."""
    op = line.op
    if op in _WRITES_FIRST and line.args:
        return {line.args[0]} - {"$zero"}, registers_in(Line(INSTR, op, line.args[1:]))
    if op in _WRITES_NOTHING:
        return set(), registers_in(line)
    return None


def is_temporary(reg: str) -> bool:
    return bool(_TEMPORARY.fullmatch(reg))


def is_dead(lines: list[Line], start: int, reg: str) -> bool:
    """El valor de `reg` no se lee en `lines[start:]`.

    Solo se contestan los `$t`. El generador vacia los descriptores de registros en cada etiqueta,
    salto y llamada a funcion del programa (guarda antes lo que sigue vivo), asi que un `$t` nunca
    lleva un valor a traves de ellos. Las rutinas de `runtime.py` (`_nombre`) conservan los `$t`.
    """
    if not is_temporary(reg):
        return False
    for line in lines[start:]:
        if line.kind == LABEL:
            return True
        if line.kind != INSTR:
            continue
        op, args = line.op, line.args
        if op == "j":
            return True
        if op in BRANCHES or op in ("jr", "jalr"):
            return reg not in registers_in(line)
        if op == "jal":
            if args[0].startswith("_"):
                continue
            return True
        known = effects(line)
        if known is None:
            if reg in registers_in(line):
                return False
            continue
        writes, reads = known
        if reg in reads:
            return False
        if reg in writes:
            return True
    return True


def next_instr(lines: list[Line], index: int):
    """Indice de la siguiente instruccion, saltando comentarios; None si antes hay una etiqueta o directiva."""
    for position in range(index + 1, len(lines)):
        kind = lines[position].kind
        if kind == INSTR:
            return position
        if kind != COMMENT:
            return None
    return None


def labels_after(lines: list[Line], index: int) -> set[str]:
    """Etiquetas que siguen a `lines[index]` antes de la proxima instruccion (comentarios aparte)."""
    found: set[str] = set()
    for line in lines[index + 1 :]:
        if line.kind == LABEL:
            found.add(line.op)
        elif line.kind != COMMENT:
            break
    return found


def jump_target(line: Line):
    """Etiqueta destino de un `j` o de un salto condicional; None en cualquier otro caso."""
    if line.kind == INSTR and (line.op == "j" or line.op in BRANCHES) and line.args:
        return line.args[-1]
    return None
