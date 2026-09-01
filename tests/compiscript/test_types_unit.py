"""Tests unitarios del sistema de tipos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from compiscript.typesystem.types import (  # noqa: E402
    BOOLEAN,
    ERROR,
    INTEGER,
    STRING,
    is_assignable,
)


def test_mismo_tipo_es_asignable():
    assert is_assignable(INTEGER, INTEGER) is True
    assert is_assignable(STRING, STRING) is True
    assert is_assignable(BOOLEAN, BOOLEAN) is True


def test_tipos_distintos_no_son_asignables():
    assert is_assignable(INTEGER, STRING) is False
    assert is_assignable(BOOLEAN, INTEGER) is False


def test_error_type_es_comodin_en_ambas_direcciones():
    # ErrorType nunca genera un segundo error en cascada sobre un valor
    # que ya fallo antes.
    assert is_assignable(ERROR, INTEGER) is True
    assert is_assignable(INTEGER, ERROR) is True
    assert is_assignable(ERROR, ERROR) is True
