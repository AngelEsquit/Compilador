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
