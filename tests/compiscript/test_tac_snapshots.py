"""Salida exacta del TAC para cada construccion (pruebas de regresion).

Si un cambio intencional altera el formato, hay que actualizar tambien
docs/Lenguaje_Intermedio.md, que muestra estos mismos ejemplos.
"""
import sys
import textwrap
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bridge_cli import _run_action  # noqa: E402

SNAPSHOTS = {
    "expresion_con_reciclaje": (
        "let a: integer = 1; let b: integer = 2; let c: integer = 3;"
        "let r: integer = (a + b) * (a - c) + b * c;",
        """
        a = 1
        b = 2
        c = 3
        t0 = a + b
        t1 = a - c
        t2 = t0 * t1
        t1 = b * c
        t0 = t2 + t1
        r = t0
        halt
        """,
    ),
    "if_else": (
        "let x: integer = 3; if (x > 1) { print(1); } else { print(2); }",
        """
        x = 3
        t0 = x > 1
        ifFalse t0 goto else0
        print 1
        goto endif1
        else0:
        print 2
        endif1:
        halt
        """,
    ),
    "if_sin_else": (
        "let x: integer = 3; if (x > 1) { print(1); }",
        """
        x = 3
        t0 = x > 1
        ifFalse t0 goto else0
        print 1
        else0:
        halt
        """,
    ),
    "while": (
        "let i: integer = 0; while (i < 3) { i = i + 1; }",
        """
        i = 0
        while0:
        t0 = i < 3
        ifFalse t0 goto endwhile1
        t0 = i + 1
        i = t0
        goto while0
        endwhile1:
        halt
        """,
    ),
    "do_while": (
        "let i: integer = 0; do { i = i + 1; } while (i < 3);",
        """
        i = 0
        do0:
        t0 = i + 1
        i = t0
        docond2:
        t0 = i < 3
        if t0 goto do0
        enddo1:
        halt
        """,
    ),
    "for": (
        "for (let i: integer = 0; i < 3; i = i + 1) { print(i); }",
        """
        i = 0
        for0:
        t0 = i < 3
        ifFalse t0 goto endfor1
        print i
        increment2:
        t0 = i + 1
        i = t0
        goto for0
        endfor1:
        halt
        """,
    ),
    "foreach": (
        "let xs: integer[] = [1, 2]; foreach (v in xs) { print(v); }",
        """
        t0 = array 1, 2
        xs = t0
        t0 = 0
        t1 = length xs
        foreach0:
        t2 = t0 < t1
        ifFalse t2 goto endforeach1
        t2 = xs[t0]
        v = t2
        print v
        foreachnext2:
        t2 = t0 + 1
        t0 = t2
        goto foreach0
        endforeach1:
        halt
        """,
    ),
    "switch": (
        "let x: integer = 2; switch (x) { case 1: print(1); case 2: print(2); default: print(0); }",
        """
        x = 2
        t0 = x == 1
        if t0 goto case1
        t0 = x == 2
        if t0 goto case2
        goto default3
        case1:
        print 1
        case2:
        print 2
        default3:
        print 0
        endswitch0:
        halt
        """,
    ),
    "try_catch": (
        "try { print(1); } catch (e) { print(e); }",
        """
        try goto catch0
        print 1
        goto endtry1
        catch0:
        e = exception
        print e
        endtry1:
        halt
        """,
    ),
    "ternario": (
        "let a: integer = 1; let b: integer = 2; let m: integer = a < b ? a : b;",
        """
        a = 1
        b = 2
        t0 = a < b
        ifFalse t0 goto false0
        t1 = a
        goto endternary1
        false0:
        t1 = b
        endternary1:
        m = t1
        halt
        """,
    ),
    "funcion_y_llamada": (
        "function suma(a: integer, b: integer): integer { return a + b; } let r: integer = suma(1, 2);",
        """
        param 1
        param 2
        t0 = call suma, 2
        r = t0
        halt
        function suma
        param_decl a
        param_decl b
        t0 = a + b
        return t0
        end function suma
        """,
    ),
    "closure": (
        "function acumular(inicio: integer, paso: integer): integer { let actual: integer = inicio; "
        "function siguiente(incremento: integer): integer { return actual + incremento; } "
        "return siguiente(paso); }",
        """
        halt
        function acumular
        param_decl inicio
        param_decl paso
        actual = inicio
        param paso
        link 0
        t0 = call acumular.siguiente, 1
        return t0
        end function acumular
        function acumular.siguiente
        param_decl incremento
        t0 = up(1).actual
        t1 = t0 + incremento
        return t1
        end function acumular.siguiente
        """,
    ),
    "matriz": (
        "let m: integer[][] = [[1, 2], [3, 4]]; m[1][0] = 9; print(m[0][1]);",
        """
        t0 = array 1, 2
        t1 = array 3, 4
        t2 = array t0, t1
        m = t2
        t2 = m[1]
        t2[0] = 9
        t2 = m[0]
        t1 = t2[1]
        print t1
        halt
        """,
    ),
    "clase": (
        "class A { let n: integer = 1; function constructor(k: integer) { this.n = k; } "
        "function get(): integer { return this.n; } } let o: A = new A(5); o.n = 7; print(o.get());",
        """
        param 5
        t0 = new A, 1
        o = t0
        o.n = 7
        param o
        t0 = invoke o.get, 1
        print t0
        halt
        function A.constructor
        param_decl this
        param_decl k
        this.n = 1
        this.n = k
        end function A.constructor
        function A.get
        param_decl this
        t0 = this.n
        return t0
        end function A.get
        """,
    ),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOTS))
def test_snapshot_del_tac(name):
    source, expected = SNAPSHOTS[name]
    result = _run_action({"action": "compiscriptTAC", "cpsSource": source})
    assert result["ok"] is True, result
    assert result["text"] == textwrap.dedent(expected).strip()
