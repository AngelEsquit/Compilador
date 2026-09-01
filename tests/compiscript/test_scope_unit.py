"""Tests unitarios de Scope, sin pasar por el parser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from compiscript.symbols.scope import Scope, ScopeKind  # noqa: E402
from compiscript.symbols.symbol import VariableSymbol  # noqa: E402
from compiscript.typesystem.types import INTEGER  # noqa: E402


def _var(name: str) -> VariableSymbol:
    return VariableSymbol(name=name, decl_type=INTEGER)


def test_define_y_resolve_en_el_mismo_scope():
    scope = Scope(ScopeKind.GLOBAL)
    assert scope.define(_var("x")) is True
    assert scope.resolve("x") is not None
    assert scope.resolve("x").name == "x"


def test_define_duplicado_en_mismo_scope_devuelve_false():
    scope = Scope(ScopeKind.GLOBAL)
    assert scope.define(_var("x")) is True
    assert scope.define(_var("x")) is False  # ya existe -> el llamador reporta el error


def test_resolve_sube_a_los_padres():
    global_scope = Scope(ScopeKind.GLOBAL)
    global_scope.define(_var("g"))
    block_scope = global_scope.child(ScopeKind.BLOCK)

    assert block_scope.resolve("g") is not None
    assert block_scope.resolve_local("g") is None  # no esta EN este scope, solo en el padre


def test_resolve_nombre_inexistente_devuelve_none():
    scope = Scope(ScopeKind.GLOBAL)
    assert scope.resolve("no_existe") is None


def test_shadowing_entre_scopes_distintos_esta_permitido():
    global_scope = Scope(ScopeKind.GLOBAL)
    global_scope.define(_var("x"))
    block_scope = global_scope.child(ScopeKind.BLOCK)

    # Un scope hijo SI puede redefinir un nombre que ya existe en el padre
    # (decision de diseno documentada en la seccion 5).
    assert block_scope.define(_var("x")) is True
    assert block_scope.resolve_local("x") is not None


def test_child_no_contamina_al_padre():
    global_scope = Scope(ScopeKind.GLOBAL)
    block_scope = global_scope.child(ScopeKind.BLOCK)
    block_scope.define(_var("local"))

    assert block_scope.resolve("local") is not None
    assert global_scope.resolve("local") is None
