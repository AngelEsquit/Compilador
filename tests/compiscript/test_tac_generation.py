"""Pruebas publicas de la representacion intermedia de Compiscript."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bridge_cli import _run_action  # noqa: E402


def test_tac_genera_temporales_y_control_de_flujo():
    result = _run_action(
        {
            "action": "compiscriptTAC",
            "cpsSource": "let x: integer = 1 + 2 * 3; while (x < 10) { x = x + 1; }",
        }
    )

    assert result["ok"] is True
    assert result["syntaxErrors"] == []
    assert result["diagnostics"] == []
    assert "t0 = 2 * 3" in result["text"]
    assert "goto while" in result["text"]
    assert any(instruction["op"] == "ifFalse" for instruction in result["tac"])


def test_tac_soporta_llamadas_arreglos_y_retorno():
    result = _run_action(
        {
            "action": "compiscriptTAC",
            "cpsSource": "function sum(a: integer): integer { return a + 1; } let xs = [1, 2]; print(sum(xs[0]));",
        }
    )

    assert result["ok"] is True, result
    assert "function sum" in result["text"]
    assert "= call sum" in result["text"]
    assert "index_load" not in result["text"]
    assert "xs[0]" in result["text"]


def test_tac_no_se_emite_si_hay_error():
    result = _run_action(
        {"action": "compiscriptTAC", "cpsSource": 'let x: integer = "texto";'}
    )

    assert result["ok"] is False
    assert result["tac"] == []
    assert result["text"] == ""


def test_tabla_de_simbolos_expone_ubicacion_de_almacenamiento():
    result = _run_action(
        {"action": "compiscriptSymbols", "cpsSource": "let x: integer = 1; let y: integer = 2;"}
    )

    assert result["scope"]["symbols"]["x"]["storage"] == "global[0]"
    assert result["scope"]["symbols"]["y"]["offset"] == 1