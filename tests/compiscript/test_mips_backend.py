"""Pruebas unitarias del backend MIPS: bloques, seleccion de registros, registros de
activacion, biblioteca de ejecucion y simulador."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiscript.backend import compile_to_mips  # noqa: E402
from compiscript.backend.asm import INSTR, parse_lines  # noqa: E402
from compiscript.backend.blocks import liveness, next_uses, split_blocks  # noqa: E402
from compiscript.backend.operands import Const, Var  # noqa: E402
from compiscript.backend.peephole import optimize  # noqa: E402
from compiscript.backend.registers import MEM, RegisterAllocator  # noqa: E402
from compiscript.backend.simulator import SimulatorError, run_mips  # noqa: E402
from compiscript.intermediate.ir import Instruction  # noqa: E402
from compiscript.semantic.analyzer import analyze_source  # noqa: E402

THREE = ("$t0", "$t1", "$t2")


def run(source: str, **options) -> list[str]:
    result = compile_to_mips(source, **options)
    return run_mips(result.text, result.functions).output.splitlines()


def instructions(source: str, **options) -> list[str]:
    result = compile_to_mips(source, **options)
    return [line.to_text().split("#")[0].strip() for line in result.program.text if line.kind == INSTR]


def events(source: str, kind: str, **options) -> list[dict]:
    return [e for e in compile_to_mips(source, **options).allocation if e["event"] == kind]


# ---------------------------------------------------------------- bloques y vida
def tac(*rows) -> list[Instruction]:
    return [Instruction(*row) for row in rows]


def test_los_saltos_y_las_etiquetas_parten_bloques():
    code = tac(
        ("copy", "0", "", "i"),
        ("label", "", "", "L0"),
        ("<", "i", "3", "t0"),
        ("ifFalse", "t0", "", "L1"),
        ("+", "i", "1", "i"),
        ("goto", "", "", "L0"),
        ("label", "", "", "L1"),
        ("halt",),
    )
    blocks = split_blocks(code)
    assert [(b.start, b.end) for b in blocks] == [(0, 1), (1, 4), (4, 6), (6, 8)]
    assert [b.successors for b in blocks] == [[1], [3, 2], [1], []]


def test_el_catch_es_sucesor_de_los_bloques_del_try():
    code = tac(
        ("try", "", "", "catch0"),
        ("label", "", "", "L0"),
        ("/", "a", "b", "t0"),
        ("endtry",),
        ("goto", "", "", "fin"),
        ("label", "", "", "catch0"),
        ("label", "", "", "fin"),
        ("halt",),
    )
    blocks = split_blocks(code)
    catch = next(b.index for b in blocks if code[b.start] == Instruction("label", result="catch0"))
    assert catch in blocks[0].successors and catch in blocks[1].successors


def test_variables_vivas_y_siguiente_uso():
    i, t0 = Var("i", "$fp", 24, 4, "local"), Var("t0", "$fp", 32, 4, "temp")
    code = tac(
        ("label", "", "", "L0"),
        ("<", "i", "3", "t0"),
        ("ifFalse", "t0", "", "L1"),
        ("+", "i", "1", "i"),
        ("goto", "", "", "L0"),
        ("label", "", "", "L1"),
        ("halt",),
    )
    info = [([], []), ([i], [t0]), ([t0], []), ([i], [i]), ([], []), ([], []), ([], [])]
    blocks = split_blocks(code)
    liveness(blocks, info, set())
    assert blocks[0].live_in == {i} and blocks[0].live_out == {i}  # t0 muere en el salto
    assert blocks[1].live_out == {i}
    assert blocks[2].live_in == set()
    after = next_uses(blocks[0], info)
    assert after[1][t0] == 2 and t0 not in after[2]


# ---------------------------------------------------------------- seleccion de registros
class Recorder:
    def __init__(self):
        self.lines = []

    def __call__(self, op, *args, comment=""):
        self.lines.append((op, *args))


def allocator(registers=THREE):
    recorder = Recorder()
    return RegisterAllocator(registers, recorder), recorder


def local(name: str, offset: int) -> Var:
    return Var(name, "$fp", offset, 4, "local")


def test_usa_un_registro_libre_y_no_recarga_lo_que_ya_tiene():
    regs, out = allocator()
    a = local("a", 24)
    regs.begin({a: 5})
    first = regs.use(a)
    regs.begin({})
    assert regs.use(a) == first
    assert out.lines == [("lw", first, "24($fp)")]
    assert regs.reg_desc[first] == {a} and regs.locations(a) == {MEM, first}


def test_el_resultado_reutiliza_el_registro_de_un_operando_que_muere():
    regs, out = allocator()
    a, b, x = local("a", 24), local("b", 28), local("x", 32)
    regs.begin({x: 9})  # despues de `x = a + b` solo x sigue viva
    ra, rb = regs.use(a), regs.use(b)
    assert regs.define(x) == ra
    assert regs.reg_desc[ra] == {x} and regs.locations(x) == {ra}
    assert regs.locations(a) == {MEM} and regs.reg_desc[rb] == {b}


def test_desaloja_sin_guardar_cuando_el_valor_tambien_esta_en_memoria():
    regs, out = allocator()
    a, b, c, d = (local(n, 24 + 4 * k) for k, n in enumerate("abcd"))
    regs.begin({a: 1, b: 2, c: 3})
    for var in (a, b, c):
        regs.use(var)
    regs.begin({a: 1, b: 2, c: 3})
    regs.use(d)
    assert [line[0] for line in out.lines] == ["lw", "lw", "lw", "lw"]  # ningun `sw`


def test_derrama_el_valor_que_se_usa_mas_tarde():
    regs, out = allocator()
    x, y, z, w = (local(n, 24 + 4 * k) for k, n in enumerate("xyzw"))
    for var in (x, y, z):  # tres valores nuevos: solo existen en registros
        regs.begin({})
        regs.define(var)
    regs.begin({x: 10, y: 50, z: 20})  # y es el que se usa mas tarde
    regs.use(w)
    assert ("sw", "$t1", "28($fp)") in out.lines
    assert regs.locations(y) == {MEM}
    assert [e["event"] for e in regs.events].count("derrame") == 1


def test_un_valor_muerto_pierde_su_registro_sin_guardarse():
    regs, out = allocator()
    x, y, z, w = (local(n, 24 + 4 * k) for k, n in enumerate("xyzw"))
    for var in (x, y, z):
        regs.begin({})
        regs.define(var)
    regs.begin({x: 10, z: 20})  # y ya no se usa
    assert regs.use(w) == "$t1"
    assert not any(line[0] == "sw" for line in out.lines)


def test_la_copia_no_emite_codigo():
    regs, out = allocator()
    a, x = local("a", 24), local("x", 28)
    regs.begin({a: 3, x: 4})
    reg = regs.use(a)
    regs.alias(x, reg)
    assert out.lines == [("lw", reg, "24($fp)")]
    assert regs.reg_desc[reg] == {a, x} and regs.locations(x) == {reg}


def test_al_cerrar_el_bloque_solo_se_guardan_las_vivas_modificadas():
    regs, out = allocator()
    a, x, t = local("a", 24), local("x", 28), Var("t0", "$fp", 40, 4, "temp")
    regs.begin({a: 9, x: 9})
    regs.use(a)  # cargada, sin modificar
    regs.define(x)  # modificada y viva
    regs.define(t)  # modificada pero muerta
    out.lines.clear()
    regs.flush({a, x})
    assert out.lines == [("sw", "$t1", "28($fp)")]
    assert all(not held for held in regs.reg_desc.values())


def test_la_constante_cero_usa_el_registro_zero():
    regs, out = allocator()
    regs.begin({})
    assert regs.use(Const("0")) == "$zero"
    assert regs.use(Const("7")) == "$t0" and out.lines == [("li", "$t0", "7")]


def test_exige_al_menos_tres_registros():
    with pytest.raises(ValueError):
        RegisterAllocator(("$t0", "$t1"), lambda *a, **k: None)


SPILL_PROGRAM = """
function f(a: integer, b: integer, c: integer, d: integer): integer {
  return (a + b) * (c + d) + (a - b) * (c - d);
}
print(f(7, 3, 5, 2));
"""


def test_con_pocos_registros_hay_derrames_y_el_resultado_no_cambia():
    assert events(SPILL_PROGRAM, "derrame") == []
    assert events(SPILL_PROGRAM, "derrame", registers=THREE)
    assert run(SPILL_PROGRAM) == run(SPILL_PROGRAM, registers=THREE) == ["82"]


def test_un_temporal_muerto_no_se_guarda_en_memoria():
    code = instructions("let a: integer = 2; let b: integer = a * 3 + 1; print(b);")
    assert not any(line.startswith(("sw", "sb")) and "($fp)" in line for line in code if line != "sw $fp, 4($gp)")


# ---------------------------------------------------------------- registros de activacion
FRAME_PROGRAM = """
let g: integer = 10;
function suma(a: integer, ok: boolean): integer {
  let local: integer = a + g;
  if (ok) { return local; }
  return 0;
}
print(suma(5, true));
"""


def test_el_prologo_respeta_el_registro_de_activacion_calculado():
    analyzer, _ = analyze_source(FRAME_PROGRAM)
    result = compile_to_mips(FRAME_PROGRAM, analyzer)
    record = analyzer.layout.records["suma"]
    code = [line.to_text().split("#")[0].strip() for line in result.program.text if line.kind == INSTR]
    size = record.frame_size
    start = code.index(f"addiu $sp, $sp, -{size}")
    assert code[start + 1 : start + 4] == ["sw $fp, 0($sp)", "sw $ra, 8($sp)", "move $fp, $sp"]
    a, ok = record.params
    # los argumentos se apilan de izquierda a derecha: el ultimo queda justo sobre el registro
    assert code[start + 4 : start + 8] == [
        f"lw $a0, {size + 4}($fp)",
        f"sw $a0, {a.offset}($fp)",
        f"lw $a0, {size}($fp)",
        f"sb $a0, {ok.offset}($fp)",
    ]
    assert f"addiu $sp, $sp, {size}" in code and "jr $ra" in code
    assert result.functions["f_suma"]["frameSize"] == size


def test_las_globales_viven_en_el_area_estatica_y_se_guardan_antes_de_llamar():
    analyzer, _ = analyze_source(FRAME_PROGRAM)
    code = instructions(FRAME_PROGRAM, analyzer=analyzer)
    g = next(s for s in analyzer.layout.data_symbols if s.name == "g")
    stores = [n for n, line in enumerate(code) if line.startswith("sw") and line.endswith(f"{g.offset}($gp)")]
    assert stores and stores[0] < code.index("jal f_suma")
    assert any(line.startswith("lw") and line.endswith(f"{g.offset}($gp)") for line in code)


def test_recursividad_y_arbol_de_activacion():
    source = """
    function fib(n: integer): integer {
      if (n < 2) { return n; }
      return fib(n - 1) + fib(n - 2);
    }
    print(fib(4));
    """
    result = compile_to_mips(source)
    machine = run_mips(result.text, result.functions)
    assert machine.output == "3\n"
    root = machine.root
    assert root.name == "main" and [c.name for c in root.children] == ["fib"]
    top = root.children[0]
    assert (top.arguments, top.result) == (["4"], "3")
    assert [(c.arguments, c.result) for c in top.children] == [(["3"], "2"), (["2"], "1")]
    assert "fib(4) = 3" in root.to_text()


def test_funcion_anidada_escribe_la_variable_de_la_que_la_encierra():
    source = """
    function contador(): integer {
      let total: integer = 0;
      function sumar(n: integer) { total = total + n; }
      sumar(2);
      sumar(5);
      return total;
    }
    print(contador());
    """
    assert run(source) == run(source, registers=THREE) == ["7"]


# ---------------------------------------------------------------- expresiones y control
def test_division_por_cero_termina_con_error():
    result = compile_to_mips("let cero: integer = 0; print(10 / cero);")
    machine = run_mips(result.text, result.functions)
    assert machine.output == "Error de ejecucion: division por cero\n" and machine.exit_code == 1


def test_cadenas_concatenacion_y_comparacion():
    source = 'let a: string = "ho"; let b: string = a + "la"; print(b); print(b == "hola"); print(b != "hola");'
    assert run(source) == ["hola", "true", "false"]


def test_solo_se_incluyen_las_rutinas_que_se_usan():
    text = compile_to_mips("print(1);").text
    assert "_print_int:" in text and "_concat:" not in text and "_throw:" not in text


# ---------------------------------------------------------------- formato, mirilla y simulador
def test_el_texto_generado_se_puede_volver_a_leer():
    result = compile_to_mips(SPILL_PROGRAM)
    again = parse_lines(result.text)
    assert [line.to_text() for line in again if line.kind == INSTR] == [
        line.to_text() for line in result.program.text if line.kind == INSTR
    ]


def test_la_mirilla_sin_reglas_no_cambia_el_programa():
    lines = compile_to_mips(SPILL_PROGRAM, peephole=False).program.text
    optimized, applied = optimize(list(lines))
    assert optimized == lines and applied == {}


def simulate(body: str) -> str:
    return run_mips(".text\nmain:\n" + body + "\n li $v0, 10\n syscall\n").output


def test_simulador_aritmetica_memoria_y_saltos():
    out = simulate(
        """
        li $t0, -7
        li $t1, 2
        div $t0, $t1
        mflo $a0
        li $v0, 1
        syscall
        mfhi $a0
        syscall
        addiu $sp, $sp, -8
        sw $t0, 4($sp)
        lw $a0, 4($sp)
        blt $a0, $zero, negativo
        li $a0, 0
    negativo:
        syscall
        """
    )
    assert out == "-3-1-7"  # la division trunca hacia cero, como en MIPS


def test_simulador_datos_y_cadenas():
    source = '.data\nmsg: .asciiz "a\\nb"\nn: .word 5, 6\n.text\nmain:\n la $a0, msg\n li $v0, 4\n syscall\n'
    source += " la $t0, n\n lw $a0, 4($t0)\n li $v0, 1\n syscall\n li $v0, 10\n syscall\n"
    assert run_mips(source).output == "a\nb6"


def test_simulador_tabla_de_etiquetas_y_salto_indirecto():
    """Lo que necesita el despacho dinamico: `.word etiqueta` y `jalr`."""
    source = """
.data
tabla: .word uno, dos
.text
main:
    la $t0, tabla
    lw $t1, 4($t0)
    jalr $t1
    li $v0, 10
    syscall
uno:
    li $a0, 1
    j imprime
dos:
    li $a0, 2
imprime:
    li $v0, 1
    syscall
    jr $ra
"""
    assert run_mips(source).output == "2"


@pytest.mark.parametrize(
    "body, message",
    [
        ("foo $t0, $t1", "no soportada"),
        ("lw $t0, 2($sp)", "no alineada"),
        ("lw $t0, 0($zero)", "memoria invalido"),
        ("j main", "no termina"),
    ],
)
def test_simulador_reporta_errores_de_maquina(body, message):
    with pytest.raises(SimulatorError, match=message):
        run_mips(".text\nmain:\n " + body + "\n", step_limit=1000)
