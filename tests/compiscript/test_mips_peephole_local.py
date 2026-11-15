"""Mirilla: reglas locales (identidades, cargas y movimientos redundantes, ajustes de pila)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC / "compiscript"))
sys.path.insert(0, str(SRC))

from compiscript.backend.asm import parse_lines  # noqa: E402
from compiscript.backend.peephole.analysis import is_dead  # noqa: E402
from compiscript.backend.peephole.local import (  # noqa: E402
    algebraic_identity,
    redundant_load,
    redundant_move,
    stack_adjustments,
)


def apply(rule, source: str):
    lines, count = rule(parse_lines(source))
    return [line.to_text().strip() for line in lines if line.kind != "comment"], count


# ---------------------------------------------------------------- identidad algebraica
def test_identidades_con_el_mismo_registro_se_eliminan():
    out, count = apply(algebraic_identity, "addiu $t0, $t0, 0\nmove $t1, $t1\nsll $t2, $t2, 0\nori $t3, $t3, 0\n")
    assert out == [] and count == 4


def test_identidad_con_cero_y_otro_destino_se_vuelve_move():
    out, count = apply(algebraic_identity, "addiu $t0, $t1, 0\naddu $t2, $t3, $zero\naddu $t4, $zero, $t5\n")
    assert out == ["move $t0, $t1", "move $t2, $t3", "move $t4, $t5"] and count == 3


def test_ajuste_de_pila_en_cero_se_elimina():
    out, _ = apply(algebraic_identity, "addiu $sp, $sp, 0\n")
    assert out == []


def test_una_suma_con_constante_no_cero_se_conserva():
    out, count = apply(algebraic_identity, "addiu $t0, $t0, 1\nsubu $t0, $t0, $t1\n")
    assert out == ["addiu $t0, $t0, 1", "subu $t0, $t0, $t1"] and count == 0


# ---------------------------------------------------------------- carga redundante
def test_carga_despues_de_guardar_en_el_mismo_registro():
    out, count = apply(redundant_load, "sw $t0, 24($fp)\nlw $t0, 24($fp)\nmove $t1, $t0\n")
    assert out == ["sw $t0, 24($fp)", "move $t1, $t0"] and count == 1


def test_carga_despues_de_guardar_en_otro_registro_es_un_move():
    out, _ = apply(redundant_load, "sw $t0, 24($fp)\nlw $t1, 24($fp)\n")
    assert out == ["sw $t0, 24($fp)", "move $t1, $t0"]


def test_dos_cargas_de_la_misma_casilla():
    out, count = apply(redundant_load, "lw $t0, 8($fp)\nlw $t1, 8($fp)\n")
    assert out == ["lw $t0, 8($fp)", "move $t1, $t0"] and count == 1


def test_carga_con_direccion_distinta_se_conserva():
    out, count = apply(redundant_load, "sw $t0, 24($fp)\nlw $t0, 28($fp)\n")
    assert out == ["sw $t0, 24($fp)", "lw $t0, 28($fp)"] and count == 0


def test_dos_cargas_cuyo_destino_es_la_base_no_se_tocan():
    out, count = apply(redundant_load, "lw $t0, 0($t0)\nlw $t0, 0($t0)\n")
    assert len(out) == 2 and count == 0


def test_una_etiqueta_entre_el_guardado_y_la_carga_lo_impide():
    out, count = apply(redundant_load, "sw $t0, 24($fp)\nL:\nlw $t0, 24($fp)\n")
    assert len(out) == 3 and count == 0


def test_los_bytes_no_se_tocan():
    out, count = apply(redundant_load, "sb $t0, 24($fp)\nlbu $t0, 24($fp)\n")
    assert len(out) == 2 and count == 0


# ---------------------------------------------------------------- movimiento redundante
def test_move_de_ida_y_vuelta():
    out, count = apply(redundant_move, "move $t0, $t1\nmove $t1, $t0\n")
    assert out == ["move $t0, $t1"] and count == 1


def test_move_a_traves_de_un_temporal_muerto():
    out, count = apply(redundant_move, "move $t0, $v0\nmove $a0, $t0\nL:\n")
    assert out == ["move $a0, $v0", "L:"] and count == 1


def test_move_a_traves_de_un_temporal_que_se_lee_despues_se_conserva():
    out, count = apply(redundant_move, "move $t0, $v0\nmove $a0, $t0\nmove $t2, $t0\n")
    assert len(out) == 3 and count == 0


def test_li_que_solo_se_copia_escribe_directo_en_el_destino():
    out, _ = apply(redundant_move, "li $t0, 5\nmove $a0, $t0\nL:\n")
    assert out == ["li $a0, 5", "L:"]


def test_carga_que_solo_se_copia_escribe_directo_en_el_destino():
    out, _ = apply(redundant_move, "lw $t0, 24($fp)\nmove $a0, $t0\nL:\n")
    assert out == ["lw $a0, 24($fp)", "L:"]


def test_el_temporal_sobrescrito_por_otra_instruccion_esta_muerto():
    out, _ = apply(redundant_move, "addiu $t0, $t1, 4\nmove $a0, $t0\nli $t0, 1\n")
    assert out == ["addiu $a0, $t1, 4", "li $t0, 1"]


def test_un_registro_que_no_es_temporal_no_se_reescribe():
    out, count = apply(redundant_move, "move $a1, $v0\nmove $a0, $a1\nL:\n")
    assert len(out) == 3 and count == 0


def test_un_temporal_usado_tras_una_rutina_de_biblioteca_sigue_vivo():
    lines = parse_lines("move $t0, $v0\nmove $a0, $t0\njal _print_int\nmove $a1, $t0\n")
    assert not is_dead(lines, 2, "$t0")
    assert is_dead(parse_lines("jal f_otra\nmove $a1, $t0\n"), 0, "$t0")


# ---------------------------------------------------------------- ajustes de pila
def test_ajustes_de_pila_opuestos_desaparecen():
    out, count = apply(stack_adjustments, "addiu $sp, $sp, -4\naddiu $sp, $sp, 4\n")
    assert out == [] and count == 1


def test_ajustes_de_pila_se_combinan():
    out, _ = apply(stack_adjustments, "addiu $sp, $sp, -4\naddiu $sp, $sp, -8\n")
    assert out == ["addiu $sp, $sp, -12"]


def test_un_acceso_a_la_pila_entre_ajustes_los_separa():
    out, count = apply(stack_adjustments, "addiu $sp, $sp, -4\nsw $t0, 0($sp)\naddiu $sp, $sp, 4\n")
    assert len(out) == 3 and count == 0
