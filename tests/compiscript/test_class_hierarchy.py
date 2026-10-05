"""Subtipado de clases: una subclase es asignable a su superclase (polimorfismo)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiscript.semantic.analyzer import analyze_source  # noqa: E402
from compiscript.typesystem.types import (  # noqa: E402
    INTEGER,
    NULL,
    ArrayType,
    ClassType,
    is_assignable,
    common_superclass,
    is_subclass,
    register_superclass,
    reset_class_hierarchy,
)


@pytest.fixture(autouse=True)
def _jerarquia_limpia():
    reset_class_hierarchy()
    yield
    reset_class_hierarchy()


def _analyze(source: str):
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    return analyzer.diagnostics


# ------------------------------------------------------------------ is_subclass
def test_una_clase_es_subclase_de_si_misma():
    assert is_subclass("A", "A") is True


def test_subclase_directa_y_multinivel():
    register_superclass("B", "A")
    register_superclass("C", "B")
    assert is_subclass("B", "A") and is_subclass("C", "B") and is_subclass("C", "A")


def test_la_relacion_no_es_simetrica():
    register_superclass("B", "A")
    assert is_subclass("A", "B") is False


def test_clases_sin_relacion_y_clases_desconocidas():
    register_superclass("B", "A")
    assert is_subclass("B", "Otra") is False
    assert is_subclass("X", "Y") is False


def test_un_ciclo_en_la_jerarquia_no_cuelga_la_consulta():
    register_superclass("A", "B")
    register_superclass("B", "A")
    assert is_subclass("A", "Z") is False


def test_reset_borra_la_jerarquia():
    register_superclass("B", "A")
    reset_class_hierarchy()
    assert is_subclass("B", "A") is False


def test_ancestro_comun_de_clases_hermanas_y_de_distinto_nivel():
    register_superclass("Perro", "Animal")
    register_superclass("Gato", "Animal")
    register_superclass("Cachorro", "Perro")
    assert common_superclass("Perro", "Gato") == "Animal"
    assert common_superclass("Cachorro", "Gato") == "Animal"
    assert common_superclass("Cachorro", "Perro") == "Perro"  # una es ancestro de la otra
    assert common_superclass("Animal", "Animal") == "Animal"


def test_sin_ancestro_comun_devuelve_none_y_no_cuelga_con_ciclos():
    register_superclass("Perro", "Animal")
    assert common_superclass("Perro", "Otro") is None
    register_superclass("A", "B")
    register_superclass("B", "A")
    assert common_superclass("A", "Z") is None


# ------------------------------------------------------------------ is_assignable
def test_subclase_es_asignable_a_la_superclase_pero_no_al_reves():
    register_superclass("Perro", "Animal")
    assert is_assignable(ClassType("Perro"), ClassType("Animal")) is True
    assert is_assignable(ClassType("Animal"), ClassType("Perro")) is False


def test_clases_hermanas_y_no_relacionadas_no_son_asignables():
    register_superclass("Perro", "Animal")
    register_superclass("Gato", "Animal")
    assert is_assignable(ClassType("Perro"), ClassType("Gato")) is False
    assert is_assignable(ClassType("Perro"), ClassType("Otro")) is False


def test_arreglos_de_subclases_son_asignables_a_arreglos_de_la_superclase():
    register_superclass("Perro", "Animal")
    assert is_assignable(ArrayType(ClassType("Perro"), 1), ArrayType(ClassType("Animal"), 1)) is True
    assert is_assignable(ArrayType(ClassType("Animal"), 1), ArrayType(ClassType("Perro"), 1)) is False


def test_null_y_primitivos_siguen_igual():
    register_superclass("Perro", "Animal")
    assert is_assignable(NULL, ClassType("Animal")) is True
    assert is_assignable(ClassType("Perro"), INTEGER) is False
    assert is_assignable(INTEGER, ClassType("Animal")) is False


# ------------------------------------------------------------------ analisis completo
BASE = """
class Animal {}
class Perro : Animal {}
class Cachorro : Perro {}
class Gato : Animal {}
class Otro {}
"""


@pytest.mark.parametrize(
    "body",
    [
        "let a: Animal = new Perro();",
        "let a: Animal = new Animal(); a = new Perro();",
        "let a: Animal = new Cachorro();",  # dos niveles
        "let a: Animal = null;",
        "function f(a: Animal): integer { return 1; } print(f(new Cachorro()));",
        "function f(): Animal { return new Perro(); }",
        "let zoo: Animal[] = [new Perro(), new Gato()];",
        "let zoo: Animal[] = [new Perro(), new Animal(), new Cachorro()];",
        "let c: boolean = new Animal() == new Perro();",
        "let c: boolean = new Perro() != new Animal();",
        "let a: Animal = true ? new Perro() : new Animal();",
        "let a: Animal = true ? new Perro() : new Gato();",  # ramas hermanas: el tipo es Animal
        "let zoo: Animal[][] = [[new Perro()], [new Gato()]];",
        "class Dueno { let mascota: Animal; } let d: Dueno = new Dueno(); d.mascota = new Perro();",
        "class Dueno { function constructor(m: Animal) {} } let d: Dueno = new Dueno(new Cachorro());",
    ],
)
def test_usos_validos_del_polimorfismo(body):
    diagnostics = _analyze(BASE + body)
    assert not diagnostics.has_errors(), [str(d) for d in diagnostics]


@pytest.mark.parametrize(
    "body, code",
    [
        ("let p: Perro = new Animal();", "SEM-TYPE-003"),  # superclase a subclase
        ("let c: Cachorro = new Perro();", "SEM-TYPE-003"),
        ("let p: Perro = new Gato();", "SEM-TYPE-003"),  # hermanas
        ("let a: Animal = new Otro();", "SEM-TYPE-003"),  # sin relacion
        ("let a: Animal = new Perro(); let p: Perro = a;", "SEM-TYPE-003"),  # sin downcast implicito
        ("function f(p: Perro): integer { return 1; } print(f(new Animal()));", "SEM-FUNC-004"),
        ("function f(): Perro { return new Animal(); }", "SEM-FUNC-005"),
        ("let ps: Perro[] = [new Perro(), new Animal()];", "SEM-TYPE-003"),
        ("let xs = [new Perro(), new Otro()];", "SEM-ARR-002"),
        ("let c: boolean = new Gato() == new Perro();", "SEM-TYPE-004"),
        ("let c: boolean = new Animal() == new Otro();", "SEM-TYPE-004"),
        ("let p: Perro = true ? new Perro() : new Animal();", "SEM-TYPE-003"),
        ("let p: Perro = true ? new Perro() : new Gato();", "SEM-TYPE-003"),  # el resultado es Animal
        ("let x = true ? new Perro() : new Otro();", "SEM-TYPE-003"),
        ("class Dueno { function constructor(m: Perro) {} } let d: Dueno = new Dueno(new Animal());", "SEM-CLASS-004"),
        ("class Dueno { let mascota: Perro; } let d: Dueno = new Dueno(); d.mascota = new Gato();", "SEM-TYPE-003"),
    ],
)
def test_usos_invalidos_siguen_reportando_error(body, code):
    diagnostics = _analyze(BASE + body)
    assert code in diagnostics.codes(), [str(d) for d in diagnostics]


def test_un_ciclo_de_herencia_no_cuelga_el_analisis_y_se_reporta():
    diagnostics = _analyze("class A : B {} class B : A {} let a: A = new B();")
    assert "SEM-CLASS-003" in diagnostics.codes()


def test_la_jerarquia_de_un_analisis_no_se_filtra_al_siguiente():
    assert not _analyze("class A {} class B : A {} let a: A = new B();").has_errors()
    # Mismos nombres, sin herencia: ahora si debe fallar.
    assert "SEM-TYPE-003" in _analyze("class A {} class B {} let a: A = new B();").codes()
    # Y nada queda registrado una vez terminado el analisis.
    assert is_subclass("B", "A") is False
