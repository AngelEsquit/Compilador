"""Optimizacion por mirilla sobre el ensamblador generado.

Pendiente: hoy devuelve el programa sin cambios. Cada transformacion es una funcion que
recibe la lista de lineas y devuelve la lista nueva; `optimize` las aplica hasta que
ninguna cambia nada.
"""
from __future__ import annotations

from compiscript.backend.asm import Line

# Transformaciones registradas, en el orden en que se aplican: (nombre, funcion).
RULES: list[tuple[str, object]] = []


def optimize(lines: list[Line]) -> tuple[list[Line], dict[str, int]]:
    """Devuelve las lineas optimizadas y cuantas veces se aplico cada transformacion."""
    applied: dict[str, int] = {name: 0 for name, _ in RULES}
    changed = True
    while changed:
        changed = False
        for name, rule in RULES:
            result = rule(lines)
            if result != lines:
                applied[name] += 1
                lines = result
                changed = True
    return lines, applied
