"""Tests unitarios del sistema de tipos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from compiscript.typesystem.types import (  # noqa: E402
    BOOLEAN,
    ERROR,
    INTEGER,
    NULL,
    STRING,
    VOID,
    ArrayType,
    ClassType,
    FunctionType,
    is_assignable,
)


def test_mismo_tipo_es_asignable():
    assert is_assignable(INTEGER, INTEGER) is True
    assert is_assignable(STRING, STRING) is True
    assert is_assignable(BOOLEAN, BOOLEAN) is True


def test_tipos_distintos_no_son_asignables():
    assert is_assignable(INTEGER, STRING) is False
    assert is_assignable(BOOLEAN, INTEGER) is False
    assert is_assignable(STRING, INTEGER) is False


def test_error_type_es_comodin_en_ambas_direcciones():
    assert is_assignable(ERROR, INTEGER) is True
    assert is_assignable(INTEGER, ERROR) is True
    assert is_assignable(ERROR, ERROR) is True


def test_null_es_asignable_a_clases_pero_no_a_primitivos():
    animal_type = ClassType("Animal")
    assert is_assignable(NULL, animal_type) is True
    assert is_assignable(NULL, INTEGER) is False
    assert is_assignable(NULL, STRING) is False
    assert is_assignable(NULL, BOOLEAN) is False


def test_arreglos_mismo_tipo_y_dimension():
    arr_int_1 = ArrayType(INTEGER, 1)
    arr_int_1_bis = ArrayType(INTEGER, 1)
    arr_int_2 = ArrayType(INTEGER, 2)
    arr_str_1 = ArrayType(STRING, 1)

    assert is_assignable(arr_int_1, arr_int_1_bis) is True
    assert is_assignable(arr_int_1, arr_int_2) is False
    assert is_assignable(arr_int_1, arr_str_1) is False


def test_function_types_assignability():
    f1 = FunctionType([INTEGER, STRING], BOOLEAN)
    f2 = FunctionType([INTEGER, STRING], BOOLEAN)
    f_diff_ret = FunctionType([INTEGER, STRING], INTEGER)
    f_diff_param = FunctionType([STRING, STRING], BOOLEAN)

    assert is_assignable(f1, f2) is True
    assert is_assignable(f1, f_diff_ret) is False
    assert is_assignable(f1, f_diff_param) is False


def test_to_dict_serializacion():
    assert INTEGER.to_dict() == {"kind": "integer"}
    arr_t = ArrayType(INTEGER, 2)
    assert arr_t.to_dict() == {
        "kind": "array",
        "elementType": {"kind": "integer"},
        "dimensions": 2,
    }
    cls_t = ClassType("Persona")
    assert cls_t.to_dict() == {"kind": "class", "className": "Persona"}
