"""Optimizacion por mirilla sobre el ensamblador generado.

Cada modulo del paquete (menos `analysis`) define `ORDER` y `RULES`: una lista de
`(nombre, funcion)`. Una regla recibe la lista de `Line` y devuelve la lista nueva junto con
cuantas veces se aplico. `optimize` repite todas las reglas hasta que ninguna cambia nada.

Las reglas nunca modifican las `Line` que reciben (las reemplazan) y ninguna ventana cruza
una etiqueta, porque a una etiqueta se puede llegar desde otro lugar.
"""
from __future__ import annotations

import importlib
import pkgutil

from compiscript.backend.asm import Line


def _load_rules() -> list[tuple[str, object]]:
    modules = [
        importlib.import_module(f"{__name__}.{info.name}")
        for info in pkgutil.iter_modules(__path__)
        if info.name != "analysis"
    ]
    rules: list[tuple[str, object]] = []
    for module in sorted(modules, key=lambda m: m.ORDER):
        rules += module.RULES
    return rules


# Transformaciones registradas, en el orden en que se aplican: (nombre, funcion).
RULES: list[tuple[str, object]] = _load_rules()


def optimize(lines: list[Line]) -> tuple[list[Line], dict[str, int]]:
    """Devuelve las lineas optimizadas y cuantas veces se aplico cada transformacion."""
    applied: dict[str, int] = {name: 0 for name, _ in RULES}
    changed = True
    while changed:
        changed = False
        for name, rule in RULES:
            lines, count = rule(lines)
            if count:
                applied[name] += count
                changed = True
    return lines, applied
