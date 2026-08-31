#!/usr/bin/env python3
"""Demo de linea de comandos del walking skeleton: corre el analizador
semantico sobre un archivo .cps y muestra los diagnosticos.

Uso:
    python3 src/compiscript/run_demo.py tests/compiscript/scope/invalid/redeclaracion.cps
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compiscript.semantic.analyzer import analyze_source  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python3 run_demo.py <archivo.cps>")
        return 2

    path = Path(sys.argv[1])
    source = path.read_text()

    analyzer, syntax_errors = analyze_source(source)

    print(f"Archivo: {path}")
    if syntax_errors:
        print(f"\nErrores de sintaxis ({len(syntax_errors)}):")
        for err in syntax_errors:
            print(f"  - {err}")
        return 1

    if len(analyzer.diagnostics) == 0:
        print("\n✅ Sin diagnosticos semanticos (dentro de lo que este walking skeleton entiende).")
        return 0

    print(f"\nDiagnosticos ({len(analyzer.diagnostics)}):")
    for diagnostic in analyzer.diagnostics:
        print(f"  {diagnostic}")

    return 1 if analyzer.diagnostics.has_errors() else 0


if __name__ == "__main__":
    raise SystemExit(main())
