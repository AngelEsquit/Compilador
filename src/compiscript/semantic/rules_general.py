"""Reglas semanticas generales (Seccion 2.7).

Valida:
- Codigo muerto: sentencias inalcanzables inmediatamente despues de un
  `return`, `break` o `continue` incondicional dentro del mismo bloque
  (SEM-GEN-001, warning).
- Expresiones sin sentido semantico: operar aritmeticamente con funciones
  o clases (SEM-GEN-002).
"""
from __future__ import annotations

from compiscript.diagnostics import DiagnosticList
from compiscript.typesystem.types import ClassType, FunctionType, Type


def _is_terminating(statement) -> bool:
    """True si `statement` (un nodo StatementContext) es un return/break/continue.

    Las alternativas de la regla `statement` no llevan etiqueta en la
    gramatica, asi que cada `statement()` de la lista es un StatementContext
    envoltorio; hay que consultar sus accessors internos en vez de comparar
    con `isinstance` directamente.
    """
    for accessor_name in ("returnStatement", "breakStatement", "continueStatement"):
        accessor = getattr(statement, accessor_name, None)
        if accessor is not None and accessor() is not None:
            return True
    return False


def check_unreachable_code(statements, diag: DiagnosticList) -> None:
    """Marca la primera sentencia inalcanzable de un bloque (SEM-GEN-001).

    Una sentencia es inalcanzable si aparece despues de un `return`, `break`
    o `continue` incondicional dentro de la misma lista de sentencias (mismo
    bloque). Solo se reporta el primer tramo muerto para no inundar de
    warnings el resto del bloque.
    """
    terminated = False
    for statement in statements:
        if terminated:
            token = statement.start
            diag.warning(
                "SEM-GEN-001",
                "Codigo inalcanzable: esta sentencia nunca se ejecuta porque el "
                "bloque ya termino con un return, break o continue.",
                token.line,
                token.column,
            )
            break

        if _is_terminating(statement):
            terminated = True


def check_no_semantic_operation(
    operand_types: list[Type],
    op: str,
    line: int,
    col: int,
    diag: DiagnosticList,
) -> bool:
    """Detecta operandos sin sentido aritmetico: funciones o clases (SEM-GEN-002).

    Devuelve True si reporto el error, para que el llamador evite tambien
    reportar el error de tipos generico sobre el mismo operando.
    """
    offending = next(
        (t for t in operand_types if isinstance(t, (FunctionType, ClassType))),
        None,
    )
    if offending is None:
        return False

    diag.error(
        "SEM-GEN-002",
        f"La operacion '{op}' no tiene sentido semantico sobre un valor de "
        f"tipo '{offending.name}'.",
        line,
        col,
    )
    return True
