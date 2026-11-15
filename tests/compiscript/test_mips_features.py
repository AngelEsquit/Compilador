"""Arreglos, punto flotante, accion `compiscriptASM` del bridge y validacion contra MARS."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bridge_cli import _run_action  # noqa: E402
from compiscript.backend import compile_to_mips  # noqa: E402
from compiscript.backend.simulator import format_float, run_mips  # noqa: E402

THREE = ("$t0", "$t1", "$t2")
MARS = ROOT / "tools" / "mars" / "Mars4_5.jar"

ARRAYS = """
let m: integer[][] = [[1, 2, 3], [4, 5, 6]];
let total: integer = 0;
foreach (fila in m) { foreach (v in fila) { total = total + v; } }
print(total);
m[1][2] = 60;
print(m[1][2] + m[0][0]);
let nombres: string[] = ["ana", "luis"];
nombres[1] = nombres[0] + "-" + nombres[1];
print(nombres[1]);
let ok: boolean[] = [true, false];
print(ok[0] && !ok[1]);
"""

SORT = """
function ordenar(v: integer[], n: integer) {
  for (let i: integer = 0; i < n; i = i + 1) {
    for (let j: integer = 0; j < n - 1 - i; j = j + 1) {
      if (v[j] > v[j + 1]) { let t: integer = v[j]; v[j] = v[j + 1]; v[j + 1] = t; }
    }
  }
}
let datos: integer[] = [5, 3, 9, 1, 7, 2];
ordenar(datos, 6);
foreach (d in datos) { print(d); }
"""

FLOATS = """
function mitad(x: float): float { return x / 2; }
function entero(): float { return 3; }
let a: float = 1.5;
let b: float = 2;
let n: integer = 4;
print(a + b);
print(a * n);
print(mitad(n));
print(entero());
print(a < b);
print(a != 1.5);
print(-a);
let xs: float[] = [0.5, 1.25];
print(xs[0] + xs[1]);
"""

EXPECTED = {
    ARRAYS: ["21", "61", "ana-luis", "true"],
    SORT: ["1", "2", "3", "5", "7", "9"],
    FLOATS: ["3.5", "6.0", "2.0", "3.0", "true", "false", "-1.5", "1.75"],
}


def run(source: str, registers=None) -> list[str]:
    result = compile_to_mips(source) if registers is None else compile_to_mips(source, registers=registers)
    return run_mips(result.text, result.functions).output.splitlines()


@pytest.mark.parametrize("registers", [None, THREE], ids=["diez_registros", "tres_registros"])
@pytest.mark.parametrize("source", EXPECTED, ids=["arreglos", "ordenamiento", "flotantes"])
def test_arreglos_y_flotantes(source, registers):
    assert run(source, registers) == EXPECTED[source]


def test_arreglo_guarda_la_longitud_en_la_primera_palabra():
    text = compile_to_mips("let a: integer[] = [7, 8, 9]; print(a[2]);").text
    assert "li $a0, 16" in text and "jal _alloc" in text  # 4 de longitud + 3 elementos de 4
    assert "sw $a0, 0($v0)" in text and "12($v0)" in text


@pytest.mark.parametrize(
    "source, message",
    [
        ("let a: integer[] = [1, 2]; let i: integer = 2; print(a[i]);", "indice fuera de rango"),
        ("let a: integer[] = [1, 2]; let i: integer = 0 - 1; a[i] = 3;", "indice fuera de rango"),
    ],
)
def test_indice_invalido_termina_con_error(source, message):
    result = compile_to_mips(source)
    machine = run_mips(result.text, result.functions)
    assert machine.output == f"Error de ejecucion: {message}\n" and machine.exit_code == 1


def test_entero_se_convierte_al_llegar_a_un_float():
    text = compile_to_mips("function f(x: float): float { return x; } let n: integer = 2; print(f(n));").text
    assert "cvt.s.w $f0, $f0" in text and "jal _print_float" in text


def test_formato_de_float_con_digitos_minimos():
    assert [format_float(bits) for bits in (0x40600000, 0x40000000, 0x3DCCCCCD)] == ["3.5", "2.0", "0.1"]


# ---------------------------------------------------------------- bridge
def test_bridge_devuelve_ensamblador_salida_y_arbol():
    source = "function f(n: integer): integer { if (n < 2) { return n; } return f(n - 1) + f(n - 2); } print(f(3));"
    result = _run_action({"action": "compiscriptASM", "cpsSource": source, "registers": 3})
    assert result["ok"] is True and "f_f:" in result["asm"]
    assert result["output"] == "2\n" and result["exitCode"] == 0
    assert result["registers"] == ["$t0", "$t1", "$t2"]
    assert result["tree"]["children"][0]["arguments"] == ["3"] and "f(3) = 2" in result["treeText"]
    assert {row["function"] for row in result["allocationSummary"]} == {"main", "f"}
    assert result["instructionCount"] > 0 and isinstance(result["peephole"], dict)


def test_bridge_con_errores_no_genera_ensamblador():
    result = _run_action({"action": "compiscriptASM", "cpsSource": 'let x: integer = "a";'})
    assert result["ok"] is False and result["asm"] == "" and result["diagnostics"]


def test_bridge_reporta_el_error_de_ejecucion_del_programa():
    result = _run_action({"action": "compiscriptASM", "cpsSource": "let z: integer = 0; print(1 / z);"})
    assert result["exitCode"] == 1 and "division por cero" in result["output"]


# ---------------------------------------------------------------- MARS
@pytest.mark.skipif(not MARS.exists() or shutil.which("java") is None, reason="requiere Java y tools/mars/Mars4_5.jar")
@pytest.mark.parametrize("source", EXPECTED, ids=["arreglos", "ordenamiento", "flotantes"])
def test_mars_produce_la_misma_salida_que_el_simulador(source, tmp_path):
    file = tmp_path / "programa.asm"
    file.write_text(compile_to_mips(source, registers=THREE).text, encoding="utf-8")
    done = subprocess.run(["java", "-jar", str(MARS), "nc", str(file)], capture_output=True, text=True, timeout=120)
    assert done.stdout.rstrip().splitlines() == EXPECTED[source]
