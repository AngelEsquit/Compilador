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
    assert lines.index("end function mk") < lines.index("function mk.inner")


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


CLOSURE = (
    "function outer(a: integer): integer { "
    "let total: integer = 0; "
    "function add(n: integer): integer { total = total + n; return total + a; } "
    "return add(a); }"
)


def test_closure_lee_y_escribe_variables_del_registro_externo():
    lines = _lines(CLOSURE)
    add = lines.index("function outer.add")
    body = lines[add : lines.index("end function outer.add")]
    assert "t0 = up(1).total" in body          # lectura de una variable capturada
    assert "up(1).total = t1" in body          # escritura de una variable capturada
    assert "t0 = up(1).a" in body or "t1 = up(1).a" in body or "t2 = up(1).a" in body


def test_variable_propia_de_la_funcion_no_usa_up():
    lines = _lines(CLOSURE)
    outer = lines[lines.index("function outer") : lines.index("end function outer")]
    assert not any("up(" in line for line in outer)
    assert "total = 0" in outer


def test_llamada_a_funcion_anidada_emite_link_antes_del_call():
    lines = _lines(CLOSURE)
    call = lines.index("t0 = call outer.add, 1")
    assert lines[call - 1] == "link 0"


def test_closure_a_dos_niveles_sube_dos_access_links():
    lines = _lines(
        "function f(): integer { let x: integer = 1; "
        "function g(): integer { function h(): integer { return x; } return h(); } return g(); }"
    )
    h = lines.index("function f.g.h")
    assert lines[h + 1] == "t0 = up(2).x"


def test_llamada_recursiva_de_funcion_anidada_sube_un_access_link():
    lines = _lines(
        "function f(): integer { function g(n: integer): integer { "
        "if (n <= 0) { return 0; } return g(n - 1); } return g(3); }"
    )
    body = lines[lines.index("function f.g") : lines.index("end function f.g")]
    assert "link 1" in body  # el padre de g es el mismo que el de la llamada recursiva


def test_funciones_anidadas_homonimas_no_chocan_en_el_tac():
    lines = _lines(
        "function a(): integer { function inner(): integer { return 1; } return inner(); } "
        "function b(): integer { function inner(): integer { return 2; } return inner(); }"
    )
    assert "function a.inner" in lines and "function b.inner" in lines
    assert "t0 = call a.inner, 0" in lines and "t0 = call b.inner, 0" in lines


def test_variable_global_no_se_trata_como_capturada():
    lines = _lines("let g: integer = 5; function f(): integer { return g + 1; }")
    assert not any("up(" in line for line in lines)


def test_variable_de_bloque_externo_dentro_de_foreach_se_alcanza_con_up():
    lines = _lines(
        "function f(xs: integer[]): integer { let s: integer = 0; "
        "function acc(n: integer): integer { s = s + n; return s; } "
        "foreach (v in xs) { acc(v); } return s; }"
    )
    assert "up(1).s = t1" in lines


def test_closure_con_error_semantico_no_genera_tac():
    result = _tac("function f(): integer { function g(): integer { return y; } return g(); }")
    assert result["ok"] is False and result["tac"] == []


def test_continue_en_foreach_salta_al_incremento_del_indice():
    lines = _lines(
        "let xs: integer[] = [1, 2]; foreach (v in xs) { if (v == 1) { continue; } print(v); }"
    )
    target = next(line for line in lines if line.startswith("goto foreachnext"))
    assert lines.index(target.removeprefix("goto ") + ":") < lines.index("goto foreach0")
    assert lines.index("foreachnext2:") > lines.index(target)
    # el incremento queda despues de la etiqueta, no antes
    assert lines[lines.index("foreachnext2:") + 1].endswith("+ 1")


def test_continue_en_do_while_evalua_la_condicion():
    lines = _lines("let i: integer = 0; do { i = i + 1; if (i == 1) { continue; } } while (i < 3);")
    condition = lines.index("docond2:")
    assert "goto docond2" in lines[:condition]
    assert lines[condition + 1] == "t0 = i < 3"


def test_operaciones_son_cuadruplas_con_el_operador_como_op():
    result = _tac("let a: integer = 2; let b: integer = -a * 3;")
    assert result["ok"] is True, result
    assert {"op": "neg", "arg1": "a", "arg2": "", "result": "t0"} in result["tac"]
    assert {"op": "*", "arg1": "t0", "arg2": "3", "result": "t1"} in result["tac"]


def test_foreach_termina_al_agotar_el_arreglo():
    lines = _lines("let xs: integer[] = [1, 2]; foreach (v in xs) { print(v); }")
    assert "t1 = length xs" in lines
    start = lines.index("foreach0:")
    assert lines[start + 1] == "t2 = t0 < t1"
    assert lines[start + 2] == "ifFalse t2 goto endforeach1"
