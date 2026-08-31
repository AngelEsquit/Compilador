"""Analizador semantico -- version minima del walking skeleton (ver
docs/Compiscript_Diseno_Semantico.md, seccion 0).

Implementa solo dos reglas, las mas simples y las que mas dependen de
Scope (seccion 2.2 del enunciado):

  * SEM-SCOPE-001: uso de una variable no declarada.
  * SEM-SCOPE-002: redeclaracion de un identificador en el mismo ambito.

El resto de las categorias (tipos, funciones, control de flujo, clases,
arreglos, generales) se agregan despues, cada una en su propio modulo
rules_*.py, siguiendo el mismo patron que se usa aqui: recibir
(ctx, contexto compartido) y agregar diagnosticos. Ver seccion 6 del
documento de diseno.
"""
from __future__ import annotations

from compiscript.diagnostics import DiagnosticList
from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser
from compiscript.grammar.generated.CompiscriptVisitor import CompiscriptVisitor
from compiscript.symbols.scope import Scope, ScopeKind
from compiscript.symbols.symbol import VariableSymbol
from compiscript.typesystem.types import BOOLEAN, ERROR, INTEGER, STRING, Type

_BASE_TYPES: dict[str, Type] = {
    "integer": INTEGER,
    "string": STRING,
    "boolean": BOOLEAN,
}


def _resolve_type_annotation(type_ctx: CompiscriptParser.TypeContext) -> Type:
    """Traduce un nodo `type` de la gramatica (ej. `integer`, `integer[]`,
    `Perro`) a un Type del walking skeleton. Los tipos que todavia no
    estan modelados (arreglos, clases) caen en ERROR a proposito: no
    generan un diagnostico nuevo, solo significa "este tipo se valida en
    una fase posterior del proyecto", no "el codigo esta mal"."""
    text = type_ctx.getText()
    if "[" in text:
        return ERROR  # ArrayType todavia no existe en este walking skeleton
    base_name = type_ctx.baseType().getText()
    return _BASE_TYPES.get(base_name, ERROR)  # nombre de clase -> ERROR por ahora


class SemanticAnalyzer(CompiscriptVisitor):
    def __init__(self) -> None:
        self.diagnostics = DiagnosticList()
        self.global_scope = Scope(ScopeKind.GLOBAL)
        self.current_scope: Scope = self.global_scope

    # ------------------------------------------------------------------
    # Programa y bloques: manejo de ambitos
    # ------------------------------------------------------------------

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        for statement in ctx.statement():
            self.visit(statement)
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        # Cada '{' abre un nuevo ambito BLOCK, hijo del ambito actual
        # (ver diseno, seccion 5). Esto es lo que hace que una variable
        # declarada dentro de un bloque no "se filtre" hacia afuera.
        previous_scope = self.current_scope
        self.current_scope = previous_scope.child(ScopeKind.BLOCK)
        for statement in ctx.statement():
            self.visit(statement)
        self.current_scope = previous_scope
        return None

    # ------------------------------------------------------------------
    # Declaraciones: aqui se aplica SEM-SCOPE-002 (redeclaracion)
    # ------------------------------------------------------------------

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        name = ctx.Identifier().getText()
        line, column = ctx.Identifier().symbol.line, ctx.Identifier().symbol.column

        declared_type = ERROR
        if ctx.typeAnnotation() is not None:
            declared_type = _resolve_type_annotation(ctx.typeAnnotation().type_())

        initialized = ctx.initializer() is not None
        if ctx.initializer() is not None:
            self.visit(ctx.initializer())

        self._declare(name, declared_type, is_const=False, initialized=initialized, line=line, column=column)
        return None

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        name = ctx.Identifier().getText()
        line, column = ctx.Identifier().symbol.line, ctx.Identifier().symbol.column

        declared_type = ERROR
        if ctx.typeAnnotation() is not None:
            declared_type = _resolve_type_annotation(ctx.typeAnnotation().type_())

        # La gramatica ya obliga a `const x = expr;` (el '=' expression no
        # es opcional en constantDeclaration), asi que la regla "const debe
        # inicializarse" del enunciado (2.1) queda garantizada por sintaxis
        # y no hace falta revalidarla aqui.
        self.visit(ctx.expression())

        self._declare(name, declared_type, is_const=True, initialized=True, line=line, column=column)
        return None

    def _declare(self, name: str, decl_type: Type, *, is_const: bool, initialized: bool, line: int, column: int) -> None:
        symbol = VariableSymbol(
            name=name,
            decl_type=decl_type,
            is_const=is_const,
            initialized=initialized,
            line=line,
            column=column,
        )
        if not self.current_scope.define(symbol):
            self.diagnostics.error(
                "SEM-SCOPE-002",
                f"El identificador '{name}' ya fue declarado en este ambito.",
                line,
                column,
            )

    # ------------------------------------------------------------------
    # Uso de identificadores: aqui se aplica SEM-SCOPE-001 (no declarada)
    # ------------------------------------------------------------------

    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        name = ctx.Identifier().getText()
        symbol = self.current_scope.resolve(name)
        if symbol is None:
            token = ctx.Identifier().symbol
            self.diagnostics.error(
                "SEM-SCOPE-001",
                f"Uso de variable no declarada: '{name}'.",
                token.line,
                token.column,
            )
            return ERROR
        return symbol.decl_type

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        expressions = ctx.expression()
        if len(expressions) == 1:
            # alternativa: Identifier '=' expression ';'
            name = ctx.Identifier().getText()
            token = ctx.Identifier().symbol
            if self.current_scope.resolve(name) is None:
                self.diagnostics.error(
                    "SEM-SCOPE-001",
                    f"Uso de variable no declarada: '{name}'.",
                    token.line,
                    token.column,
                )
            self.visit(expressions[0])
        else:
            # alternativa: expression '.' Identifier '=' expression ';'
            # (asignacion a una propiedad -- la existencia del atributo se
            # valida en la fase de reglas de clases, no aqui)
            self.visit(expressions[0])
            self.visit(expressions[1])
        return None


def analyze_source(source: str) -> tuple[SemanticAnalyzer, list]:
    """Corre el pipeline completo (lexer -> parser -> analizador
    semantico) sobre un string de codigo Compiscript. Devuelve el
    analizador (con su Scope global y su lista de diagnosticos) y los
    errores de sintaxis encontrados, si los hay."""
    from antlr4 import CommonTokenStream, InputStream
    from antlr4.error.ErrorListener import ErrorListener

    from compiscript.grammar.generated.CompiscriptLexer import CompiscriptLexer

    class _CollectingErrorListener(ErrorListener):
        def __init__(self) -> None:
            super().__init__()
            self.errors: list[str] = []

        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):  # noqa: N803
            self.errors.append(f"linea {line}:{column} {msg}")

    error_listener = _CollectingErrorListener()

    lexer = CompiscriptLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)

    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    tree = parser.program()

    analyzer = SemanticAnalyzer()
    if not error_listener.errors:
        analyzer.visit(tree)

    return analyzer, error_listener.errors
