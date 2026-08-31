"""Primera prueba end-to-end del pipeline completo: parser (ANTLR) ->
SemanticAnalyzer -> Diagnostics.

Este es el test que valida el "walking skeleton" descrito en la
seccion 0 de docs/Compiscript_Diseno_Semantico.md: confirma que las
dos reglas mas simples (variable no declarada, redeclaracion en el
mismo ambito) funcionan de punta a punta con codigo Compiscript real,
no solo unitariamente sobre Scope en aislado.
"""
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
    # Decision de diseno documentada en la seccion 5: una variable local
    # puede tener el mismo nombre que una de un ambito exterior.
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
    # animals.cps (tests/compiscript/samples/) ejercita clases, funciones,
    # foreach, try/catch y arreglos -- todo eso es trabajo de las
    # siguientes iteraciones (rules_functions.py, rules_classes.py, etc.,
    # ver seccion 6 del diseno), no del walking skeleton. Aqui solo
    # confirmamos que el parser lo acepta sintacticamente; es normal y
    # esperado que el analizador semantico actual reporte SEM-SCOPE-001
    # sobre parametros de funcion, la variable de foreach, etc. -- ese
    # mismo archivo se reutiliza como caso de integracion mas adelante,
    # cuando esas reglas existan.
    samples_dir = Path(__file__).resolve().parent / "samples"
    source = (samples_dir / "animals.cps").read_text()
    _, syntax_errors = analyze_source(source)

    assert syntax_errors == []
