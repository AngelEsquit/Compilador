"""Test end-to-end: parser ANTLR -> SemanticAnalyzer -> Diagnostics."""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

from compiscript.semantic.analyzer import analyze_source  # noqa: E402

CASES_DIR = Path(__file__).resolve().parent / "scope"


def _read(relative_path: str) -> str:
    return (CASES_DIR / relative_path).read_text()


def test_caso_valido_no_genera_errores():
    source = _read("valid/declaracion_simple.cps")
    analyzer, syntax_errors = analyze_source(source)

    assert syntax_errors == []
    assert analyzer.diagnostics.has_errors() is False, [str(d) for d in analyzer.diagnostics]


def test_variable_no_declarada_se_detecta():
    source = _read("invalid/variable_no_declarada.cps")
    analyzer, syntax_errors = analyze_source(source)

    assert syntax_errors == []
    assert "SEM-SCOPE-001" in analyzer.diagnostics.codes()


def test_redeclaracion_en_mismo_ambito_se_detecta():
    source = _read("invalid/redeclaracion.cps")
    analyzer, syntax_errors = analyze_source(source)

    assert syntax_errors == []
    assert "SEM-SCOPE-002" in analyzer.diagnostics.codes()


def test_shadowing_entre_ambitos_distintos_esta_permitido():
    # Decision de diseno: una variable local puede tapar a una exterior.
    source = """
    let x: integer = 1;
    {
      let x: integer = 2;
      print(x);
    }
    print(x);
    """
    analyzer, syntax_errors = analyze_source(source)

    assert syntax_errors == []
    assert analyzer.diagnostics.has_errors() is False, [str(d) for d in analyzer.diagnostics]


def test_sample_grande_parsea_sintacticamente():
    # animals.cps ejercita clases, funciones, foreach, try/catch y arreglos.
    # Aqui solo se comprueba que el parser lo acepte; pasa a ser caso de
    # integracion semantica cuando existan rules_functions.py y rules_classes.py.
    samples_dir = Path(__file__).resolve().parent / "samples"
    source = (samples_dir / "animals.cps").read_text()
    _, syntax_errors = analyze_source(source)

    assert syntax_errors == []
