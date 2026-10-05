"""CLI `src/compiscript/run_demo.py`: diagnosticos, --tac y --layout."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
for path in (SRC, SRC / "compiscript"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_demo import main  # noqa: E402

VALID = "function sumar(a: integer, b: integer): integer { return a + b; }\nlet r: integer = sumar(1, 2);\n"


def _write(tmp_path, source: str) -> str:
    file = tmp_path / "programa.cps"
    file.write_text(source, encoding="utf-8")
    return str(file)


def test_sin_opciones_solo_muestra_diagnosticos(tmp_path, capsys):
    assert main([_write(tmp_path, VALID)]) == 0
    out = capsys.readouterr().out
    assert "Sin diagnosticos semanticos." in out
    assert "Codigo intermedio" not in out


def test_tac_muestra_el_codigo_intermedio(tmp_path, capsys):
    assert main([_write(tmp_path, VALID), "--tac"]) == 0
    out = capsys.readouterr().out
    assert "Codigo intermedio:" in out
    assert "t0 = call sumar, 2" in out and "halt" in out
    assert "Registros de activacion" not in out


def test_layout_muestra_los_registros_de_activacion(tmp_path, capsys):
    assert main([_write(tmp_path, VALID), "--layout"]) == 0
    out = capsys.readouterr().out
    assert "registro de activacion sumar" in out
    assert "tamano del frame" in out
    assert "Codigo intermedio:" not in out


def test_las_dos_opciones_juntas(tmp_path, capsys):
    assert main([_write(tmp_path, VALID), "--tac", "--layout"]) == 0
    out = capsys.readouterr().out
    assert "Codigo intermedio:" in out and "Registros de activacion:" in out


def test_con_errores_semanticos_no_genera_codigo(tmp_path, capsys):
    assert main([_write(tmp_path, 'let x: integer = "texto";'), "--tac"]) == 1
    out = capsys.readouterr().out
    assert "SEM-TYPE-003" in out
    assert "No se genera codigo intermedio" in out
    assert "halt" not in out


def test_con_errores_de_sintaxis_termina_con_error(tmp_path, capsys):
    assert main([_write(tmp_path, "let x: integer = 1"), "--tac"]) == 1
    assert "Errores de sintaxis" in capsys.readouterr().out


def test_argumentos_invalidos_devuelven_uso(tmp_path, capsys):
    assert main([]) == 2
    assert main([_write(tmp_path, VALID), "--otra"]) == 2
    assert main([_write(tmp_path, VALID), _write(tmp_path, VALID)]) == 2
    assert "Uso:" in capsys.readouterr().out


def test_lee_archivos_con_acentos_en_utf8(tmp_path, capsys):
    source = '// comentario con acentos: á é í ó ú ñ\nprint("canción");\n'
    assert main([_write(tmp_path, source), "--tac"]) == 0
    assert 'print "canción"' in capsys.readouterr().out
