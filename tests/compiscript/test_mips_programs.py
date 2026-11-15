"""Programas completos en MIPS: se compilan, se ejecutan en el simulador y se compara lo
que imprimen con las lineas `// expect:` del propio archivo.

Son los mismos programas que validan el codigo intermedio (`intermediate/valid/*.cps`).
Los que usan una construccion que el backend aun no traduce se saltan; al implementarla
hay que quitarla de `PENDING` y las pruebas correspondientes empiezan a exigirse solas.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiscript.backend import UnsupportedFeature, compile_to_mips  # noqa: E402
from compiscript.backend.simulator import run_mips  # noqa: E402

# Construcciones sin traduccion a MIPS todavia.
PENDING = {"clases", "try/catch"}

VALID = sorted((HERE / "intermediate" / "valid").glob("*.cps"))
REGISTER_SETS = {"diez_registros": None, "tres_registros": ("$t0", "$t1", "$t2")}


def expected_output(source: str) -> list[str]:
    return [line.split("// expect:", 1)[1].strip() for line in source.splitlines() if line.startswith("// expect:")]


def compile_or_skip(source: str, registers=None):
    try:
        return compile_to_mips(source) if registers is None else compile_to_mips(source, registers=registers)
    except UnsupportedFeature as error:
        if error.feature in PENDING:
            pytest.skip(f"pendiente en el backend: {error.feature}")
        raise


@pytest.mark.parametrize("registers", REGISTER_SETS.values(), ids=REGISTER_SETS.keys())
@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_programa_produce_la_salida_esperada_en_mips(path, registers):
    source = path.read_text(encoding="utf-8")
    result = compile_or_skip(source, registers)
    machine = run_mips(result.text, result.functions)
    assert machine.exit_code == 0
    assert machine.output.splitlines() == expected_output(source)


def _unsupported() -> dict[str, str]:
    """Programa -> construccion que impide traducirlo."""
    found = {}
    for path in VALID:
        try:
            compile_to_mips(path.read_text(encoding="utf-8"))
        except UnsupportedFeature as error:
            found[path.stem] = error.feature
    return found


def test_hay_programas_que_si_se_ejecutan():
    """Evita que todo quede saltado sin que nadie lo note."""
    assert len(VALID) - len(_unsupported()) >= 35


def test_lo_pendiente_esta_declarado():
    """Toda construccion sin traducir figura en PENDING, y PENDING no tiene sobrantes."""
    assert set(_unsupported().values()) == PENDING
