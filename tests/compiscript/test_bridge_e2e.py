"""Pruebas end-to-end del bridge: el mismo camino que sigue el IDE.

El IDE (src-tauri/src/lib.rs) lanza `python src/bridge_cli.py`, escribe el payload JSON
por stdin y lee un unico objeto JSON de stdout, que decodifica como UTF-8:

    {"ok": true,  "result": {...}}      codigo de salida 0
    {"ok": false, "error": "mensaje"}   codigo de salida 1

Aqui se hace exactamente eso, como subproceso y sin variables de entorno de UTF-8, para
cubrir lo que `_run_action` (usado en el resto de las pruebas) no ve: el proceso, la
codificacion de stdin/stdout, las rutas de archivo y el formato del sobre.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "src" / "bridge_cli.py"
SAMPLES = ROOT / "tests" / "compiscript" / "samples"
VALID = ROOT / "tests" / "compiscript" / "intermediate" / "valid"
TYPES_TS = ROOT / "src" / "desktop-app" / "src" / "types.ts"

# Orden en que el IDE ejecuta el pipeline de Compiscript (COMPISCRIPT_ACTIONS en App.tsx).
PIPELINE = ["compiscriptCheck", "compiscriptSymbols", "compiscriptTree", "compiscriptTAC"]


def call_bridge(payload, cwd=None, raw: bytes | None = None):
    """Ejecuta el bridge como lo hace Tauri. Devuelve (codigo, sobre JSON, stderr)."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    data = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    done = subprocess.run(
        [sys.executable, str(BRIDGE)],
        input=data,
        capture_output=True,
        cwd=cwd or ROOT,
        env=env,
        timeout=120,
    )
    stdout = done.stdout.decode("utf-8")  # estricto: Tauri decodifica la salida como UTF-8
    return done.returncode, json.loads(stdout), done.stderr.decode("utf-8", errors="replace")


def result_of(payload, cwd=None):
    code, envelope, stderr = call_bridge(payload, cwd)
    assert code == 0, (envelope, stderr)
    assert set(envelope) == {"ok", "result"} and envelope["ok"] is True
    return envelope["result"]


# --------------------------------------------------------------------------- pipeline del IDE
def test_pipeline_completo_sobre_un_archivo_por_ruta():
    path = str(SAMPLES / "animals.cps")
    results = {action: result_of({"action": action, "cpsPath": path}) for action in PIPELINE}

    check = results["compiscriptCheck"]
    assert check["ok"] is True and check["syntaxErrors"] == [] and check["diagnostics"] == []

    scope = results["compiscriptSymbols"]["scope"]
    assert scope["kind"] == "global" and scope["symbols"]["Animal"]["kind"] == "class"
    assert "layout" in results["compiscriptSymbols"]

    tree = results["compiscriptTree"]["tree"]
    assert tree["kind"] == "rule" and tree["label"] == "program" and tree["children"]

    tac = results["compiscriptTAC"]
    assert tac["ok"] is True and tac["tac"]
    assert "halt" in tac["text"].splitlines()
    assert any(r["name"] == "main" for r in tac["layout"]["records"])
    assert tac["layoutText"].startswith("area estatica")


def test_cps_source_y_cps_path_producen_el_mismo_resultado(tmp_path):
    source = (SAMPLES / "animals.cps").read_text(encoding="utf-8")
    by_source = result_of({"action": "compiscriptTAC", "cpsSource": source})
    by_path = result_of({"action": "compiscriptTAC", "cpsPath": str(SAMPLES / "animals.cps")})
    assert by_source == by_path


def test_el_resultado_no_depende_del_directorio_de_trabajo(tmp_path):
    payload = {"action": "compiscriptTAC", "cpsPath": str(SAMPLES / "animals.cps")}
    assert result_of(payload, cwd=tmp_path) == result_of(payload, cwd=ROOT)


def test_ruta_con_espacios_y_acentos(tmp_path):
    folder = tmp_path / "Proyecto de Compiladores ñandú"
    folder.mkdir()
    file = folder / "programa con acentos.cps"
    file.write_text('let a: integer = 1;\nprint(a);\n', encoding="utf-8")
    result = result_of({"action": "compiscriptTAC", "cpsPath": str(file)})
    assert result["ok"] is True and "print a" in result["text"].splitlines()


@pytest.mark.parametrize(
    "name",
    [
        "closure_acumular",
        "polimorfismo_despacho_dinamico",
        "foreach_continue_y_break",
        "switch_caida_y_default",
        "arreglos_y_matrices",
        "clases_campos_y_metodos",
    ],
)
def test_programas_del_conjunto_de_pruebas_pasan_por_el_bridge(name):
    source = (VALID / f"{name}.cps").read_text(encoding="utf-8")
    result = result_of({"action": "compiscriptTAC", "cpsSource": source})
    assert result["ok"] is True, result["diagnostics"]
    assert result["tac"] and result["layout"]["records"]


