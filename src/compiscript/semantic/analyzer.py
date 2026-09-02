"""Analizador semantico de Compiscript (ANTLR Visitor).

Orquesta las reglas semanticas de tipos, ambitos y control de flujo.
"""
from __future__ import annotations

from typing import Optional

from compiscript.diagnostics import DiagnosticList
from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser
from compiscript.grammar.generated.CompiscriptVisitor import CompiscriptVisitor
from compiscript.semantic.rules_control_flow import (
    check_break_continue,
    check_condition,
    check_return_in_function,
)
from compiscript.semantic.declarations_pass import predeclare_functions
from compiscript.semantic.rules_arrays import (
    check_array_literal,
    check_foreach_collection,
    check_index_access,
)
from compiscript.semantic.rules_functions import (
    build_function_symbol,
    check_call,
    check_return_type,
    declare_function,
)
from compiscript.semantic.rules_scope import (
    declare_variable,
    resolve_variable,
)
from compiscript.semantic.rules_types import (
    check_arithmetic_binary_op,
    check_assignment_compatibility,
    check_equality_op,
    check_logical_binary_op,
    check_relational_op,
    check_ternary_op,
    check_unary_op,
)
from compiscript.semantic.type_resolution import resolve_type_node
from compiscript.symbols.scope import Scope, ScopeKind
from compiscript.symbols.symbol import ClassSymbol, FunctionSymbol
from compiscript.typesystem.types import (
    BOOLEAN,
    ERROR,
    INTEGER,
    NULL,
    STRING,
    VOID,
    ClassType,
    ErrorType,
    Type,
)


