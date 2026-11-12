"""Backend: del codigo de tres direcciones a ensamblador MIPS32."""
from __future__ import annotations

from compiscript.backend.mips import AsmResult, generate_mips
from compiscript.backend.operands import UnsupportedFeature
from compiscript.backend.peephole import optimize
from compiscript.backend.registers import ALLOCATABLE


def compile_to_mips(source: str, analyzer=None, registers=ALLOCATABLE, peephole: bool = True) -> AsmResult:
    """Compila codigo Compiscript sin errores a MIPS.

    Si ya se analizo el codigo se pasa el `analyzer`. `registers` limita los registros
    que reparte el asignador (minimo tres) y `peephole` activa la optimizacion por mirilla.
    """
    from compiscript.intermediate.generator import generate_tac
    from compiscript.semantic.analyzer import analyze_source

    if analyzer is None:
        analyzer, syntax_errors = analyze_source(source)
        if syntax_errors or analyzer.diagnostics.has_errors():
            raise ValueError("el programa tiene errores: no se genera ensamblador")
    result = generate_mips(generate_tac(source, analyzer), analyzer, registers)
    if peephole:
        result.program.text, result.peephole = optimize(result.program.text)
    return result


__all__ = ["ALLOCATABLE", "AsmResult", "UnsupportedFeature", "compile_to_mips", "generate_mips"]
