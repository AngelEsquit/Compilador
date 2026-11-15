"""Mirilla: reglas de flujo de control (saltos innecesarios, encadenados y codigo inalcanzable)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC / "compiscript"))
sys.path.insert(0, str(SRC))

from compiscript.backend import compile_to_mips  # noqa: E402
from compiscript.backend.asm import parse_lines  # noqa: E402
from compiscript.backend.peephole import optimize
from compiscript.backend.peephole.flow import chained_jumps  # noqa: E402
from compiscript.backend.simulator import run_mips  # noqa: E402


def optimized(source: str):
    """Optimiza el texto ensamblador y lo devuelve como lista de lineas de texto sin comentarios."""
    lines, applied = optimize(parse_lines(source))
    return [line.to_text().strip() for line in lines if line.kind != "comment"], applied


def test_salto_a_la_siguiente_instruccion():
    out, applied = optimized("j L\nL:\nmove $t0, $t1\n")
    assert out == ["L:", "move $t0, $t1"]
    assert applied["salto a la siguiente instruccion"] == 1


def test_salto_condicional_a_la_siguiente_instruccion():
    out, _ = optimized("beqz $t0, L\n# nota\nL:\nmove $t0, $t1\n")
    assert out == ["L:", "move $t0, $t1"]


def test_un_salto_a_otra_etiqueta_se_conserva():
    out, applied = optimized("j M\nL:\nmove $t0, $t1\nM:\nmove $t1, $t2\n")
    assert out[0] == "j M" and applied["salto a la siguiente instruccion"] == 0


def test_salto_sobre_salto():
    out, applied = optimized("beqz $t0, L1\nj L2\nL1:\nmove $t1, $t2\nL2:\njr $ra\n")
    assert out == ["bnez $t0, L2", "L1:", "move $t1, $t2", "L2:", "jr $ra"]
    assert applied["salto sobre salto"] == 1


def test_salto_sobre_salto_con_comparacion_de_dos_registros():
    out, _ = optimized("blt $t0, $t1, L1\nj L2\nL1:\nmove $t1, $t2\nL2:\njr $ra\n")
    assert out[0] == "bge $t0, $t1, L2"


def test_codigo_inalcanzable_despues_de_un_salto():
    out, applied = optimized("j L\nmove $t0, $t1\nmove $t1, $t2\nL:\njr $ra\n")
    assert out == ["j L", "L:", "jr $ra"] or out == ["L:", "jr $ra"]
    assert applied["codigo inalcanzable"] == 2


def test_codigo_inalcanzable_despues_de_un_retorno():
    out, _ = optimized("jr $ra\nmove $t0, $t1\nL:\nmove $t1, $t2\n")
    assert out == ["jr $ra", "L:", "move $t1, $t2"]


def test_el_codigo_tras_una_etiqueta_es_alcanzable():
    out, applied = optimized("j M\nL:\nmove $t0, $t1\nM:\nmove $t1, $t2\n")
    assert "move $t0, $t1" in out and applied["codigo inalcanzable"] == 0


def test_saltos_encadenados():
    lines, count = chained_jumps(parse_lines("j L1\nmove $t0, $t1\nL1:\nj L2\nmove $t1, $t1\nL2:\njr $ra\n"))
    assert count == 1 and lines[0].args == ("L2",)


def test_saltos_encadenados_conservan_la_salida():
    show = "li $v0, 1\nsyscall\n"
    body = f"j L1\nli $a0, 1\n{show}L1:\nj L2\nli $a0, 2\n{show}L2:\nli $a0, 7\n{show}"
    assert run_equivalent(body)


def test_saltos_encadenados_en_un_salto_condicional():
    lines, count = chained_jumps(parse_lines("beqz $t0, L1\nmove $t1, $t2\nL1:\nj L2\nmove $t3, $t3\nL2:\njr $ra\n"))
    assert count == 1 and lines[0].args == ("$t0", "L2")


def test_un_bucle_de_un_solo_salto_no_cicla():
    out, _ = optimized("L:\nj L\n")
    assert out == ["L:", "j L"]


def test_las_lineas_de_comentario_no_se_pierden():
    lines, _ = optimize(parse_lines("j L\n# conserva esto\nL:\nmove $t0, $t1\n"))
    assert [line.comment for line in lines if line.kind == "comment"] == ["conserva esto"]


def test_las_reglas_no_modifican_la_entrada():
    original = parse_lines("beqz $t0, L1\nj L2\nL1:\nmove $t1, $t2\nL2:\njr $ra\n")
    snapshot = [line.to_text() for line in original]
    optimize(original)
    assert [line.to_text() for line in original] == snapshot


def run_equivalent(body: str) -> bool:
    """El cuerpo da la misma salida con y sin optimizar."""
    source = ".text\nmain:\n" + body + "\nli $v0, 10\nsyscall\n"
    lines = parse_lines(source)
    optimized_lines, _ = optimize(lines)
    text = ".text\n" + "\n".join(line.to_text() for line in optimized_lines) + "\n"
    return run_mips(source).output == run_mips(text).output


PROGRAM = """
function pares(n: integer): integer {
    let total: integer = 0;
    for (let i: integer = 0; i < n; i = i + 1) {
        if (i % 2 == 1) { continue; }
        if (i > 8) { break; }
        total = total + i;
    }
    return total;
}
print(pares(20));
"""


def test_la_mirilla_de_flujo_reduce_un_programa_real_sin_cambiar_su_salida():
    plain = compile_to_mips(PROGRAM, peephole=False)
    better = compile_to_mips(PROGRAM)
    assert len(better.program.text) < len(plain.program.text)
    assert run_mips(better.text).output == run_mips(plain.text).output == "20\n"
