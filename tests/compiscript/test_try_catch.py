"""try/catch: errores de ejecucion, desinstalacion de manejadores y errores sin capturar.

Los programas que SI capturan el error estan en intermediate/valid/try_*.cps; aqui estan
los casos en los que el error NO debe capturarse (o el programa debe terminar):
un manejador que sigue instalado cuando ya no corresponde capturaria errores ajenos.
"""
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


def _compile(source: str) -> dict:
    result = _run_action({"action": "compiscriptTAC", "cpsSource": source})
    assert result["ok"] is True, result["diagnostics"] or result["syntaxErrors"]
    return result


def _run(source: str) -> list[str]:
    result = _compile(source)
    return run_tac(result["tac"], result["layout"])


def _uncaught(source: str, message: str) -> None:
    with pytest.raises(TACRuntimeError, match=f"excepcion no capturada: {message}"):
        _run(source)


ZERO = "let cero: integer = 0;\n"


# ------------------------------------------------------------------ errores sin capturar
def test_division_por_cero_sin_try_termina_el_programa():
    _uncaught(ZERO + "print(1);\nprint(10 / cero);", "division por cero")


def test_modulo_por_cero_sin_try_termina_el_programa():
    _uncaught(ZERO + "print(5 % cero);", "division por cero")


def test_indice_fuera_de_rango_sin_try_termina_el_programa():
    _uncaught("let xs: integer[] = [1];\nprint(xs[3]);", "indice fuera de rango")


def test_acceso_a_null_sin_try_termina_el_programa():
    _uncaught("class A { let x: integer = 1; }\nlet a: A = null;\nprint(a.x);", "acceso a null")


def test_el_error_de_una_funcion_sin_try_sube_hasta_main_y_termina():
    _uncaught(ZERO + "function f(): integer { return 1 / cero; }\nprint(f());", "division por cero")


def test_la_salida_previa_al_error_se_conserva_en_el_tac_pero_el_programa_aborta():
    result = _compile(ZERO + 'print("antes");\nprint(1 / cero);')
    with pytest.raises(TACRuntimeError):
        run_tac(result["tac"], result["layout"])


# ------------------------------------------------------------------ el manejador deja de estar activo
def test_un_manejador_se_consume_al_capturar_un_error():
    _uncaught(
        ZERO + 'try { print(1 / cero); } catch (e) { print("capturado"); }\nprint(2 / cero);',
        "division por cero",
    )


def test_un_error_dentro_del_catch_no_lo_captura_el_mismo_try():
    _uncaught(ZERO + "try { print(1 / cero); } catch (e) { print(2 / cero); }", "division por cero")


def test_return_dentro_del_try_desinstala_el_manejador():
    _uncaught(
        ZERO
        + "function g(): integer { try { return 1; } catch (e) { return 2; } }\n"
        + "print(g());\nprint(10 / cero);",
        "division por cero",
    )


def test_return_dentro_de_un_try_anidado_desinstala_ambos():
    _uncaught(
        ZERO
        + "function f(): integer { try { try { return 1; } catch (a) { return 2; } } catch (b) { return 3; } }\n"
        + "print(f());\nprint(10 / cero);",
        "division por cero",
    )


def test_return_dentro_del_catch_solo_desinstala_el_try_externo():
    # El manejador interno ya se consumio al capturar; el externo sigue activo hasta el return.
    source = (
        ZERO
        + "function f(): integer { try { try { return 1 / cero; } catch (a) { return 2; } } catch (b) { return 3; } }\n"
        + "print(f());\nprint(10 / cero);"
    )
    result = _compile(source)
    with pytest.raises(TACRuntimeError, match="division por cero"):
        run_tac(result["tac"], result["layout"])


def test_break_dentro_del_try_desinstala_el_manejador():
    _uncaught(
        ZERO
        + "let i: integer = 0;\nwhile (true) { i = i + 1; try { if (i == 2) { break; } } catch (e) { print(e); } }\n"
        + "print(10 / cero);",
        "division por cero",
    )


def test_continue_dentro_del_try_desinstala_el_manejador():
    _uncaught(
        ZERO
        + "let i: integer = 0;\nwhile (i < 3) { i = i + 1; try { if (i < 3) { continue; } } catch (e) { print(e); } }\n"
        + "print(10 / cero);",
        "division por cero",
    )


def test_break_en_un_try_dentro_de_un_foreach_anidado_desinstala_solo_lo_necesario():
    out = _run(
        ZERO
        + """
let xs: integer[] = [1, 2, 3];
try {
  foreach (v in xs) {
    try {
      if (v == 2) {
        break;
      }
    } catch (e) {
      print("interno");
    }
    print(v);
  }
  print(1 / cero);
} catch (e) {
  print("externo");
}
"""
    )
    # el break sale del try interno (que se desinstala) pero el externo sigue activo
    assert out == ["1", "externo"]


# ------------------------------------------------------------------ forma del TAC
def test_return_dentro_de_dos_try_emite_dos_endtry_antes_del_return():
    result = _compile(
        "function f(): integer { try { try { return 1; } catch (a) { return 2; } } catch (b) { return 3; } }"
    )
    lines = result["text"].splitlines()
    position = lines.index("return 1")
    assert lines[position - 2 : position] == ["endtry", "endtry"]


def test_el_valor_del_return_se_calcula_antes_de_desinstalar_el_manejador():
    lines = _compile(
        ZERO + "function f(d: integer): integer { try { return 10 / d; } catch (e) { return 0; } }"
    )["text"].splitlines()
    division = lines.index("t0 = 10 / d")
    assert lines[division : division + 3] == ["t0 = 10 / d", "endtry", "return t0"]


def test_cada_try_tiene_su_catch_que_lee_exception():
    source = (
        ZERO
        + "try { print(1); } catch (a) { print(a); }\n"
        + "function f(): integer { try { return 1; } catch (b) { return 2; } }"
    )
    tac = _compile(source)["tac"]
    for number, instruction in enumerate(tac):
        if instruction["op"] != "try":
            continue
        position = next(n for n, i in enumerate(tac) if i["op"] == "label" and i["result"] == instruction["result"])
        assert tac[position + 1]["op"] == "copy" and tac[position + 1]["arg1"] == "exception"


def test_las_operaciones_peligrosas_no_agregan_instrucciones_de_comprobacion():
    """Los errores de ejecucion son parte de la semantica de `/`, `%`, `[ ]` y `.`."""
    ops = {i["op"] for i in _compile(ZERO + "let xs: integer[] = [1];\nprint(10 / cero);\nprint(xs[0]);")["tac"]}
    assert ops <= {"copy", "/", "array", "index_load", "print", "halt"}
