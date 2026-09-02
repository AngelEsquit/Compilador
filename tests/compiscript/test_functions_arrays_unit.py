"""Tests unitarios de las reglas de funciones y arreglos, sin pasar por el parser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from compiscript.diagnostics import DiagnosticList  # noqa: E402
from compiscript.semantic.rules_arrays import (  # noqa: E402
    check_array_literal,
    check_foreach_collection,
    check_index_access,
    element_type_of,
)
from compiscript.semantic.rules_functions import check_call, check_return_type  # noqa: E402
from compiscript.symbols.symbol import FunctionSymbol  # noqa: E402
from compiscript.typesystem.types import (  # noqa: E402
    BOOLEAN,
    ERROR,
    INTEGER,
    STRING,
    VOID,
    ArrayType,
    FunctionType,
)


def _diag() -> DiagnosticList:
    return DiagnosticList()


# --- Funciones ---------------------------------------------------------

def test_llamada_correcta_devuelve_tipo_de_retorno():
    diag = _diag()
    signature = FunctionType([INTEGER, INTEGER], INTEGER)
    result = check_call(signature, "suma", [INTEGER, INTEGER], 1, 0, diag)
    assert result == INTEGER
    assert len(diag) == 0


def test_llamada_con_aridad_incorrecta():
    diag = _diag()
    check_call(FunctionType([INTEGER], INTEGER), "f", [INTEGER, INTEGER], 1, 0, diag)
    assert "SEM-FUNC-003" in diag.codes()


def test_llamada_con_argumento_incompatible():
    diag = _diag()
    check_call(FunctionType([INTEGER], INTEGER), "f", [STRING], 1, 0, diag)
    assert "SEM-FUNC-004" in diag.codes()


def test_invocar_algo_que_no_es_funcion():
    diag = _diag()
    assert check_call(INTEGER, "x", [], 1, 0, diag) == ERROR
    assert "SEM-FUNC-006" in diag.codes()


def test_errortype_no_encadena_diagnosticos():
    diag = _diag()
    assert check_call(ERROR, "desconocida", [INTEGER], 1, 0, diag) == ERROR
    assert len(diag) == 0


def test_retorno_incompatible_con_la_firma():
    diag = _diag()
    func = FunctionSymbol(name="f", decl_type=ERROR, parameters=[], return_type=INTEGER)
    check_return_type(func, STRING, 1, 0, diag)
    assert "SEM-FUNC-005" in diag.codes()


def test_retorno_vacio_en_funcion_con_tipo_declarado():
    diag = _diag()
    func = FunctionSymbol(name="f", decl_type=ERROR, parameters=[], return_type=INTEGER)
    check_return_type(func, None, 1, 0, diag)
    assert "SEM-FUNC-005" in diag.codes()


def test_retorno_vacio_en_funcion_void_es_valido():
    diag = _diag()
    func = FunctionSymbol(name="f", decl_type=ERROR, parameters=[], return_type=VOID)
    check_return_type(func, None, 1, 0, diag)
    assert len(diag) == 0


def test_return_fuera_de_funcion_no_revalida_tipo():
    diag = _diag()
    check_return_type(None, INTEGER, 1, 0, diag)
    assert len(diag) == 0


# --- Arreglos ----------------------------------------------------------

def test_literal_homogeneo_produce_array_type():
    diag = _diag()
    assert check_array_literal([INTEGER, INTEGER], 1, 0, diag) == ArrayType(INTEGER, 1)
    assert len(diag) == 0


def test_literal_heterogeneo_reporta_error():
    diag = _diag()
    check_array_literal([INTEGER, STRING], 1, 0, diag)
    assert "SEM-ARR-002" in diag.codes()


def test_literal_anidado_suma_una_dimension():
    diag = _diag()
    nested = check_array_literal([ArrayType(INTEGER, 1), ArrayType(INTEGER, 1)], 1, 0, diag)
    assert nested == ArrayType(INTEGER, 2)


def test_literal_vacio_no_reporta_error():
    diag = _diag()
    check_array_literal([], 1, 0, diag)
    assert len(diag) == 0


def test_indice_no_entero():
    diag = _diag()
    check_index_access(ArrayType(INTEGER, 1), STRING, "notas", 1, 0, diag)
    assert "SEM-ARR-001" in diag.codes()


def test_indexar_no_arreglo():
    diag = _diag()
    check_index_access(INTEGER, INTEGER, "x", 1, 0, diag)
    assert "SEM-ARR-004" in diag.codes()


def test_indexar_matriz_reduce_una_dimension():
    diag = _diag()
    result = check_index_access(ArrayType(INTEGER, 2), INTEGER, "m", 1, 0, diag)
    assert result == ArrayType(INTEGER, 1)
    assert len(diag) == 0


def test_foreach_sobre_no_arreglo():
    diag = _diag()
    check_foreach_collection(BOOLEAN, 1, 0, diag)
    assert "SEM-ARR-003" in diag.codes()


def test_foreach_sobre_arreglo_devuelve_tipo_de_elemento():
    diag = _diag()
    assert check_foreach_collection(ArrayType(STRING, 1), 1, 0, diag) == STRING
    assert len(diag) == 0


def test_element_type_of_reduce_dimensiones():
    assert element_type_of(ArrayType(INTEGER, 1)) == INTEGER
    assert element_type_of(ArrayType(INTEGER, 3)) == ArrayType(INTEGER, 2)
