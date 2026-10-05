"""Registros de activacion, area estatica y layout de clases."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bridge_cli import _run_action  # noqa: E402


def _layout(source: str) -> dict:
    result = _run_action({"action": "compiscriptTAC", "cpsSource": source})
    assert result["ok"] is True, result
    return result["layout"]


def _record(layout: dict, name: str) -> dict:
    return next(r for r in layout["records"] if r["name"] == name)


def _slots(record: dict) -> dict:
    return {s["name"]: s for s in record["params"] + record["locals"]}


def test_globales_van_al_area_estatica_con_tamano_y_alineacion():
    layout = _layout('let a: integer = 1; let b: boolean = true; let c: string = "s"; let d: float = 1.5;')
    data = {s["name"]: s for s in layout["dataArea"]["symbols"]}
    assert (data["a"]["offset"], data["a"]["size"]) == (0, 4)
    assert (data["b"]["offset"], data["b"]["size"]) == (4, 1)
    assert data["c"]["offset"] == 8 and data["d"]["offset"] == 16
    assert layout["dataArea"]["size"] == 24


def test_registro_de_funcion_tiene_area_de_control_parametros_locales_y_temporales():
    layout = _layout(
        "function f(a: integer, b: float): integer { let x: integer = a + 1; return x * 2; } "
        "let r: integer = f(1, 2.0);"
    )
    record = _record(layout, "f")
    assert [c["name"] for c in record["control"]] == ["saved_fp", "return_address", "access_link"]
    slots = _slots(record)
    assert slots["a"]["offset"] == 24 and slots["a"]["size"] == 4
    assert slots["b"]["offset"] == 32 and slots["b"]["size"] == 8  # alineado a 8
    assert slots["x"]["offset"] == 40
    assert record["temps"]["count"] == 1  # t0 se recicla entre las dos expresiones
    assert record["temps"]["offset"] == 48
    assert record["frameSize"] == 56


def test_simbolos_quedan_anotados_con_storage_offset_y_frame():
    result = _run_action(
        {
            "action": "compiscriptTAC",
            "cpsSource": "function f(a: integer): integer { let x: integer = a; return x; }",
        }
    )
    function_scope = result["symbols"]["children"][0]
    assert function_scope["symbols"]["a"]["storage"] == "param"
    assert function_scope["symbols"]["a"]["frame"] == "f"
    block = function_scope["children"][0]
    assert block["symbols"]["x"]["storage"] == "local"
    assert block["symbols"]["x"]["offset"] == 28


def test_bloques_hermanos_reutilizan_espacio_del_frame():
    layout = _layout(
        "function f(c: boolean): integer { "
        "if (c) { let a: integer = 1; let b: integer = 2; } else { let z: integer = 3; } return 0; }"
    )
    slots = _slots(_record(layout, "f"))
    assert slots["z"]["offset"] == slots["a"]["offset"]
    # el frame cubre el bloque mas grande, no la suma de ambos
    assert _record(layout, "f")["temps"]["offset"] == 40


def test_funcion_anidada_registra_nivel_y_enlace_al_registro_que_la_encierra():
    layout = _layout(
        "function outer(): integer { function inner(): integer { return 1; } return inner(); }"
    )
    assert _record(layout, "outer")["level"] == 1
    inner = _record(layout, "inner")
    assert inner["level"] == 2 and inner["parent"] == "outer"


def test_metodos_reciben_this_como_primer_parametro():
    layout = _layout("class A { function f(n: integer): integer { return n; } }")
    slots = _slots(_record(layout, "A.f"))
    assert slots["this"]["offset"] == 24 and slots["n"]["offset"] == 32


def test_layout_de_clase_hereda_campos_y_sobrescribe_metodos():
    layout = _layout(
        "class A { let x: integer = 1; function m(): integer { return 1; } } "
        "class B : A { let y: integer = 2; function m(): integer { return 2; } function n(): integer { return 3; } }"
    )
    classes = {c["name"]: c for c in layout["classes"]}
    fields_b = {f["name"]: f["offset"] for f in classes["B"]["fields"]}
    assert fields_b == {"x": 8, "y": 16}  # B empieza donde termina A (16 bytes con relleno)
    assert classes["A"]["size"] == 16 and classes["B"]["size"] == 24
    methods = {m["name"]: m for m in classes["B"]["methods"]}
    assert methods["m"]["label"] == "B.m" and methods["m"]["slot"] == 0
    assert methods["n"]["slot"] == 1


def test_constructor_sintetizado_tiene_registro_con_this():
    layout = _layout("class C { let n: integer = 5; }")
    assert _slots(_record(layout, "C.constructor"))["this"]["offset"] == 24


def test_main_lleva_los_temporales_del_codigo_de_nivel_superior():
    layout = _layout("let a: integer = 1; let b: integer = (a + 1) * (a + 2);")
    main = _record(layout, "main")
    assert main["temps"]["count"] == 3
    assert main["frameSize"] == 24 + 3 * 8


def test_ciclo_de_herencia_no_rompe_el_layout():
    result = _run_action({"action": "compiscriptSymbols", "cpsSource": "class A : B {} class B : A {}"})
    assert "layout" in result


def test_layout_no_se_entrega_si_hay_errores_en_tac():
    result = _run_action({"action": "compiscriptTAC", "cpsSource": 'let x: integer = "no";'})
    assert result["ok"] is False and "layout" not in result
