"""Bateria de pruebas automatizada para las reglas semanticas de Compiscript."""
import sys
from pathlib import Path
import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

from compiscript.semantic.analyzer import analyze_source  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent


def _read_cps(relative_path: str) -> str:
    path = TESTS_DIR / relative_path
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Pruebas de Sistema de Tipos (2.1)
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_file",
    [
        "types/valid/operaciones_aritmeticas.cps",
        "types/valid/operaciones_logicas.cps",
        "types/valid/comparaciones_y_ternario.cps",
        "types/valid/asignacion_valida.cps",
    ],
)
def test_tipos_casos_validos(case_file: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("types/invalid/aritmetica_incompatible.cps", "SEM-TYPE-001"),
        ("types/invalid/logica_incompatible.cps", "SEM-TYPE-002"),
        ("types/invalid/comparacion_incompatible.cps", "SEM-TYPE-004"),
        ("types/invalid/asignacion_incompatible.cps", "SEM-TYPE-003"),
        ("types/invalid/reasignacion_constante.cps", "SEM-TYPE-006"),
    ],
)
def test_tipos_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


# ----------------------------------------------------------------------
# Pruebas de Ambitos (2.2)
# ----------------------------------------------------------------------

def test_ambito_caso_valido():
    source = _read_cps("scope/valid/declaracion_simple.cps")
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("scope/invalid/variable_no_declarada.cps", "SEM-SCOPE-001"),
        ("scope/invalid/redeclaracion.cps", "SEM-SCOPE-002"),
    ],
)
def test_ambito_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


# ----------------------------------------------------------------------
# Pruebas de Control de Flujo (2.4)
# ----------------------------------------------------------------------

def test_control_flujo_caso_valido():
    source = _read_cps("control_flow/valid/estructuras_control.cps")
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("control_flow/invalid/condicion_no_booleana.cps", "SEM-FLOW-001"),
        ("control_flow/invalid/break_fuera_bucle.cps", "SEM-FLOW-002"),
        ("control_flow/invalid/continue_fuera_bucle.cps", "SEM-FLOW-002"),
        ("control_flow/invalid/return_fuera_funcion.cps", "SEM-FLOW-003"),
    ],
)
def test_control_flujo_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


# ----------------------------------------------------------------------
# Pruebas de Funciones y Procedimientos (2.3)
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_file",
    [
        "functions/valid/llamadas_y_retornos.cps",
        "functions/valid/recursion.cps",
        "functions/valid/closures.cps",
    ],
)
def test_funciones_casos_validos(case_file: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("functions/invalid/funcion_duplicada.cps", "SEM-FUNC-001"),
        ("functions/invalid/parametro_duplicado.cps", "SEM-FUNC-002"),
        ("functions/invalid/aridad_incorrecta.cps", "SEM-FUNC-003"),
        ("functions/invalid/argumento_incompatible.cps", "SEM-FUNC-004"),
        ("functions/invalid/retorno_incompatible.cps", "SEM-FUNC-005"),
        ("functions/invalid/llamada_a_no_funcion.cps", "SEM-FUNC-006"),
    ],
)
def test_funciones_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


def test_recursion_mutua_resuelve_llamada_adelantada():
    # Sin la pasada de pre-declaracion, 'esImpar' seria una variable no declarada.
    source = _read_cps("functions/valid/recursion.cps")
    analyzer, _ = analyze_source(source)
    assert "SEM-SCOPE-001" not in analyzer.diagnostics.codes()


def test_llamada_devuelve_el_tipo_de_retorno():
    source = """
    function suma(a: integer, b: integer): integer { return a + b; }
    let total: string = suma(1, 2);
    """
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    # El error debe ser de asignacion integer contra string, no de FunctionType.
    assert "SEM-TYPE-003" in analyzer.diagnostics.codes()
    assert "=>" not in str(analyzer.diagnostics.items[0])


