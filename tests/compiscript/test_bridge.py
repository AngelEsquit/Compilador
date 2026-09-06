"""Pruebas end-to-end del bridge JSON para las acciones de Compiscript.

Ejercita `bridge_cli._run_action` directamente (sin pasar por stdin/stdout)
para las tres acciones que consume el IDE de escritorio:
`compiscriptCheck`, `compiscriptSymbols` y `compiscriptTree`.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bridge_cli import _run_action  # noqa: E402

VALID_SOURCE = """
class Animal {
  let nombre: string;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return this.nombre + " hace ruido.";
  }
}

let a: Animal = new Animal("Toby");
print(a.hablar());
"""

INVALID_SOURCE = "let x: integer = \"no es un entero\";"


def test_compiscript_check_ok_sin_errores():
    result = _run_action({"action": "compiscriptCheck", "cpsSource": VALID_SOURCE})
    assert result["ok"] is True
    assert result["syntaxErrors"] == []
    assert result["diagnostics"] == []


def test_compiscript_check_reporta_diagnosticos():
    result = _run_action({"action": "compiscriptCheck", "cpsSource": INVALID_SOURCE})
    assert result["ok"] is False
    assert result["syntaxErrors"] == []
    codes = [d["code"] for d in result["diagnostics"]]
    assert "SEM-TYPE-003" in codes
    diag = result["diagnostics"][0]
    assert set(diag.keys()) == {"severity", "code", "message", "line", "column"}


def test_compiscript_symbols_serializa_tabla_global():
    result = _run_action(
        {
            "action": "compiscriptSymbols",
            "cpsSource": "let x: integer = 5;\nconst y: string = \"hola\";",
        }
    )
    scope = result["scope"]
    assert scope["kind"] == "global"
    assert "x" in scope["symbols"]
    assert scope["symbols"]["x"]["kind"] == "variable"
    assert scope["symbols"]["x"]["type"] == "integer"
    assert scope["symbols"]["y"]["kind"] == "constant"


def test_compiscript_symbols_incluye_clases_y_funciones_anidadas():
    result = _run_action(
        {
            "action": "compiscriptSymbols",
            "cpsSource": VALID_SOURCE,
        }
    )
    scope = result["scope"]
    assert "Animal" in scope["symbols"]
    assert scope["symbols"]["Animal"]["kind"] == "class"
    assert "hablar" in scope["symbols"]["Animal"]["methods"]


def test_compiscript_tree_devuelve_arbol_con_raiz_program():
    result = _run_action(
        {
            "action": "compiscriptTree",
            "cpsSource": "let x: integer = 1 + 2;",
        }
    )
    tree = result["tree"]
    assert result["syntaxErrors"] == []
    assert tree["kind"] == "rule"
    assert tree["label"] == "program"
    assert len(tree["children"]) > 0


def test_compiscript_tree_reporta_errores_de_sintaxis():
    result = _run_action(
        {
            "action": "compiscriptTree",
            "cpsSource": "let x integer = ;",
        }
    )
    assert result["syntaxErrors"] != []


def test_compiscript_check_requiere_cps_path_o_source():
    try:
        _run_action({"action": "compiscriptCheck"})
        assert False, "Se esperaba ValueError"
    except ValueError:
        pass
