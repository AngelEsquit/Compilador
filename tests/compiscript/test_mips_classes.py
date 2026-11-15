"""Clases, objetos y herencia en el backend MIPS."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiscript.backend import compile_to_mips  # noqa: E402
from compiscript.backend.simulator import run_mips  # noqa: E402

THREE = ("$t0", "$t1", "$t2")
BOTH = pytest.mark.parametrize("registers", [None, THREE], ids=["diez_registros", "tres_registros"])


def execute(source: str, registers=None):
    options = {} if registers is None else {"registers": registers}
    result = compile_to_mips(source, **options)
    return run_mips(result.text, result.functions)


def run(source: str, registers=None) -> list[str]:
    return execute(source, registers).output.splitlines()


def text_of(source: str, **options) -> str:
    return compile_to_mips(source, **options).text


ANIMALES = """
class Animal {
  let nombre: string;
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return "..."; }
  function presentar(): string { return this.nombre + " dice " + this.hablar(); }
}
class Perro : Animal {
  function hablar(): string { return "guau"; }
}
class Gato : Animal {
  function hablar(): string { return "miau"; }
  function ronronear(): string { return "rrr"; }
}
"""


# ---------------------------------------------------------------- objetos y campos
@BOTH
def test_campos_y_constructor(registers):
    source = """
    class Punto {
      let x: integer;
      let y: integer;
      function constructor(x: integer, y: integer) { this.x = x; this.y = y; }
      function suma(): integer { return this.x + this.y; }
    }
    let p: Punto = new Punto(3, 4);
    print(p.x); print(p.y); print(p.suma());
    p.x = 10;
    print(p.suma());
    """
    assert run(source, registers) == ["3", "4", "7", "14"]


@BOTH
def test_objetos_independientes_y_campos_con_inicializador(registers):
    source = """
    class Contador {
      let n: integer = 5;
      function incrementar() { this.n = this.n + 1; }
    }
    let a: Contador = new Contador();
    let b: Contador = new Contador();
    a.incrementar(); a.incrementar();
    b.incrementar();
    print(a.n); print(b.n);
    """
    assert run(source, registers) == ["7", "6"]


@BOTH
def test_campos_boolean_float_y_referencia(registers):
    source = """
    class Caja {
      let activa: boolean = true;
      let peso: float = 1.5;
      let siguiente: Caja;
    }
    let a: Caja = new Caja();
    let b: Caja = new Caja();
    a.siguiente = b;
    b.activa = false;
    b.peso = 2;
    print(a.activa); print(a.siguiente.activa);
    print(a.peso + a.siguiente.peso);
    print(a.siguiente.siguiente == null);
    """
    assert run(source, registers) == ["true", "false", "3.5", "true"]


@BOTH
def test_objetos_en_arreglos_y_como_argumentos(registers):
    source = """
    class Caja { let v: integer; function constructor(v: integer) { this.v = v; } }
    function total(cajas: Caja[]): integer {
      let s: integer = 0;
      foreach (c in cajas) { s = s + c.v; }
      return s;
    }
    function duplicar(c: Caja): Caja { return new Caja(c.v * 2); }
    let cajas: Caja[] = [new Caja(1), new Caja(2), duplicar(new Caja(5))];
    print(total(cajas));
    """
    assert run(source, registers) == ["13"]


# ---------------------------------------------------------------- herencia y polimorfismo
@BOTH
def test_constructor_heredado_y_metodo_sobrescrito(registers):
    source = ANIMALES + """
    let p: Perro = new Perro("Rex");
    print(p.presentar());
    print(p.nombre);
    """
    assert run(source, registers) == ["Rex dice guau", "Rex"]


@BOTH
def test_llamada_desde_la_superclase_ejecuta_el_metodo_de_la_clase_real(registers):
    source = ANIMALES + """
    let a: Animal = new Perro("Rex");
    let b: Animal = new Gato("Mishi");
    let c: Animal = new Animal("Bicho");
    print(a.hablar()); print(b.hablar()); print(c.hablar());
    print(b.presentar());
    """
    assert run(source, registers) == ["guau", "miau", "...", "Mishi dice miau"]


@BOTH
def test_arreglo_de_la_superclase_con_instancias_de_subclases(registers):
    source = ANIMALES + """
    let zoo: Animal[] = [new Perro("A"), new Gato("B"), new Animal("C")];
    foreach (z in zoo) { print(z.presentar()); }
    """
    assert run(source, registers) == ["A dice guau", "B dice miau", "C dice ..."]


@BOTH
def test_metodo_propio_de_la_subclase_y_herencia_multinivel(registers):
    source = """
    class A { let a: integer = 1; function quien(): string { return "A"; } function suma(): integer { return this.a; } }
    class B : A {
      let b: integer = 2;
      function quien(): string { return "B"; }
      function suma(): integer { return this.a + this.b; }
    }
    class C : B { let c: integer = 3; function suma(): integer { return this.a + this.b + this.c; } }
    let x: A = new C();
    print(x.quien()); print(x.suma());
    let y: C = new C();
    y.a = 10;
    print(y.suma());
    """
    assert run(source, registers) == ["B", "6", "15"]


def test_los_campos_heredados_conservan_su_offset_en_las_subclases():
    source = """
    class A { let a: integer = 1; }
    class B : A { let b: integer = 2; }
    let x: B = new B();
    print(x.a); print(x.b);
    """
    text = text_of(source)
    assert run(source) == ["1", "2"]
    assert "lw" in text and "8($" in text and "12($" in text


def test_tabla_de_metodos_de_una_subclase():
    text = text_of(ANIMALES + 'let p: Gato = new Gato("x");')
    table = lambda name: text.split(f"_vt_{name}:")[1].splitlines()[1].split()  # noqa: E731
    assert table("Animal") == [".word", "f_Animal_hablar,", "f_Animal_presentar"]
    assert table("Perro") == [".word", "f_Perro_hablar,", "f_Animal_presentar"]
    assert table("Gato") == [".word", "f_Gato_hablar,", "f_Animal_presentar,", "f_Gato_ronronear"]


def test_el_objeto_guarda_su_tabla_en_la_cabecera_y_la_llamada_es_dinamica():
    text = text_of(ANIMALES + 'let a: Animal = new Perro("x"); print(a.hablar());')
    assert "la $a1, _vt_Perro" in text and "sw $a1, 0($v0)" in text
    assert "jalr $a1" in text


def test_el_constructor_de_la_superclase_recibe_this_primero():
    source = """
    class Base { let n: integer; function constructor(n: integer, m: integer) { this.n = n - m; } }
    class Hija : Base {}
    let h: Hija = new Hija(10, 3);
    print(h.n);
    """
    assert run(source) == ["7"]


@BOTH
def test_metodos_que_se_llaman_entre_si_y_recursion_en_metodo(registers):
    source = """
    class Mate {
      function fact(n: integer): integer { if (n <= 1) { return 1; } return n * this.fact(n - 1); }
      function doble(n: integer): integer { return this.fact(n) * 2; }
    }
    let m: Mate = new Mate();
    print(m.doble(5));
    """
    assert run(source, registers) == ["240"]


def test_el_arbol_de_activacion_incluye_los_metodos():
    machine = execute(ANIMALES + 'let a: Animal = new Perro("x"); print(a.presentar());')
    tree = machine.root.to_text()
    assert "Animal.constructor" in tree and "Animal.presentar" in tree and "Perro.hablar" in tree


# ---------------------------------------------------------------- errores de ejecucion
def test_acceso_a_campo_de_null_termina_con_error():
    source = """
    class C { let v: integer; }
    let c: C = null;
    print(c.v);
    """
    machine = execute(source)
    assert machine.output == "Error de ejecucion: acceso a null\n" and machine.exit_code == 1


def test_llamada_a_metodo_de_null_termina_con_error():
    source = """
    class C { function f(): integer { return 1; } }
    let c: C = null;
    print(c.f());
    """
    machine = execute(source)
    assert machine.output == "Error de ejecucion: acceso a null\n" and machine.exit_code == 1


def test_asignar_a_campo_de_null_termina_con_error():
    source = """
    class C { let v: integer; }
    let c: C = null;
    c.v = 1;
    """
    assert execute(source).exit_code == 1


def test_this_no_lleva_comprobacion_de_null():
    text = text_of("class C { let v: integer = 1; function f(): integer { return this.v; } } print(new C().f());")
    method = text.split("f_C_f:")[1].split("jr $ra")[0]
    assert "_null_error" not in method
