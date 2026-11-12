"""Bloques basicos, variables vivas y siguiente uso.

El asignador de registros decide con esta informacion: un valor que ya no se usa puede
perder su registro sin guardarse, y cuando hay que desalojar uno se elige el que se
usara mas tarde.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Instrucciones que terminan un bloque. `try` cuenta porque su `catch` es un segundo sucesor.
TERMINATORS = frozenset({"goto", "if", "ifFalse", "return", "halt", "try", "end_function"})
_NO_FALLTHROUGH = frozenset({"goto", "return", "halt", "end_function"})

# Siguiente uso de una variable que sigue viva al salir del bloque.
LIVE_ON_EXIT = 10**9


@dataclass
class Block:
    index: int
    start: int
    end: int  # exclusivo
    successors: list[int] = field(default_factory=list)
    live_in: set = field(default_factory=set)
    live_out: set = field(default_factory=set)


def split_blocks(instructions) -> list[Block]:
    """Parte la funcion en bloques basicos y conecta el grafo de flujo."""
    leaders = {0}
    for position, ins in enumerate(instructions):
        if ins.op == "label":
            leaders.add(position)
        if ins.op in TERMINATORS and position + 1 < len(instructions):
            leaders.add(position + 1)
    starts = sorted(leaders)
    blocks = [
        Block(index, start, starts[index + 1] if index + 1 < len(starts) else len(instructions))
        for index, start in enumerate(starts)
    ]
    of_label = {
        instructions[block.start].result: block.index
        for block in blocks
        if instructions[block.start].op == "label"
    }
    for block in blocks:
        last = instructions[block.end - 1]
        if last.op in ("goto", "if", "ifFalse", "try"):
            block.successors.append(of_label[last.result])
        if last.op not in _NO_FALLTHROUGH and block.index + 1 < len(blocks):
            block.successors.append(block.index + 1)

    # Un error dentro de un `try` salta a su `catch` desde cualquier punto de la region.
    for position, ins in enumerate(instructions):
        if ins.op != "try":
            continue
        catch = of_label[ins.result]
        for block in blocks:
            if position < block.start < blocks[catch].start and catch not in block.successors:
                block.successors.append(catch)
    return blocks


def liveness(blocks: list[Block], uses_defs, exit_live: set) -> None:
    """Analisis de flujo de datos hacia atras: llena `live_in` y `live_out` de cada bloque.

    `uses_defs[i]` es `(usos, definiciones)` de la instruccion `i`. `exit_live` son las
    variables que deben quedar en memoria al salir de la funcion (las globales).
    """
    use: dict[int, set] = {}
    define: dict[int, set] = {}
    for block in blocks:
        used, defined = set(), set()
        for position in range(block.start, block.end):
            uses, defs = uses_defs[position]
            used.update(v for v in uses if v not in defined)
            defined.update(defs)
        use[block.index], define[block.index] = used, defined

    changed = True
    while changed:
        changed = False
        for block in reversed(blocks):
            if block.successors:
                out = set().union(*(blocks[s].live_in for s in block.successors))
            else:
                out = set(exit_live)
            live_in = use[block.index] | (out - define[block.index])
            if out != block.live_out or live_in != block.live_in:
                block.live_out, block.live_in = out, live_in
                changed = True


def next_uses(block: Block, uses_defs) -> list[dict]:
    """Para cada instruccion del bloque: variables vivas despues de ella y su siguiente uso.

    El valor es la posicion del siguiente uso dentro de la funcion, o `LIVE_ON_EXIT` si
    la variable solo se usa en otro bloque. Una variable ausente esta muerta.
    """
    current = {var: LIVE_ON_EXIT for var in block.live_out}
    after: list[dict] = []
    for position in range(block.end - 1, block.start - 1, -1):
        after.append(dict(current))
        uses, defs = uses_defs[position]
        for var in defs:
            current.pop(var, None)
        for var in uses:
            current[var] = position
    after.reverse()
    return after
