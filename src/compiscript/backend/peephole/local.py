"""Reglas locales sobre pares de instrucciones contiguas: identidades, cargas y movimientos redundantes."""
from __future__ import annotations

from dataclasses import replace

from compiscript.backend.asm import INSTR, Line
from compiscript.backend.peephole.analysis import effects, int_value, is_dead, next_instr

ORDER = 2

_IDENTITY_IMMEDIATE = frozenset({"addiu", "addi", "ori", "xori", "sll", "srl", "sra"})
_IDENTITY_REGISTER = frozenset({"addu", "add", "subu", "sub", "or", "xor"})
_COMMUTATIVE = frozenset({"addu", "add", "or", "xor"})
# Instrucciones reales de un solo destino: se puede cambiar el destino sin alterar lo que leen.
_RETARGETABLE = frozenset({
    "li", "la", "lw", "lb", "lbu", "move", "addiu", "addu", "subu", "mul", "sll", "srl", "sra", "slt", "slti",
    "and", "or", "xor", "andi", "ori", "xori",
})


def _move(line: Line, dest: str, source: str) -> Line:
    return replace(line, op="move", args=(dest, source))


def algebraic_identity(lines: list[Line]):
    """`addiu $t0, $t0, 0`, `move $t0, $t0`, `sll $t0, $t0, 0`... no hacen nada; con otro destino son un `move`."""
    out: list[Line] = []
    count = 0
    for line in lines:
        op, args = line.op, line.args
        if line.kind == INSTR and op == "move" and args[0] == args[1]:
            count += 1
            continue
        if line.kind == INSTR and len(args) == 3:
            neutral = None
            if op in _IDENTITY_IMMEDIATE and int_value(args[2]) == 0:
                neutral = args[1]
            elif op in _IDENTITY_REGISTER and args[2] == "$zero":
                neutral = args[1]
            elif op in _COMMUTATIVE and args[1] == "$zero":
                neutral = args[2]
            if neutral is not None:
                count += 1
                if neutral != args[0]:
                    out.append(_move(line, args[0], neutral))
                continue
        out.append(line)
    return out, count


def redundant_load(lines: list[Line]):
    """`sw $t0, M` seguido de `lw $t0, M` (o dos `lw` de la misma casilla) repite un valor ya cargado."""
    out: list[Line] = []
    skipped: set[int] = set()
    count = 0
    for index, line in enumerate(lines):
        if index in skipped:
            continue
        out.append(line)
        if line.kind != INSTR or line.op not in ("sw", "lw") or len(line.args) != 2:
            continue
        following = next_instr(lines, index)
        if following is None:
            continue
        load = lines[following]
        if load.op != "lw" or len(load.args) != 2 or load.args[1] != line.args[1]:
            continue
        holder, address = line.args
        if line.op == "lw" and holder in address:
            continue  # `lw $t0, 0($t0)`: la segunda lectura ya usa otra direccion
        skipped.add(following)
        count += 1
        if load.args[0] != holder:
            out.append(_move(load, load.args[0], holder))
    return out, count


def redundant_move(lines: list[Line]):
    """`move $a, $b` / `move $b, $a` se queda con el primero; y una instruccion que escribe un temporal que
    solo se copia a otro registro escribe directo en el destino final."""
    out: list[Line] = []
    skipped: set[int] = set()
    count = 0
    for index, line in enumerate(lines):
        if index in skipped:
            continue
        following = next_instr(lines, index) if line.kind == INSTR else None
        if following is not None and lines[following].op == "move" and len(lines[following].args) == 2:
            copy = lines[following]
            target, source = copy.args
            if line.op == "move" and line.args == (source, target) and line.args[0] != line.args[1]:
                skipped.add(following)  # el valor ya estaba en los dos registros
                count += 1
            elif (
                line.op in _RETARGETABLE
                and line.args
                and line.args[0] == source
                and target not in ("$zero", source)
                and is_dead(lines, following + 1, source)
            ):
                known = effects(line)
                if known is not None and known[0] == {source}:
                    line = replace(line, args=(target,) + line.args[1:])
                    skipped.add(following)
                    count += 1
        out.append(line)
    return out, count


def stack_adjustments(lines: list[Line]):
    """`addiu $sp, $sp, -4` seguido de `addiu $sp, $sp, 4` se combinan; si suman cero, desaparecen."""
    out: list[Line] = []
    skipped: set[int] = set()
    count = 0
    for index, line in enumerate(lines):
        if index in skipped:
            continue
        following = next_instr(lines, index) if _is_sp_adjust(line) else None
        if following is not None and _is_sp_adjust(lines[following]):
            total = int_value(line.args[2]) + int_value(lines[following].args[2])
            skipped.add(following)
            count += 1
            if total != 0:
                out.append(replace(line, op="addiu", args=("$sp", "$sp", str(total))))
            continue
        out.append(line)
    return out, count


def _is_sp_adjust(line: Line) -> bool:
    return (
        line.kind == INSTR
        and line.op in ("addiu", "addi")
        and line.args[:2] == ("$sp", "$sp")
        and int_value(line.args[2]) is not None
    )


RULES = [
    ("identidad algebraica", algebraic_identity),
    ("carga redundante", redundant_load),
    ("movimiento redundante", redundant_move),
    ("ajustes de pila contiguos", stack_adjustments),
]
