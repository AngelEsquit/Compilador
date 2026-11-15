"""try/catch en el backend MIPS: pila de manejadores, desenrollado y variables vivas en el catch."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiscript.backend import compile_to_mips  # noqa: E402
from compiscript.backend.simulator import run_mips  # noqa: E402

THREE = ("$t0", "$t1", "$t2")
BOTH = pytest.mark.parametrize("registers", [None, THREE], ids=["diez_registros", "tres_registros"])


def execute(source: str, registers=None):
    options = {} if registers is None else {"registers": registers}
    result = compile_to_mips(source, **options)
    return run_mips(result.text, result.functions)


def run(source: str, registers=None) -> list[str]:
    return execute(source, registers).output.splitlines()


ZERO = "let cero: integer = 0;\n"


# ---------------------------------------------------------------- error sin capturar
def test_error_sin_try_termina_el_programa():
    machine = execute(ZERO + "print(1 / cero);")
    assert machine.output == "Error de ejecucion: division por cero\n" and machine.exit_code == 1


def test_error_despues_de_un_try_terminado_no_se_captura():
    source = ZERO + """
    try { print(1); } catch (e) { print("no"); }
    print(1 / cero);
    """
    machine = execute(source)
    assert machine.output == "1\nError de ejecucion: division por cero\n" and machine.exit_code == 1


def test_sin_try_no_se_incluye_la_pila_de_manejadores():
    text = compile_to_mips(ZERO + "print(1 / cero);").text
    assert "_handlers" not in text and "_throw_fatal" not in text


# ---------------------------------------------------------------- captura
@BOTH
def test_captura_division_indice_y_null(registers):
    source = ZERO + """
    class C { let v: integer; }
    let nada: C = null;
    let v: integer[] = [1, 2];
    try { print(1 / cero); } catch (e) { print(e); }
    try { print(v[5]); } catch (e) { print(e); }
    try { print(nada.v); } catch (e) { print(e); }
    print("fin");
    """
    assert run(source, registers) == ["division por cero", "indice fuera de rango", "acceso a null", "fin"]


@BOTH
def test_try_anidado_el_interno_no_captura_lo_del_externo(registers):
    source = ZERO + """
    let v: integer[] = [1];
    try {
      try { print(v[3]); } catch (e) { print("interno " + e); }
      print(1 / cero);
    } catch (e) { print("externo " + e); }
    """
    assert run(source, registers) == ["interno indice fuera de rango", "externo division por cero"]


@BOTH
def test_un_error_dentro_del_catch_lo_atiende_el_try_de_afuera(registers):
    source = ZERO + """
    try {
      try { print(1 / cero); } catch (e) { print("uno"); print(2 / cero); }
    } catch (e) { print("dos " + e); }
    """
    assert run(source, registers) == ["uno", "dos division por cero"]


@BOTH
def test_error_dentro_de_una_funcion_llamada_desde_el_try(registers):
    source = """
    function pasos(n: integer): integer {
      if (n == 0) { return 10 / n; }
      return pasos(n - 1) + 1;
    }
    function seguro(n: integer): integer {
      try { return pasos(n); } catch (e) { return -1; }
    }
    print(seguro(5));
    print(seguro(0));
    """
    assert run(source, registers) == ["-1", "-1"]


@BOTH
def test_desenrollado_deja_la_pila_lista_para_seguir_llamando(registers):
    source = """
    function falla(d: integer): integer { return 1 / d; }
    function nivel(n: integer): integer { if (n == 0) { return falla(0); } return nivel(n - 1); }
    function suma(a: integer, b: integer): integer { return a + b; }
    let total: integer = 0;
    for (let i: integer = 0; i < 4; i = i + 1) {
      try { total = total + nivel(6); } catch (e) { total = suma(total, 10); }
    }
    print(total);
    """
    assert run(source, registers) == ["40"]


@BOTH
def test_variable_modificada_en_el_try_se_lee_en_el_catch(registers):
    source = """
    function f(z: integer) {
      let x: integer = 1;
      let y: integer = 100;
      try {
        x = x + 5;
        x = x * 2;
        y = y - x;
        print(10 / z);
      } catch (e) { print(x); print(y); }
    }
    f(0);
    """
    assert run(source, registers) == ["12", "88"]


@BOTH
def test_variable_modificada_antes_de_una_llamada_que_falla(registers):
    source = """
    function falla(d: integer): integer { return 1 / d; }
    function f() {
      let a: integer = 1;
      try { a = a + 41; print(falla(0)); } catch (e) { print(a); }
    }
    f();
    """
    assert run(source, registers) == ["42"]


@BOTH
def test_return_break_y_continue_dentro_de_try_desinstalan_el_manejador(registers):
    source = ZERO + """
    function f(n: integer): integer {
      try { if (n > 0) { return n; } } catch (e) { return -1; }
      return 0;
    }
    let s: integer = 0;
    for (let i: integer = 0; i < 6; i = i + 1) {
      try {
        if (i == 1) { continue; }
        if (i == 4) { break; }
        s = s + f(i);
      } catch (e) { print("no"); }
    }
    print(s);
    print(1 / cero);
    """
    machine = execute(source, registers)
    assert machine.output == "5\nError de ejecucion: division por cero\n"


@BOTH
def test_error_dentro_de_un_metodo(registers):
    source = """
    class Banco {
      let saldo: integer = 10;
      function dividir(n: integer): integer { return this.saldo / n; }
    }
    let b: Banco = new Banco();
    try { print(b.dividir(0)); } catch (e) { print("fallo: " + e); }
    print(b.dividir(2));
    """
    assert run(source, registers) == ["fallo: division por cero", "5"]


# ---------------------------------------------------------------- pila de manejadores
def test_el_try_guarda_catch_fp_y_sp_y_throw_los_restaura():
    text = compile_to_mips(ZERO + "try { print(1 / cero); } catch (e) { print(e); }").text
    assert "sw $fp, 4($a1)" in text and "sw $sp, 8($a1)" in text
    assert "lw $fp, 4($a2)" in text and "lw $sp, 8($a2)" in text and "jr $a2" in text


def test_demasiados_try_anidados_termina_con_un_error_claro():
    source = """
    function hondo(n: integer): integer {
      try { return hondo(n + 1); } catch (e) { return 0; }
    }
    print(hondo(0));
    """
    machine = execute(source)
    assert machine.exit_code == 1 and "demasiados try anidados" in machine.output