# ----------------------------------------------------------------------
# Pruebas de Arreglos y Listas (2.6)
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_file",
    [
        "arrays/valid/literales_y_acceso.cps",
        "arrays/valid/matrices.cps",
        "arrays/valid/foreach_arreglos.cps",
    ],
)
def test_arreglos_casos_validos(case_file: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("arrays/invalid/indice_no_entero.cps", "SEM-ARR-001"),
        ("arrays/invalid/elementos_heterogeneos.cps", "SEM-ARR-002"),
        ("arrays/invalid/foreach_no_arreglo.cps", "SEM-ARR-003"),
        ("arrays/invalid/indexar_no_arreglo.cps", "SEM-ARR-004"),
    ],
)
def test_arreglos_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


def test_tipo_declarado_de_arreglo_no_se_sobrescribe():
    # El tipo anotado manda: un inicializador incompatible se reporta y no
    # redefine el simbolo en la tabla.
    source = 'let notas: integer[] = ["a", "b"];'
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert "SEM-TYPE-003" in analyzer.diagnostics.codes()
    assert analyzer.global_scope.resolve("notas").decl_type.name == "integer[]"


# ----------------------------------------------------------------------
# Pruebas de Clases y Objetos (2.5)
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_file",
    [
        "classes/valid/herencia_y_this.cps",
        "classes/valid/forward_reference.cps",
    ],
)
def test_clases_casos_validos(case_file: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("classes/invalid/propiedad_inexistente.cps", "SEM-CLASS-001"),
        ("classes/invalid/this_fuera_de_clase.cps", "SEM-CLASS-002"),
        ("classes/invalid/superclase_inexistente.cps", "SEM-CLASS-003"),
        ("classes/invalid/ciclo_herencia.cps", "SEM-CLASS-003"),
        ("classes/invalid/constructor_aridad_incorrecta.cps", "SEM-CLASS-004"),
    ],
)
def test_clases_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


def test_clases_herencia_multinivel_resuelve_miembros():
    source = """
class A {
  let x: integer;
  function constructor(x: integer) { this.x = x; }
  function getX(): integer { return this.x; }
}
class B : A {}
class C : B {}
let c: C = new C(5);
print(c.getX());
print(c.x);
"""
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]


def test_clases_asignacion_a_propiedad_incompatible():
    source = """
class A { let x: integer; function constructor() { this.x = 1; } }
let a: A = new A();
a.x = "hola";
"""
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert "SEM-TYPE-003" in analyzer.diagnostics.codes()


# ----------------------------------------------------------------------
# Pruebas de Reglas Generales y Codigo Muerto (2.7)
# ----------------------------------------------------------------------

def test_general_control_flujo_normal_sin_errores():
    source = _read_cps("general/valid/control_flujo_normal.cps")
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]
    assert "SEM-GEN-001" not in analyzer.diagnostics.codes()


@pytest.mark.parametrize(
    "case_file,expected_code",
    [
        ("general/invalid/codigo_muerto_tras_return.cps", "SEM-GEN-001"),
        ("general/invalid/codigo_muerto_tras_break.cps", "SEM-GEN-001"),
        ("general/invalid/expresion_sin_sentido_funcion.cps", "SEM-GEN-002"),
        ("general/invalid/expresion_sin_sentido_clase.cps", "SEM-GEN-002"),
    ],
)
def test_general_casos_invalidos(case_file: str, expected_code: str):
    source = _read_cps(case_file)
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert expected_code in analyzer.diagnostics.codes()


def test_general_codigo_muerto_solo_reporta_una_vez_por_tramo():
    source = """
function f(): integer {
  return 1;
  print("a");
  print("b");
}
"""
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert analyzer.diagnostics.codes().count("SEM-GEN-001") == 1


def test_general_return_en_una_rama_de_if_no_marca_codigo_muerto():
    # El return esta dentro del bloque del if, no en el mismo bloque que el
    # return final: no debe reportarse como inalcanzable.
    source = """
function clasificar(n: integer): string {
  if (n > 0) {
    return "positivo";
  }
  return "no positivo";
}
"""
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert "SEM-GEN-001" not in analyzer.diagnostics.codes()


# ----------------------------------------------------------------------
# Integracion: el sample grande no debe reportar errores semanticos
# ----------------------------------------------------------------------

def test_sample_animals_sin_errores_semanticos():
    source = _read_cps("samples/animals.cps")
    analyzer, syntax_errors = analyze_source(source)
    assert syntax_errors == []
    assert not analyzer.diagnostics.has_errors(), [str(d) for d in analyzer.diagnostics]
