#!/usr/bin/env python3
"""Compila un archivo .cps desde la linea de comandos.

Uso:
    python src/compiscript/run_demo.py <archivo.cps> [opciones]

    (sin opciones)   diagnosticos semanticos
    --tac            codigo de tres direcciones
    --layout         registros de activacion
    --asm            ensamblador MIPS
    --run            ejecuta el ensamblador en el simulador y muestra la salida
    --tree           arbol de activacion de esa ejecucion
    --registers=N    limita a N los registros que reparte el asignador (minimo 3)
    --no-peephole    desactiva la optimizacion por mirilla
    --out=ARCHIVO    guarda el ensamblador en ARCHIVO (para abrirlo en MARS o SPIM)

Solo se genera codigo si el programa no tiene errores.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compiscript.backend import ALLOCATABLE, UnsupportedFeature, compile_to_mips  # noqa: E402
from compiscript.backend.simulator import SimulatorError, run_mips  # noqa: E402
from compiscript.intermediate.generator import generate_tac  # noqa: E402
from compiscript.semantic.analyzer import analyze_source  # noqa: E402

USAGE = (
    "Uso: python run_demo.py <archivo.cps> [--tac] [--layout] [--asm] [--run] [--tree] "
    "[--registers=N] [--no-peephole] [--out=ARCHIVO]"
)
_FLAGS = {"--tac", "--layout", "--asm", "--run", "--tree", "--no-peephole"}
_VALUED = ("--registers", "--out")


def _parse(args: list[str]):
    flags, values, files = set(), {}, []
    for arg in args:
        name, has_value, value = arg.partition("=")
        if arg in _FLAGS:
            flags.add(arg)
        elif has_value and name in _VALUED and value:
            values[name] = value
        elif arg.startswith("--"):
            return None
        else:
            files.append(arg)
    if len(files) != 1:
        return None
    registers = ALLOCATABLE
    if "--registers" in values:
        if not values["--registers"].isdigit() or not 3 <= int(values["--registers"]) <= len(ALLOCATABLE):
            return None
        registers = ALLOCATABLE[: int(values["--registers"])]
    return files[0], flags, registers, values.get("--out")


def _backend(source: str, analyzer, flags: set[str], registers, out_path) -> int:
    try:
        result = compile_to_mips(source, analyzer, registers, peephole="--no-peephole" not in flags)
    except UnsupportedFeature as error:
        print(f"\nEl backend aun no traduce esta construccion: {error}")
        return 1
    if "--asm" in flags:
        print("\nEnsamblador MIPS:")
        print(result.text)
        applied = [f"{name} x{count}" for name, count in result.peephole.items() if count]
        if applied:
            print("Mirilla: " + ", ".join(applied))
    if out_path:
        Path(out_path).write_text(result.text, encoding="utf-8")
        print(f"\nEnsamblador guardado en {out_path}")
    if flags & {"--run", "--tree"}:
        try:
            machine = run_mips(result.text, result.functions)
        except SimulatorError as error:
            print(f"\nError del simulador: {error}")
            return 1
        if "--run" in flags:
            print("\nSalida del programa:")
            print(machine.output, end="")
        if "--tree" in flags:
            print("\nArbol de activacion:")
            print(machine.root.to_text())
        return machine.exit_code or 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parsed = _parse(list(sys.argv[1:] if argv is None else argv))
    if parsed is None:
        print(USAGE)
        return 2
    file, flags, registers, out_path = parsed

    path = Path(file)
    source = path.read_text(encoding="utf-8")

    analyzer, syntax_errors = analyze_source(source)

    print(f"Archivo: {path}")
    if syntax_errors:
        print(f"\nErrores de sintaxis ({len(syntax_errors)}):")
        for err in syntax_errors:
            print(f"  - {err}")
        return 1

    if len(analyzer.diagnostics) == 0:
        print("\nSin diagnosticos semanticos.")
    else:
        print(f"\nDiagnosticos ({len(analyzer.diagnostics)}):")
        for diagnostic in analyzer.diagnostics:
            print(f"  {diagnostic}")

    if analyzer.diagnostics.has_errors():
        if flags or out_path:
            print("\nNo se genera codigo intermedio: el programa tiene errores.")
        return 1

    if flags & {"--tac", "--layout"}:
        program = generate_tac(source, analyzer)
        analyzer.layout.apply_temps(program.temp_counts)
        if "--tac" in flags:
            print("\nCodigo intermedio:")
            print(program.to_text())
        if "--layout" in flags:
            print("\nRegistros de activacion:")
            print(analyzer.layout.to_text())

    if flags & {"--asm", "--run", "--tree", "--no-peephole"} or out_path:
        return _backend(source, analyzer, flags, registers, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
