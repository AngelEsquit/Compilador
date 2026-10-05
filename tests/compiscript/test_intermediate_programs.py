"""Programas completos: se traducen a TAC, se ejecutan con el interprete de referencia
y se compara lo que imprimen con las lineas `// expect:` del propio archivo.

- tests/compiscript/intermediate/valid/*.cps    deben generar TAC y producir la salida esperada
- tests/compiscript/intermediate/invalid/*.cps  no deben generar TAC (`// error: <codigo>`)
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for path in (SRC, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bridge_cli import _run_action  # noqa: E402
from tac_interpreter import TACRuntimeError, run_tac  # noqa: E402

VALID = sorted((HERE / "intermediate" / "valid").glob("*.cps"))
INVALID = sorted((HERE / "intermediate" / "invalid").glob("*.cps"))


def _compile(source: str) -> dict:
    return _run_action({"action": "compiscriptTAC", "cpsSource": source})


def _expected_output(source: str) -> list[str]:
    return [line.split("// expect:", 1)[1].strip() for line in source.splitlines() if line.startswith("// expect:")]


def test_hay_casos_de_prueba_cargados():
    assert len(VALID) >= 25 and len(INVALID) >= 8
    assert all(_expected_output(p.read_text(encoding="utf-8")) for p in VALID)  # ninguno es vacuo


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_programa_valido_produce_la_salida_esperada(path):
    source = path.read_text(encoding="utf-8")
    result = _compile(source)
    assert result["ok"] is True, result["diagnostics"] or result["syntaxErrors"]
    assert run_tac(result["tac"], result["layout"]) == _expected_output(source)


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_programa_valido_es_consistente_con_su_layout(path):
    result = _compile(path.read_text(encoding="utf-8"))
    layout = result["layout"]
    records = {r["name"]: r for r in layout["records"]}
    tac = result["tac"]

    # El programa principal termina en halt y ninguna instruccion de cuerpo queda antes.
    halt = next(n for n, i in enumerate(tac) if i["op"] == "halt")
    assert not any(i["op"] in ("function", "end_function", "param_decl") for i in tac[:halt])

    # Cada funcion emitida tiene registro, y sus temporales caben en el que se reservo.
    owner = "main"
    used: dict[str, int] = {}
    for n, ins in enumerate(tac):
        if ins["op"] == "function":
            owner = ins["result"]
            assert owner in records, owner
        elif n > halt and ins["op"] == "end_function":
            owner = "main"
        for field in ("arg1", "arg2", "result"):
            for name in re.findall(r"\bt(\d+)\b", ins[field]):
                used[owner] = max(used.get(owner, -1), int(name))
    source = path.read_text(encoding="utf-8")
    if not re.search(r"\blet t\d+\b", source):  # una variable de usuario t<n> no es un temporal
        for name, highest in used.items():
            assert highest < records[name]["temps"]["count"], (name, highest)

    for record in records.values():
        assert record["frameSize"] % 8 == 0
        assert record["temps"]["offset"] % 8 == 0


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_programa_invalido_no_genera_tac_ni_layout(path):
    source = path.read_text(encoding="utf-8")
    expected = re.search(r"// error: (\S+)", source).group(1)
    result = _compile(source)

    assert result["ok"] is False
    assert result["tac"] == [] and result["text"] == ""
    assert "layout" not in result
    if expected == "syntax":
        assert result["syntaxErrors"]
    elif expected == "any":
        assert result["syntaxErrors"] or result["diagnostics"]
    else:
        assert expected in {d["code"] for d in result["diagnostics"]}


def test_el_interprete_detecta_un_bucle_infinito():
    tac = [
        {"op": "label", "arg1": "", "arg2": "", "result": "L0"},
        {"op": "goto", "arg1": "", "arg2": "", "result": "L0"},
    ]
    with pytest.raises(TACRuntimeError):
        run_tac(tac, {"classes": []})
