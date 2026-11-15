"""Mirilla: reglas con constantes y la mirilla completa sobre programas reales."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
sys.path.insert(0, str(SRC / "compiscript"))
sys.path.insert(0, str(SRC))

from compiscript.backend import UnsupportedFeature, compile_to_mips  # noqa: E402
from compiscript.backend.asm import INSTR, parse_lines  # noqa: E402
from compiscript.backend.peephole import RULES, optimize  # noqa: E402
from compiscript.backend.peephole.constants import (  # noqa: E402
    arithmetic_immediate,
    compare_immediate,
    strength_reduction,
)
from compiscript.backend.simulator import run_mips  # noqa: E402


def apply(rule, source: str):
    lines, count = rule(parse_lines(source))
    return [line.to_text().strip() for line in lines if line.kind != "comment"], count


# ---------------------------------------------------------------- reduccion de fuerza
def test_multiplicar_por_potencia_de_dos_es_un_desplazamiento():
    out, count = apply(strength_reduction, "li $t1, 8\nmul $t0, $t0, $t1\nL:\n")
    assert out == ["sll $t0, $t0, 3", "L:"] and count == 1


def test_la_constante_puede_ir_en_el_primer_operando():
    out, _ = apply(strength_reduction, "li $t1, 4\nmul $t2, $t1, $t0\nL:\n")
    assert out == ["sll $t2, $t0, 2", "L:"]


def test_multiplicar_por_uno_y_por_cero():
    assert apply(strength_reduction, "li $t1, 1\nmul $t0, $t2, $t1\nL:\n")[0] == ["move $t0, $t2", "L:"]
    assert apply(strength_reduction, "li $t1, 0\nmul $t0, $t2, $t1\nL:\n")[0] == ["li $t0, 0", "L:"]


def test_si_la_constante_se_vuelve_a_leer_el_li_se_conserva():
    out, _ = apply(strength_reduction, "li $t1, 8\nmul $t0, $t2, $t1\naddu $t3, $t1, $t0\n")
    assert out == ["li $t1, 8", "sll $t0, $t2, 3", "addu $t3, $t1, $t0"]


def test_multiplicar_por_otra_constante_no_cambia():
    out, count = apply(strength_reduction, "li $t1, 6\nmul $t0, $t0, $t1\n")
    assert out == ["li $t1, 6", "mul $t0, $t0, $t1"] and count == 0


# ---------------------------------------------------------------- comparacion con inmediato
def test_slt_con_constante():
    out, count = apply(compare_immediate, "li $t1, 3\nslt $t1, $t0, $t1\nL:\n")
    assert out == ["slti $t1, $t0, 3", "L:"] and count == 1


def test_sle_con_constante_suma_uno():
    out, _ = apply(compare_immediate, "li $t1, 1\nsle $t1, $t0, $t1\nL:\n")
    assert out == ["slti $t1, $t0, 2", "L:"]


def test_la_constante_en_el_lado_izquierdo_no_se_reescribe():
    out, count = apply(compare_immediate, "li $t1, 3\nslt $t0, $t1, $t0\n")
    assert len(out) == 2 and count == 0


def test_constante_fuera_de_rango_de_inmediato():
    out, count = apply(compare_immediate, "li $t1, 70000\nslt $t0, $t0, $t1\n")
    assert len(out) == 2 and count == 0


# ---------------------------------------------------------------- aritmetica con inmediato
def test_suma_y_resta_con_constante():
    assert apply(arithmetic_immediate, "li $t1, 5\naddu $t0, $t0, $t1\nL:\n")[0] == ["addiu $t0, $t0, 5", "L:"]
    assert apply(arithmetic_immediate, "li $t1, 5\naddu $t0, $t2, $t1\nL:\n")[0] == ["addiu $t0, $t2, 5", "L:"]
    assert apply(arithmetic_immediate, "li $t1, 5\nsubu $t0, $t0, $t1\nL:\n")[0] == ["addiu $t0, $t0, -5", "L:"]


def test_restar_de_una_constante_no_se_reescribe():
    out, count = apply(arithmetic_immediate, "li $t1, 5\nsubu $t0, $t1, $t0\n")
    assert len(out) == 2 and count == 0


# ---------------------------------------------------------------- mirilla completa
def test_hay_al_menos_seis_transformaciones_distintas():
    names = [name for name, _ in RULES]
    assert len(names) == len(set(names)) >= 6


def test_el_optimizador_cuenta_cada_transformacion():
    _, applied = optimize(parse_lines("li $t1, 8\nmul $t0, $t0, $t1\nj L\nL:\njr $ra\n"))
    assert applied["reduccion de fuerza"] == 1 and applied["salto a la siguiente instruccion"] == 1
    assert set(applied) == {name for name, _ in RULES}


PROGRAMS = sorted((HERE / "intermediate" / "valid").glob("*.cps"))


def _count(result) -> int:
    return sum(1 for line in result.program.text if line.kind == INSTR)


def _compile_both(path):
    source = path.read_text(encoding="utf-8")
    try:
        return compile_to_mips(source, peephole=False), compile_to_mips(source)
    except UnsupportedFeature:
        pytest.skip("pendiente en el backend")


@pytest.mark.parametrize("registers", [None, 3], ids=["diez_registros", "tres_registros"])
@pytest.mark.parametrize("path", PROGRAMS, ids=lambda p: p.stem)
def test_la_mirilla_no_cambia_la_salida_ni_agranda_el_programa(path, registers):
    source = path.read_text(encoding="utf-8")
    options = {} if registers is None else {"registers": ("$t0", "$t1", "$t2")}
    try:
        plain = compile_to_mips(source, peephole=False, **options)
    except UnsupportedFeature:
        pytest.skip("pendiente en el backend")
    better = compile_to_mips(source, **options)
    assert _count(better) <= _count(plain)
    assert run_mips(better.text, better.functions).output == run_mips(plain.text, plain.functions).output


def test_la_mirilla_reduce_el_conjunto_de_programas():
    total_plain = total_better = 0
    for path in PROGRAMS:
        try:
            plain, better = _compile_both(path)
        except pytest.skip.Exception:
            continue
        total_plain += _count(plain)
        total_better += _count(better)
    assert total_better < 0.95 * total_plain