# --------------------------------------------------------------------------- errores del programa
def test_programa_con_errores_semanticos_devuelve_diagnosticos_y_no_genera_tac():
    path = str(SAMPLES / "multiples_errores.cps")
    check = result_of({"action": "compiscriptCheck", "cpsPath": path})
    assert check["ok"] is False
    codes = {d["code"] for d in check["diagnostics"]}
    assert {"SEM-CLASS-001", "SEM-FUNC-003", "SEM-FLOW-001"} <= codes

    tac = result_of({"action": "compiscriptTAC", "cpsPath": path})
    assert tac["ok"] is False and tac["tac"] == [] and tac["text"] == ""
    assert "layout" not in tac and tac["diagnostics"] == check["diagnostics"]


def test_error_de_sintaxis_se_reporta_sin_romper_el_bridge():
    result = result_of({"action": "compiscriptTAC", "cpsSource": "let x: integer = 1\nprint(x);"})
    assert result["ok"] is False and result["syntaxErrors"] and result["tac"] == []


# --------------------------------------------------------------------------- errores del bridge
@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({}, "action"),
        ({"action": "accionInexistente"}, "no soportada"),
        ({"action": "compiscriptTAC"}, "cpsPath"),
        ({"action": "compiscriptTAC", "cpsPath": "no/existe/programa.cps"}, "no encontrado"),
    ],
)
def test_fallos_del_bridge_devuelven_ok_false_y_codigo_1(payload, fragment):
    code, envelope, _ = call_bridge(payload)
    assert code == 1
    assert envelope["ok"] is False and fragment in envelope["error"]
    assert "result" not in envelope


@pytest.mark.parametrize("raw", [b"", b"   \n", b"{no es json", b"[1, 2"])
def test_entrada_vacia_o_invalida_devuelve_error_json(raw):
    code, envelope, _ = call_bridge(None, raw=raw)
    assert code == 1 and envelope["ok"] is False and envelope["error"]


# --------------------------------------------------------------------------- codificacion
def test_texto_con_acentos_y_caracteres_fuera_de_cp1252_viaja_intacto():
    """Tauri lee stdout como UTF-8; en Windows Python escribiria con la codificacion local."""
    # El emoji va como escape: tests/test_repo_style.py prohibe emojis literales en el repositorio.
    message = "canción → 日本語 \U0001F600 ñandú"
    result = result_of(
        {"action": "compiscriptTAC", "cpsSource": f'// {message}\nprint("{message}");\n'}
    )
    assert result["ok"] is True
    assert f'print "{message}"' in result["text"].splitlines()
    assert any(i["op"] == "print" and i["arg1"] == f'"{message}"' for i in result["tac"])


def test_error_con_caracteres_unicode_tambien_es_json_valido():
    code, envelope, _ = call_bridge({"action": "compiscriptTAC", "cpsPath": "no/existe/ñandú→.cps"})
    assert code == 1 and "ñandú→" in envelope["error"]


# --------------------------------------------------------------------------- contrato con el IDE
def _ts_declares(name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\??:", TYPES_TS.read_text(encoding="utf-8")) is not None


def test_el_resultado_cumple_el_contrato_de_types_ts():
    source = (VALID / "closure_acumular.cps").read_text(encoding="utf-8")
    tac = result_of({"action": "compiscriptTAC", "cpsSource": source})

    top = {"ok", "syntaxErrors", "diagnostics", "tac", "text", "symbols", "layout", "layoutText"}
    assert set(tac) == top
    instruction = {"op", "arg1", "arg2", "result"}
    assert all(set(i) == instruction for i in tac["tac"])
    layout = {"dataArea", "records", "classes"}
    assert set(tac["layout"]) == layout
    record = {"name", "kind", "parent", "level", "control", "params", "locals", "temps", "frameSize"}
    assert all(set(r) == record for r in tac["layout"]["records"])
    slot = {"name", "type", "kind", "offset", "size"}
    assert all(set(s) == slot for r in tac["layout"]["records"] for s in r["params"] + r["locals"])

    symbol = {"kind", "name", "type", "isConst", "initialized", "line", "column", "storage", "offset", "frame", "size"}
    variable = next(iter(tac["symbols"]["children"][0]["symbols"].values()))
    assert symbol <= set(variable)

    for key in top | instruction | layout | record | slot | symbol:
        assert _ts_declares(key), f"types.ts no declara '{key}'"


def test_el_arbol_sintactico_cumple_el_contrato():
    tree = result_of({"action": "compiscriptTree", "cpsSource": "let x: integer = 1;"})["tree"]
    assert set(tree) == {"kind", "label", "line", "column", "children"}
    assert all(_ts_declares(k) for k in tree)


def test_las_acciones_del_pipeline_coinciden_con_las_del_ide():
    app = (ROOT / "src" / "desktop-app" / "src" / "App.tsx").read_text(encoding="utf-8")
    declared = re.findall(r'id: "(compiscript\w+)"', app)
    assert declared == PIPELINE
