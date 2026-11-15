"""Reglas sobre el flujo de control: saltos innecesarios, saltos encadenados y codigo inalcanzable."""
from __future__ import annotations

from dataclasses import replace

from compiscript.backend.asm import COMMENT, DIRECTIVE, INSTR, LABEL, Line
from compiscript.backend.peephole.analysis import (
    BRANCHES,
    INVERSE_BRANCH,
    jump_target,
    labels_after,
    next_instr,
)

ORDER = 1


def jump_to_next(lines: list[Line]):
    """`j L` (o un salto condicional) seguido de `L:` no hace nada: se elimina el salto."""
    out: list[Line] = []
    count = 0
    for index, line in enumerate(lines):
        target = jump_target(line)
        if target is not None and target in labels_after(lines, index):
            count += 1
            continue
        out.append(line)
    return out, count


def jump_over_jump(lines: list[Line]):
    """`beqz r, L1` / `j L2` / `L1:` se convierte en `bnez r, L2` / `L1:`."""
    out: list[Line] = []
    skipped: set[int] = set()
    count = 0
    for index, line in enumerate(lines):
        if index in skipped:
            continue
        jump = next_instr(lines, index) if line.kind == INSTR and line.op in BRANCHES else None
        if jump is not None and lines[jump].op == "j" and line.args[-1] in labels_after(lines, jump):
            line = replace(line, op=INVERSE_BRANCH[line.op], args=line.args[:-1] + (lines[jump].args[0],))
            skipped.add(jump)
            count += 1
        out.append(line)
    return out, count


def unreachable_code(lines: list[Line]):
    """Las instrucciones entre un `j` o `jr` y la siguiente etiqueta no se pueden ejecutar."""
    out: list[Line] = []
    count = 0
    dead = False
    for line in lines:
        if line.kind == INSTR and dead:
            count += 1
            continue
        if line.kind in (LABEL, DIRECTIVE):
            dead = False
        elif line.kind == INSTR:
            dead = line.op in ("j", "jr")
        out.append(line)
    return out, count


def chained_jumps(lines: list[Line]):
    """Un salto a una etiqueta cuya primera instruccion es `j L2` salta directo a `L2`."""
    alias: dict[str, str] = {}
    for index, line in enumerate(lines):
        if line.kind != LABEL:
            continue
        following = next((nxt for nxt in lines[index + 1 :] if nxt.kind not in (COMMENT, LABEL)), None)
        if following is not None and following.kind == INSTR and following.op == "j":
            alias[line.op] = following.args[0]

    def final(label: str) -> str:
        seen = {label}
        while label in alias and alias[label] not in seen:
            label = alias[label]
            seen.add(label)
        return label

    out: list[Line] = []
    count = 0
    for line in lines:
        target = jump_target(line)
        if target is not None and final(target) != target:
            line = replace(line, args=line.args[:-1] + (final(target),))
            count += 1
        out.append(line)
    return out, count


RULES = [
    ("salto a la siguiente instruccion", jump_to_next),
    ("salto sobre salto", jump_over_jump),
    ("codigo inalcanzable", unreachable_code),
    ("saltos encadenados", chained_jumps),
]
