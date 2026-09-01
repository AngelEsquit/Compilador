"""Tests unitarios de Scope y Tabla de Simbolos, sin pasar por el parser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from compiscript.symbols.scope import Scope, ScopeKind  # noqa: E402
from compiscript.symbols.symbol import (  # noqa: E402
    ClassSymbol,
    ConstSymbol,
    FunctionSymbol,
    ParameterSymbol,
    VariableSymbol,
)
from compiscript.typesystem.types import BOOLEAN, INTEGER, STRING  # noqa: E402


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
    assert scope.define(_var("x")) is False


def test_resolve_sube_a_los_padres():
    global_scope = Scope(ScopeKind.GLOBAL)
    global_scope.define(_var("g"))
    block_scope = global_scope.child(ScopeKind.BLOCK)

    assert block_scope.resolve("g") is not None
    assert block_scope.resolve_local("g") is None


def test_resolve_nombre_inexistente_devuelve_none():
    scope = Scope(ScopeKind.GLOBAL)
    assert scope.resolve("no_existe") is None


def test_shadowing_entre_scopes_distintos_esta_permitido():
    global_scope = Scope(ScopeKind.GLOBAL)
    global_scope.define(_var("x"))
    block_scope = global_scope.child(ScopeKind.BLOCK)

    assert block_scope.define(_var("x")) is True
    assert block_scope.resolve_local("x") is not None


def test_child_no_contamina_al_padre():
    global_scope = Scope(ScopeKind.GLOBAL)
    block_scope = global_scope.child(ScopeKind.BLOCK)
    block_scope.define(_var("local"))

    assert block_scope.resolve("local") is not None
    assert global_scope.resolve("local") is None


def test_update_modifica_atributos_del_simbolo():
    global_scope = Scope(ScopeKind.GLOBAL)
    global_scope.define(VariableSymbol(name="total", decl_type=INTEGER, initialized=False))

    assert global_scope.resolve("total").initialized is False
    assert global_scope.update("total", initialized=True) is True
    assert global_scope.resolve("total").initialized is True

    # Actualizar simbolo inexistente
    assert global_scope.update("no_existe", initialized=True) is False


def test_manejo_de_alcances_y_contexto_jerarquico():
    global_scope = Scope(ScopeKind.GLOBAL, name="global")
    func_scope = global_scope.child(ScopeKind.FUNCTION, name="calcular")
    loop_scope = func_scope.child(ScopeKind.LOOP, name="while")
    block_scope = loop_scope.child(ScopeKind.BLOCK, name="bloque_interno")

    assert block_scope.is_inside_loop() is True
    assert block_scope.get_enclosing_function() is func_scope
    assert global_scope.is_inside_loop() is False
    assert global_scope.get_enclosing_function() is None


def test_scope_to_dict_serializacion():
    global_scope = Scope(ScopeKind.GLOBAL, name="global")
    global_scope.define(VariableSymbol(name="edad", decl_type=INTEGER, line=1, column=4))
    global_scope.define(ConstSymbol(name="PI", decl_type=INTEGER, line=2, column=6))

    child = global_scope.child(ScopeKind.BLOCK, name="bloque1")
    child.define(VariableSymbol(name="temp", decl_type=STRING, line=4, column=8))

    serialized = global_scope.to_dict()
    assert serialized["kind"] == "global"
    assert "edad" in serialized["symbols"]
    assert "PI" in serialized["symbols"]
    assert len(serialized["children"]) == 1
    assert serialized["children"][0]["name"] == "bloque1"
    assert "temp" in serialized["children"][0]["symbols"]
