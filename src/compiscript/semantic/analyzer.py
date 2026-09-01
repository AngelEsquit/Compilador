"""Analizador semantico de Compiscript (ANTLR Visitor).

Reglas implementadas: SEM-SCOPE-001 (variable no declarada) y
SEM-SCOPE-002 (redeclaracion en el mismo ambito).
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
    """Traduce un nodo `type` de la gramatica a un Type. Los tipos aun no
    modelados (arreglos, clases) caen en ERROR sin generar diagnostico."""
    text = type_ctx.getText()
    if "[" in text:
        return ERROR  # ArrayType todavia no existe
    base_name = type_ctx.baseType().getText()
    return _BASE_TYPES.get(base_name, ERROR)  # nombre de clase -> ERROR por ahora


class SemanticAnalyzer(CompiscriptVisitor):
    def __init__(self) -> None:
        self.diagnostics = DiagnosticList()
        self.global_scope = Scope(ScopeKind.GLOBAL)
        self.current_scope: Scope = self.global_scope

    # Programa y bloques: manejo de ambitos

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        for statement in ctx.statement():
            self.visit(statement)
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        # Cada '{' abre un ambito BLOCK hijo, para que lo declarado adentro
        # no se filtre hacia afuera.
        previous_scope = self.current_scope
        self.current_scope = previous_scope.child(ScopeKind.BLOCK)
        for statement in ctx.statement():
            self.visit(statement)
        self.current_scope = previous_scope
        return None

    # Declaraciones: aqui se aplica SEM-SCOPE-002 (redeclaracion)

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

        # La gramatica ya obliga a `const x = expr;`, asi que la regla 2.1
        # "const debe inicializarse" queda garantizada por sintaxis.
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

    # Uso de identificadores: aqui se aplica SEM-SCOPE-001 (no declarada)

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
            # La existencia del atributo se valida en rules_classes.py.
            self.visit(expressions[0])
            self.visit(expressions[1])
        return None


def analyze_source(source: str) -> tuple[SemanticAnalyzer, list]:
    """Corre lexer, parser y analisis semantico sobre codigo Compiscript.

    Devuelve (analizador, errores de sintaxis).
    """
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
