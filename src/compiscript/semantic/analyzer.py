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
from compiscript.symbols.scope import Scope, ScopeKind
from compiscript.symbols.symbol import ClassSymbol, FunctionSymbol, ParameterSymbol
from compiscript.typesystem.types import (
    BOOLEAN,
    ERROR,
    INTEGER,
    NULL,
    STRING,
    VOID,
    ArrayType,
    ClassType,
    ErrorType,
    Type,
)


def resolve_type_node(type_ctx: Optional[CompiscriptParser.TypeContext]) -> Type:
    """Traduce un nodo `type` de la gramatica a la jerarquia `Type`."""
    if type_ctx is None:
        return ERROR

    base_ctx = type_ctx.baseType()
    if base_ctx is None:
        return ERROR

    base_name = base_ctx.getText()
    if base_name == "integer":
        base_type: Type = INTEGER
    elif base_name == "string":
        base_type = STRING
    elif base_name == "boolean":
        base_type = BOOLEAN
    else:
        base_type = ClassType(base_name)

    # Conteo de corchetes para arreglos multidimensionales
    full_text = type_ctx.getText()
    bracket_pairs = full_text.count("[]")
    if bracket_pairs > 0:
        return ArrayType(base_type, bracket_pairs)

    return base_type


class SemanticAnalyzer(CompiscriptVisitor):
    """Visitor principal para el analisis semantico de Compiscript."""

    def __init__(self) -> None:
        self.diagnostics = DiagnosticList()
        self.global_scope = Scope(ScopeKind.GLOBAL, name="global")
        self.current_scope: Scope = self.global_scope

    # ---------------------------------------------------------
    # Programa y Bloques
    # ---------------------------------------------------------

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        for statement in ctx.statement():
            self.visit(statement)
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.BLOCK)
        for statement in ctx.statement():
            self.visit(statement)
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
        if decl_type == ERROR and init_type is not None and not isinstance(init_type, ErrorType):
            decl_type = init_type

        # Validacion de compatibilidad de tipo del inicializador
        if init_type is not None and decl_type != ERROR:
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
        if decl_type == ERROR and init_type is not None and not isinstance(init_type, ErrorType):
            decl_type = init_type

        # Validacion de compatibilidad de tipo
        if init_type is not None and decl_type != ERROR:
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

        elem_type = ERROR
        if isinstance(col_type, ArrayType):
            elem_type = col_type.element_type if col_type.dimensions == 1 else ArrayType(col_type.element_type, col_type.dimensions - 1)
        elif not isinstance(col_type, ErrorType):
            self.diagnostics.error(
                "SEM-ARR-003",
                f"La expresion sobre la que itera foreach debe ser un arreglo (se recibio '{col_type.name}').",
                col_expr.start.line,
                col_expr.start.column,
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
        func_scope = check_return_in_function(self.current_scope, token.line, token.column, self.diagnostics)
        ret_type = VOID
        if ctx.expression() is not None:
            ret_type = self.visit(ctx.expression())
        return ret_type

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
        ident = ctx.Identifier()
        name = ident.getText()
        line, col = ident.symbol.line, ident.symbol.column

        ret_type = VOID
        if ctx.type_() is not None:
            ret_type = resolve_type_node(ctx.type_())

        param_symbols: list[ParameterSymbol] = []
        if ctx.parameters() is not None:
            for p in ctx.parameters().parameter():
                p_name = p.Identifier().getText()
                p_line, p_col = p.Identifier().symbol.line, p.Identifier().symbol.column
                p_type = resolve_type_node(p.type_()) if p.type_() is not None else ERROR
                param_symbols.append(
                    ParameterSymbol(name=p_name, decl_type=p_type, line=p_line, column=p_col)
                )

        func_symbol = FunctionSymbol(
            name=name,
            decl_type=ERROR,
            parameters=param_symbols,
            return_type=ret_type,
            line=line,
            column=col,
        )

        if not self.current_scope.define(func_symbol):
            self.diagnostics.error(
                "SEM-FUNC-001",
                f"La funcion '{name}' ya fue declarada en este ambito.",
                line,
                col,
            )

        # Ambito de la funcion
        prev = self.current_scope
        self.current_scope = prev.child(ScopeKind.FUNCTION, name=name)
        for p_sym in param_symbols:
            if not self.current_scope.define(p_sym):
                self.diagnostics.error(
                    "SEM-FUNC-002",
                    f"Parametro duplicado '{p_sym.name}' en la declaracion de funcion.",
                    p_sym.line,
                    p_sym.column,
                )

        self.visit(ctx.block())
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
        for member in ctx.classMember():
            self.visit(member)
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
        expressions = ctx.expression()
        if not expressions:
            return ArrayType(ERROR, 1)

        elem_types = [self.visit(e) for e in expressions]
        first_type = elem_types[0]
        for t in elem_types[1:]:
            if t != first_type and not isinstance(t, ErrorType) and not isinstance(first_type, ErrorType):
                token = ctx.start
                self.diagnostics.error(
                    "SEM-ARR-002",
                    f"Los elementos del arreglo deben ser del mismo tipo (se encontro '{first_type.name}' y '{t.name}').",
                    token.line,
                    token.column,
                )
                return ArrayType(ERROR, 1)

        if isinstance(first_type, ArrayType):
            return ArrayType(first_type.element_type, first_type.dimensions + 1)
        return ArrayType(first_type, 1)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        curr_type = self.visit(ctx.primaryAtom())
        for suffix in ctx.suffixOp():
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                # Invocacion
                if suffix.arguments() is not None:
                    for arg in suffix.arguments().expression():
                        self.visit(arg)
            elif isinstance(suffix, CompiscriptParser.IndexExprContext):
                # Indexacion
                idx_expr = suffix.expression()
                idx_type = self.visit(idx_expr)
                if idx_type != INTEGER and not isinstance(idx_type, ErrorType):
                    self.diagnostics.error(
                        "SEM-ARR-001",
                        f"El indice de acceso a arreglo debe ser de tipo integer (se recibio '{idx_type.name}').",
                        idx_expr.start.line,
                        idx_expr.start.column,
                    )
                if isinstance(curr_type, ArrayType):
                    curr_type = curr_type.element_type if curr_type.dimensions == 1 else ArrayType(curr_type.element_type, curr_type.dimensions - 1)
            elif isinstance(suffix, CompiscriptParser.PropertyAccessExprContext):
                # Acceso a propiedad
                pass
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