class SemanticAnalyzer(CompiscriptVisitor):
    """Visitor principal para el analisis semantico de Compiscript."""

    def __init__(self) -> None:
        self.diagnostics = DiagnosticList()
        self.global_scope = Scope(ScopeKind.GLOBAL, name="global")
        self.current_scope: Scope = self.global_scope
        # Atributos heredados: contexto de la funcion en curso y firmas que la
        # pasada de pre-declaracion ya registro en el ambito actual.
        self.function_stack: list[FunctionSymbol] = []
        self.predeclared_stack: list[dict] = []

    @property
    def current_function(self) -> Optional[FunctionSymbol]:
        return self.function_stack[-1] if self.function_stack else None

    def _visit_scoped_statements(self, statements) -> None:
        """Pre-declara las funciones del bloque y despues visita sus sentencias."""
        self.predeclared_stack.append(
            predeclare_functions(statements, self.current_scope, self.diagnostics)
        )
        for statement in statements:
            self.visit(statement)
        self.predeclared_stack.pop()

    # ---------------------------------------------------------
    # Programa y Bloques
    # ---------------------------------------------------------

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        self._visit_scoped_statements(ctx.statement())
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.BLOCK)
        self._visit_scoped_statements(ctx.statement())
        self.current_scope = prev
        return None

    # ---------------------------------------------------------
    # Declaraciones de Variables y Constantes
    # ---------------------------------------------------------

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        ident = ctx.Identifier()
        name = ident.getText()
        line, col = ident.symbol.line, ident.symbol.column

        decl_type = ERROR
        if ctx.typeAnnotation() is not None:
            decl_type = resolve_type_node(ctx.typeAnnotation().type_())

        init_type = None
        if ctx.initializer() is not None:
            init_type = self.visit(ctx.initializer().expression())

        # Inferencia de tipo si no se especifico anotacion
        if isinstance(decl_type, ErrorType) and init_type is not None and not isinstance(init_type, ErrorType):
            decl_type = init_type

        # Validacion de compatibilidad de tipo del inicializador
        if init_type is not None and not isinstance(decl_type, ErrorType):
            check_assignment_compatibility(
                decl_type, init_type, is_const=False, line=line, col=col, diag=self.diagnostics, symbol_name=name
            )

        declare_variable(
            name=name,
            decl_type=decl_type,
            is_const=False,
            initialized=(ctx.initializer() is not None),
            line=line,
            col=col,
            scope=self.current_scope,
            diag=self.diagnostics,
        )
        return None

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        ident = ctx.Identifier()
        name = ident.getText()
        line, col = ident.symbol.line, ident.symbol.column

        decl_type = ERROR
        if ctx.typeAnnotation() is not None:
            decl_type = resolve_type_node(ctx.typeAnnotation().type_())

        init_type = self.visit(ctx.expression())

        # Inferencia de tipo si no tiene anotacion explicita
        if isinstance(decl_type, ErrorType) and init_type is not None and not isinstance(init_type, ErrorType):
            decl_type = init_type

        # Validacion de compatibilidad de tipo
        if init_type is not None and not isinstance(decl_type, ErrorType):
            check_assignment_compatibility(
                decl_type, init_type, is_const=False, line=line, col=col, diag=self.diagnostics, symbol_name=name
            )

        declare_variable(
            name=name,
            decl_type=decl_type,
            is_const=True,
            initialized=True,
            line=line,
            col=col,
            scope=self.current_scope,
            diag=self.diagnostics,
        )
        return None

    # ---------------------------------------------------------
    # Asignaciones
    # ---------------------------------------------------------

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        expressions = ctx.expression()
        if len(expressions) == 1:
            # Identifier '=' expression ';'
            ident = ctx.Identifier()
            name = ident.getText()
            line, col = ident.symbol.line, ident.symbol.column

            symbol, sym_type = resolve_variable(name, line, col, self.current_scope, self.diagnostics)
            val_type = self.visit(expressions[0])

            if symbol is not None:
                check_assignment_compatibility(
                    sym_type, val_type, symbol.is_const, line, col, self.diagnostics, symbol_name=name
                )
                self.current_scope.update(name, initialized=True)
        else:
            # expression '.' Identifier '=' expression ';'
            obj_type = self.visit(expressions[0])
            val_type = self.visit(expressions[1])
            # La resolucion de miembros de clase se amplia en rules_classes.py
        return None

    # ---------------------------------------------------------
    # Sentencias de Control de Flujo
    # ---------------------------------------------------------

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        cond_expr = ctx.expression()
        cond_type = self.visit(cond_expr)
        token = cond_expr.start
        check_condition(cond_type, "if", token.line, token.column, self.diagnostics)

        blocks = ctx.block()
        self.visit(blocks[0])
        if len(blocks) > 1:
            self.visit(blocks[1])
        return None

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.LOOP, name="while")

        cond_expr = ctx.expression()
        cond_type = self.visit(cond_expr)
        token = cond_expr.start
        check_condition(cond_type, "while", token.line, token.column, self.diagnostics)

        self.visit(ctx.block())
        self.current_scope = prev
        return None

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.LOOP, name="do-while")

        self.visit(ctx.block())

        cond_expr = ctx.expression()
        cond_type = self.visit(cond_expr)
        token = cond_expr.start
        check_condition(cond_type, "do-while", token.line, token.column, self.diagnostics)

        self.current_scope = prev
        return None

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.LOOP, name="for")

        # Inicializador del bucle for
        if ctx.variableDeclaration() is not None:
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment() is not None:
            self.visit(ctx.assignment())

        # Expresiones de condicion e incremento
        expressions = ctx.expression()
        if len(expressions) >= 1:
            cond_type = self.visit(expressions[0])
            token = expressions[0].start
            check_condition(cond_type, "for", token.line, token.column, self.diagnostics)
        if len(expressions) >= 2:
            self.visit(expressions[1])

        self.visit(ctx.block())
        self.current_scope = prev
        return None

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.LOOP, name="foreach")

        ident = ctx.Identifier()
        name = ident.getText()
        line, col = ident.symbol.line, ident.symbol.column

        col_expr = ctx.expression()
        col_type = self.visit(col_expr)
        elem_type = check_foreach_collection(
            col_type, col_expr.start.line, col_expr.start.column, self.diagnostics
        )

        declare_variable(
            name=name,
            decl_type=elem_type,
            is_const=False,
            initialized=True,
            line=line,
            col=col,
            scope=self.current_scope,
            diag=self.diagnostics,
        )

        self.visit(ctx.block())
        self.current_scope = prev
        return None

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        expr = ctx.expression()
        self.visit(expr)

        for case in ctx.switchCase():
            case_expr = case.expression()
            self.visit(case_expr)
            for stmt in case.statement():
                self.visit(stmt)

        if ctx.defaultCase() is not None:
            for stmt in ctx.defaultCase().statement():
                self.visit(stmt)

        return None

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        token = ctx.start
        check_break_continue(self.current_scope, "break", token.line, token.column, self.diagnostics)
        return None

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        token = ctx.start
        check_break_continue(self.current_scope, "continue", token.line, token.column, self.diagnostics)
        return None

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        token = ctx.start
        check_return_in_function(self.current_scope, token.line, token.column, self.diagnostics)

        returned_type = None
        if ctx.expression() is not None:
            returned_type = self.visit(ctx.expression())

        check_return_type(
            self.current_function, returned_type, token.line, token.column, self.diagnostics
        )
        return returned_type if returned_type is not None else VOID

    def visitPrintStatement(self, ctx: CompiscriptParser.PrintStatementContext):
        self.visit(ctx.expression())
        return None

    def visitExpressionStatement(self, ctx: CompiscriptParser.ExpressionStatementContext):
        return self.visit(ctx.expression())

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        blocks = ctx.block()
        # try block
        self.visit(blocks[0])

        # catch block
        catch_ident = ctx.Identifier()
        name = catch_ident.getText()
        line, col = catch_ident.symbol.line, catch_ident.symbol.column

        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.BLOCK, name="catch")
        declare_variable(
            name=name,
            decl_type=STRING,
            is_const=False,
            initialized=True,
            line=line,
            col=col,
            scope=self.current_scope,
            diag=self.diagnostics,
        )
        self.visit(blocks[1])
        self.current_scope = prev
        return None

    # ---------------------------------------------------------
    # Funciones y Clases (Estructura base)
    # ---------------------------------------------------------

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        name = ctx.Identifier().getText()

        # La pasada de pre-declaracion ya registro esta firma en el ambito;
        # solo se construye de nuevo si el nodo no paso por ella.
        predeclared = self.predeclared_stack[-1] if self.predeclared_stack else {}
        func_symbol = predeclared.get(ctx)
        if func_symbol is None:
            func_symbol = build_function_symbol(ctx, self.diagnostics)
            declare_function(func_symbol, self.current_scope, self.diagnostics)

        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.FUNCTION, name=name)
        for param in func_symbol.parameters:
            self.current_scope.define(param)

        self.function_stack.append(func_symbol)
        self.visit(ctx.block())
        self.function_stack.pop()

        self.current_scope = prev
        return None

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        idents = ctx.Identifier()
        class_name = idents[0].getText()
        line, col = idents[0].symbol.line, idents[0].symbol.column
        super_name = idents[1].getText() if len(idents) > 1 else None

        class_sym = ClassSymbol(
            name=class_name,
            decl_type=ClassType(class_name),
            superclass_name=super_name,
            line=line,
            column=col,
        )

        if not self.current_scope.define(class_sym):
            self.diagnostics.error(
                "SEM-SCOPE-002",
                f"La clase '{class_name}' ya fue declarada en este ambito.",
                line,
                col,
            )

        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.CLASS, name=class_name)

        members = ctx.classMember()
        self.predeclared_stack.append(
            predeclare_functions(members, self.current_scope, self.diagnostics, are_methods=True)
        )
        for member in members:
            self.visit(member)
        self.predeclared_stack.pop()

        self.current_scope = prev
        return None

    # ---------------------------------------------------------
    # Expresiones
    # ---------------------------------------------------------

    def visitAssignExpr(self, ctx: CompiscriptParser.AssignExprContext):
        lhs_node = ctx.lhs
        val_type = self.visit(ctx.assignmentExpr())

        # Si el lhs es un identificador simple
        ident_name = lhs_node.getText()
        token = lhs_node.start
        sym, sym_type = resolve_variable(ident_name, token.line, token.column, self.current_scope, self.diagnostics)
        if sym is not None:
            check_assignment_compatibility(
                sym_type, val_type, sym.is_const, token.line, token.column, self.diagnostics, symbol_name=ident_name
            )
            self.current_scope.update(ident_name, initialized=True)
        return val_type

    def visitPropertyAssignExpr(self, ctx: CompiscriptParser.PropertyAssignExprContext):
        self.visit(ctx.lhs)
        val_type = self.visit(ctx.assignmentExpr())
        return val_type

    def visitExprNoAssign(self, ctx: CompiscriptParser.ExprNoAssignContext):
        return self.visit(ctx.conditionalExpr())

    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext):
        cond_type = self.visit(ctx.logicalOrExpr())
        expressions = ctx.expression()
        if not expressions:
            return cond_type

        left_type = self.visit(expressions[0])
        right_type = self.visit(expressions[1])
        token = ctx.start
        return check_ternary_op(cond_type, left_type, right_type, token.line, token.column, self.diagnostics)

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext):
        children = ctx.logicalAndExpr()
        curr_type = self.visit(children[0])
        for child in children[1:]:
            right_type = self.visit(child)
            token = child.start
            curr_type = check_logical_binary_op(curr_type, right_type, "||", token.line, token.column, self.diagnostics)
        return curr_type

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        children = ctx.equalityExpr()
        curr_type = self.visit(children[0])
        for child in children[1:]:
            right_type = self.visit(child)
            token = child.start
            curr_type = check_logical_binary_op(curr_type, right_type, "&&", token.line, token.column, self.diagnostics)
        return curr_type

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext):
        children = ctx.relationalExpr()
        curr_type = self.visit(children[0])
        if len(children) > 1:
            for i in range(1, len(children)):
                right_type = self.visit(children[i])
                token = children[i].start
                # Buscar el operador exacto en el texto del nodo
                op = "==" if "==" in ctx.getText() else "!="
                curr_type = check_equality_op(curr_type, right_type, op, token.line, token.column, self.diagnostics)
        return curr_type

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext):
        children = ctx.additiveExpr()
        curr_type = self.visit(children[0])
        if len(children) > 1:
            for i in range(1, len(children)):
                right_type = self.visit(children[i])
                token = children[i].start
                curr_type = check_relational_op(curr_type, right_type, "<", token.line, token.column, self.diagnostics)
        return curr_type

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        children = ctx.multiplicativeExpr()
        curr_type = self.visit(children[0])
        if len(children) > 1:
            for i in range(1, len(children)):
                right_type = self.visit(children[i])
                token = children[i].start
                op = "+" if "+" in ctx.getText() else "-"
                curr_type = check_arithmetic_binary_op(curr_type, right_type, op, token.line, token.column, self.diagnostics)
        return curr_type

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        children = ctx.unaryExpr()
        curr_type = self.visit(children[0])
        if len(children) > 1:
            for i in range(1, len(children)):
                right_type = self.visit(children[i])
                token = children[i].start
                curr_type = check_arithmetic_binary_op(curr_type, right_type, "*", token.line, token.column, self.diagnostics)
        return curr_type

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext):
        if ctx.primaryExpr() is not None:
            return self.visit(ctx.primaryExpr())

        op = "-" if ctx.getText().startswith("-") else "!"
        sub_type = self.visit(ctx.unaryExpr())
        token = ctx.start
        return check_unary_op(sub_type, op, token.line, token.column, self.diagnostics)

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        if ctx.expression() is not None:
            return self.visit(ctx.expression())
        return ERROR

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        text = ctx.getText()
        if ctx.Literal() is not None:
            if text.startswith('"') and text.endswith('"'):
                return STRING
            return INTEGER
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        if text == "null":
            return NULL
        if text in ("true", "false"):
            return BOOLEAN
        return ERROR

    def visitArrayLiteral(self, ctx: CompiscriptParser.ArrayLiteralContext):
        element_types = [self.visit(e) for e in ctx.expression()]
        token = ctx.start
        return check_array_literal(element_types, token.line, token.column, self.diagnostics)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        curr_type = self.visit(ctx.primaryAtom())
        base_name = ctx.primaryAtom().getText()

        # Mientras rules_classes.py (Parte 3) no resuelva miembros, el tipo que
        # sigue a un '.' es desconocido. Se marca como ERROR para no encadenar
        # falsos positivos sobre codigo de clases que todavia no se valida.
        after_property = False

        for suffix in ctx.suffixOp():
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                arg_types: list[Type] = []
                if suffix.arguments() is not None:
                    arg_types = [self.visit(a) for a in suffix.arguments().expression()]
                if after_property:
                    curr_type = ERROR
                else:
                    curr_type = check_call(
                        curr_type,
                        base_name,
                        arg_types,
                        suffix.start.line,
                        suffix.start.column,
                        self.diagnostics,
                    )

            elif isinstance(suffix, CompiscriptParser.IndexExprContext):
                idx_expr = suffix.expression()
                idx_type = self.visit(idx_expr)
                curr_type = check_index_access(
                    curr_type,
                    idx_type,
                    base_name,
                    idx_expr.start.line,
                    idx_expr.start.column,
                    self.diagnostics,
                    report_non_array=not after_property,
                )

            elif isinstance(suffix, CompiscriptParser.PropertyAccessExprContext):
                after_property = True
                curr_type = ERROR

        return curr_type

    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        ident = ctx.Identifier()
        name = ident.getText()
        line, col = ident.symbol.line, ident.symbol.column
        _, sym_type = resolve_variable(name, line, col, self.current_scope, self.diagnostics)
        return sym_type

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        class_name = ctx.Identifier().getText()
        if ctx.arguments() is not None:
            for arg in ctx.arguments().expression():
                self.visit(arg)
        return ClassType(class_name)

    def visitThisExpr(self, ctx: CompiscriptParser.ThisExprContext):
        enclosing_class = self.current_scope.get_enclosing_class()
        if enclosing_class is None:
            self.diagnostics.error(
                "SEM-CLASS-002",
                "La palabra clave 'this' solo puede utilizarse dentro de metodos de una clase.",
                ctx.start.line,
                ctx.start.column,
            )
            return ERROR
        return ClassType(enclosing_class.name)


def analyze_source(source: str) -> tuple[SemanticAnalyzer, list]:
    """Ejecuta el lexer, parser y visitor semantico sobre codigo Compiscript."""
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
