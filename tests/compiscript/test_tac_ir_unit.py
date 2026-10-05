"""Pruebas unitarias de intermediate/ir.py: allocator de temporales y formato de instrucciones."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiscript.intermediate.ir import Instruction, TACProgram, TempAllocator  # noqa: E402


# ----------------------------------------------------------------- TempAllocator
def test_allocator_entrega_temporales_consecutivos():
    temps = TempAllocator()
    assert [temps.acquire() for _ in range(3)] == ["t0", "t1", "t2"]
    assert temps.count == 3


def test_allocator_reutiliza_el_temporal_liberado():
    temps = TempAllocator()
    t0, t1 = temps.acquire(), temps.acquire()
    temps.release(t0)
    assert temps.acquire() == t0
    assert temps.count == 2
    assert t1 == "t1"


def test_allocator_reutiliza_en_orden_lifo():
    temps = TempAllocator()
    a, b = temps.acquire(), temps.acquire()
    temps.release(a)
    temps.release(b)
    assert temps.acquire() == b
    assert temps.acquire() == a


def test_liberar_dos_veces_no_duplica_el_temporal():
    temps = TempAllocator()
    t0 = temps.acquire()
    temps.release(t0)
    temps.release(t0)
    assert temps.acquire() == "t0"
    assert temps.acquire() == "t1"


@pytest.mark.parametrize("name", ["x", "t9", "5", '"t0"', "", "this"])
def test_liberar_algo_que_no_es_un_temporal_se_ignora(name):
    temps = TempAllocator()
    temps.release(name)
    assert temps.acquire() == "t0"
    assert temps.count == 1


def test_allocator_salta_nombres_reservados_por_el_programa_fuente():
    temps = TempAllocator(reserved={"t0", "t2"})
    assert [temps.acquire() for _ in range(3)] == ["t1", "t3", "t4"]


def test_variable_reservada_nunca_se_recicla():
    temps = TempAllocator(reserved={"t0"})
    temps.release("t0")  # es una variable del usuario, no un temporal
    assert temps.acquire() == "t1"


def test_el_conteo_no_crece_al_reciclar():
    temps = TempAllocator()
    for _ in range(50):
        temps.release(temps.acquire())
    assert temps.count == 1


# ----------------------------------------------------------------- Instruction
@pytest.mark.parametrize(
    "instruction, text",
    [
        (Instruction("copy", arg1="1", result="x"), "x = 1"),
        (Instruction("+", arg1="a", arg2="b", result="t0"), "t0 = a + b"),
        (Instruction("<=", arg1="a", arg2="b", result="t0"), "t0 = a <= b"),
        (Instruction("neg", arg1="a", result="t0"), "t0 = -a"),
        (Instruction("not", arg1="a", result="t0"), "t0 = !a"),
        (Instruction("label", result="L0"), "L0:"),
        (Instruction("goto", result="L0"), "goto L0"),
        (Instruction("if", arg1="t0", result="L0"), "if t0 goto L0"),
        (Instruction("ifFalse", arg1="t0", result="L0"), "ifFalse t0 goto L0"),
        (Instruction("try", result="catch0"), "try goto catch0"),
        (Instruction("halt"), "halt"),
        (Instruction("function", result="f"), "function f"),
        (Instruction("end_function", result="f"), "end function f"),
        (Instruction("param_decl", arg1="x"), "param_decl x"),
        (Instruction("param", arg1="x"), "param x"),
        (Instruction("link", arg1="1"), "link 1"),
        (Instruction("call_result", arg1="f", arg2="2", result="t0"), "t0 = call f, 2"),
        (Instruction("invoke", arg1="o.m", arg2="1", result="t0"), "t0 = invoke o.m, 1"),
        (Instruction("return"), "return"),
        (Instruction("return", arg1="t0"), "return t0"),
        (Instruction("print", arg1="x"), "print x"),
        (Instruction("array", arg1="1, 2", result="t0"), "t0 = array 1, 2"),
        (Instruction("array", result="t0"), "t0 = array"),
        (Instruction("length", arg1="xs", result="t0"), "t0 = length xs"),
        (Instruction("index_load", arg1="xs", arg2="i", result="t0"), "t0 = xs[i]"),
        (Instruction("index_store", arg1="i", arg2="v", result="xs"), "xs[i] = v"),
        (Instruction("member_load", arg1="o", arg2="f", result="t0"), "t0 = o.f"),
        (Instruction("member_store", arg1="f", arg2="v", result="o"), "o.f = v"),
        (Instruction("new", arg1="C", arg2="2", result="t0"), "t0 = new C, 2"),
        (Instruction("env_load", arg1="2", arg2="x", result="t0"), "t0 = up(2).x"),
        (Instruction("env_store", arg1="v", arg2="1", result="x"), "up(1).x = v"),
    ],
)
def test_formato_de_texto_de_cada_instruccion(instruction, text):
    assert instruction.to_text() == text


def test_to_dict_expone_los_cuatro_campos():
    assert Instruction("+", "a", "b", "t0").to_dict() == {
        "op": "+",
        "arg1": "a",
        "arg2": "b",
        "result": "t0",
    }


def test_instruccion_es_inmutable():
    with pytest.raises(Exception):
        Instruction("copy", "1", "", "x").op = "goto"  # type: ignore[misc]


def test_programa_emite_en_orden_y_une_las_lineas():
    program = TACProgram()
    program.emit("copy", arg1="1", result="x")
    program.emit("print", arg1="x")
    assert [i.op for i in program.instructions] == ["copy", "print"]
    assert program.to_text() == "x = 1\nprint x"
