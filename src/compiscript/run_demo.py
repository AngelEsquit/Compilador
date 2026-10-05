#!/usr/bin/env python3
"""Compila un archivo .cps: analisis semantico y, opcionalmente, codigo intermedio.

Uso:
    python src/compiscript/run_demo.py <archivo.cps>            # diagnosticos semanticos
    python src/compiscript/run_demo.py <archivo.cps> --tac      # ademas, el codigo de tres direcciones
    python src/compiscript/run_demo.py <archivo.cps> --layout   # ademas, registros de activacion

El codigo intermedio solo se genera si el programa no tiene errores.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compiscript.intermediate.generator import generate_tac  # noqa: E402
from compiscript.semantic.analyzer import analyze_source  # noqa: E402

USAGE = "Uso: python run_demo.py <archivo.cps> [--tac] [--layout]"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    flags = {a for a in args if a.startswith("--")}
    files = [a for a in args if not a.startswith("--")]
    if len(files) != 1 or not flags <= {"--tac", "--layout"}:
        print(USAGE)
        return 2

    path = Path(files[0])
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
        if flags:
            print("\nNo se genera codigo intermedio: el programa tiene errores.")
        return 1

    if flags:
        program = generate_tac(source, analyzer)
        analyzer.layout.apply_temps(program.temp_counts)
        if "--tac" in flags:
            print("\nCodigo intermedio:")
            print(program.to_text())
        if "--layout" in flags:
            print("\nRegistros de activacion:")
            print(analyzer.layout.to_text())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
