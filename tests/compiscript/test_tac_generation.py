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

    symbols = result["scope"]["symbols"]
    assert symbols["x"]["storage"] == "global"
    assert (symbols["x"]["offset"], symbols["x"]["size"]) == (0, 4)
    assert symbols["y"]["offset"] == 4

def _tac(source: str) -> dict:
    return _run_action({"action": "compiscriptTAC", "cpsSource": source})


def _lines(source: str) -> list[str]:
    result = _tac(source)
    assert result["ok"] is True, result
    return result["text"].splitlines()


def test_new_emite_los_argumentos_antes_de_crear_el_objeto():
    lines = _lines(
        "class P { let x: integer; function constructor(x: integer) { this.x = x; } } "
        "let p: P = new P(3);"
    )
    assert lines.index("param 3") < lines.index("t0 = new P, 1")


def test_metodos_llevan_el_nombre_de_su_clase_y_this_implicito():
    lines = _lines(
        "class A { function f(): integer { return 1; } } "
        "class B { function f(): integer { return 2; } }"
    )
    assert "function A.f" in lines and "function B.f" in lines
    assert lines.count("param_decl this") == 2


def test_llamada_a_metodo_pasa_el_receptor_y_usa_invoke():
    lines = _lines(
        "class A { function f(n: integer): integer { return n; } } "
        "let a: A = new A(); print(a.f(7));"
    )
    assert lines.index("param a") + 1 == lines.index("param 7")
    assert "t0 = invoke a.f, 2" in lines


def test_inicializadores_de_campos_van_al_constructor_y_no_al_global():
    lines = _lines("class C { let n: integer = 5; } let z: integer = 1;")
    assert "n = 5" not in lines
    constructor = lines.index("function C.constructor")
    assert lines[constructor : constructor + 3] == [
        "function C.constructor",
        "param_decl this",
        "this.n = 5",
    ]


def test_asignacion_a_elemento_de_arreglo_emite_index_store():
    result = _tac("let xs: integer[] = [1, 2]; xs[0] = 9;")
    assert result["ok"] is True, result
    assert "xs[0] = 9" in result["text"].splitlines()
    assert any(i["op"] == "index_store" for i in result["tac"])


def test_asignacion_a_elemento_con_tipo_incorrecto_es_error_semantico():
    result = _tac('let xs: integer[] = [1, 2]; xs[0] = "texto";')
    assert result["ok"] is False
    assert result["tac"] == []
    assert any(d["code"] == "SEM-TYPE-003" for d in result["diagnostics"])


def test_cuerpos_de_funcion_quedan_despues_de_halt():
    lines = _lines("function f(): integer { return 1; } let x: integer = f();")
    assert lines.index("halt") < lines.index("function f")
    assert lines.index("x = t0") < lines.index("halt")


def test_funciones_anidadas_se_elevan_y_no_quedan_dentro_del_cuerpo_externo():
    lines = _lines(
        "function mk(): integer { function inner(): integer { return 1; } return inner(); }"
    )
    assert lines.index("end function mk") < lines.index("function inner")


def test_temporales_se_reinician_en_cada_funcion():
    lines = _lines(
        "let a: integer = 1; let b: integer = 2; let c: integer = a + b; "
        "function f(x: integer): integer { return x * 2; }"
    )
    function = lines.index("function f")
    assert lines[function:].count("t0 = x * 2") == 1


def test_variable_de_usuario_llamada_t1_no_se_recicla_ni_choca_con_temporales():
    lines = _lines("let t0: integer = 1; let t1: integer = 2; let r: integer = t0 + t1 * 3;")
    assert "t2 = t1 * 3" in lines
    assert "t3 = t0 + t2" in lines
    assert "r = t3" in lines


def test_temporales_se_reciclan_en_expresiones_aritmeticas():
    lines = _lines("let a: integer = 1; let b: integer = 2; let c: integer = (a + b) * (a - b) + a * b;")
    assigned = [line.split(" = ")[0] for line in lines if line.startswith("t")]
    assert len(set(assigned)) < len(assigned)
    assert max(int(name[1:]) for name in assigned) <= 2
