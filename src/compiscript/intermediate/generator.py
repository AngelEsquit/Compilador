"""Generador de codigo de tres direcciones para el arbol ANTLR de Compiscript."""
from __future__ import annotations

from antlr4 import CommonTokenStream, InputStream

from compiscript.grammar.generated.CompiscriptLexer import CompiscriptLexer
from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser
from compiscript.grammar.generated.CompiscriptVisitor import CompiscriptVisitor
from compiscript.intermediate.ir import Instruction, TACProgram, TempAllocator


class TACGenerator(CompiscriptVisitor):
    """Traduce el arbol sintactico a instrucciones TAC legibles y serializables."""

    def __init__(self, reserved: frozenset[str] | set[str] = frozenset()) -> None:
        super().__init__()
        self.program = TACProgram()
        self._reserved = reserved
        self.temps = TempAllocator(reserved)
        self._label_number = 0
        self._deferred: list[Instruction] = []
        self._break_labels: list[str] = []
        self._continue_labels: list[str] = []

    def temp(self) -> str:
        return self.temps.acquire()

    def release(self, value: str) -> None:
        self.temps.release(value)

    def label(self, prefix: str = "L") -> str:
        value = f"{prefix}{self._label_number}"
        self._label_number += 1
        return value

    def emit_label(self, value: str) -> None:
        self.program.emit("label", result=value)

    def visitProgram(self, ctx):
        for statement in ctx.statement():
            self.visit(statement)
        # El programa principal termina en `halt`; los cuerpos de funcion y metodos
        # van despues para que la ejecucion secuencial nunca entre en ellos.
        self.program.emit("halt")
        self.program.instructions.extend(self._deferred)
        self.program.temp_counts["main"] = self.temps.count
        return None

    def visitBlock(self, ctx):
        for statement in ctx.statement():
            self.visit(statement)
        return None

    def visitVariableDeclaration(self, ctx):
        name = ctx.Identifier().getText()
        if ctx.initializer() is not None:
            value = self.visit(ctx.initializer().expression())
            self.program.emit("copy", arg1=value, result=name)
            self.release(value)
        return name

    def visitConstantDeclaration(self, ctx):
        value = self.visit(ctx.expression())
        self.program.emit("copy", arg1=value, result=ctx.Identifier().getText())
        self.release(value)
        return ctx.Identifier().getText()

    def visitAssignment(self, ctx):
        expressions = ctx.expression()
        value = self.visit(expressions[-1])
        if len(expressions) == 1:
            self.program.emit("copy", arg1=value, result=ctx.Identifier().getText())
        else:
            target = self.visit(expressions[0])
            self.program.emit("member_store", arg1=ctx.Identifier().getText(), arg2=value, result=target)
            self.release(target)
        self.release(value)
        return None

    def visitExpressionStatement(self, ctx):
        value = self.visit(ctx.expression())
        self.release(value)
        return None

    def visitPrintStatement(self, ctx):
        value = self.visit(ctx.expression())
        self.program.emit("print", arg1=value)
        self.release(value)
        return None

    def visitIfStatement(self, ctx):
        condition = self.visit(ctx.expression())
        false_label = self.label("else")
        end_label = self.label("endif")
        self.program.emit("ifFalse", arg1=condition, result=false_label)
        self.release(condition)
        self.visit(ctx.block(0))
        if len(ctx.block()) > 1:
            self.program.emit("goto", result=end_label)
        self.emit_label(false_label)
        if len(ctx.block()) > 1:
            self.visit(ctx.block(1))
            self.emit_label(end_label)
        return None

    def visitWhileStatement(self, ctx):
        start = self.label("while")
        end = self.label("endwhile")
        self.emit_label(start)
        condition = self.visit(ctx.expression())
        self.program.emit("ifFalse", arg1=condition, result=end)
        self.release(condition)
        self._break_labels.append(end)
        self._continue_labels.append(start)
        self.visit(ctx.block())
        self._continue_labels.pop()
        self._break_labels.pop()
        self.program.emit("goto", result=start)
        self.emit_label(end)
        return None

    def visitDoWhileStatement(self, ctx):
        start = self.label("do")
        end = self.label("enddo")
        self.emit_label(start)
        self._break_labels.append(end)
        self._continue_labels.append(start)
        self.visit(ctx.block())
        self._continue_labels.pop()
        self._break_labels.pop()
        condition = self.visit(ctx.expression())
        self.program.emit("if", arg1=condition, result=start)
        self.release(condition)
        self.emit_label(end)
        return None

    def visitForStatement(self, ctx):
        if ctx.variableDeclaration() is not None:
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment() is not None:
            self.visit(ctx.assignment())
        start = self.label("for")
        end = self.label("endfor")
        increment = self.label("increment")
        self.emit_label(start)
        expressions = ctx.expression()
        if expressions:
            condition = self.visit(expressions[0])
            self.program.emit("ifFalse", arg1=condition, result=end)
            self.release(condition)
        self._break_labels.append(end)
        self._continue_labels.append(increment)
        self.visit(ctx.block())
        self._continue_labels.pop()
        self._break_labels.pop()
        self.emit_label(increment)
        if len(expressions) > 1:
            value = self.visit(expressions[1])
            self.release(value)
        self.program.emit("goto", result=start)
        self.emit_label(end)
        return None

    def visitForeachStatement(self, ctx):
        collection = self.visit(ctx.expression())
        iterator = ctx.Identifier().getText()
        index = self.temp()
        self.program.emit("copy", arg1="0", result=index)
        start = self.label("foreach")
        end = self.label("endforeach")
        self.emit_label(start)
        item = self.temp()
        self.program.emit("index_load", arg1=collection, arg2=index, result=item)
        self.program.emit("copy", arg1=item, result=iterator)
        self.release(item)
        self._break_labels.append(end)
        self._continue_labels.append(start)
        self.visit(ctx.block())
        self._continue_labels.pop()
        self._break_labels.pop()
        next_index = self.temp()
        self.program.emit("binary", arg1=index, arg2="+ 1", result=next_index)
        self.program.emit("copy", arg1=next_index, result=index)
        self.release(next_index)
        self.program.emit("goto", result=start)
        self.emit_label(end)
        self.release(index)
        self.release(collection)
        return None

    def visitBreakStatement(self, ctx):
        if self._break_labels:
            self.program.emit("goto", result=self._break_labels[-1])
        return None

    def visitContinueStatement(self, ctx):
        if self._continue_labels:
            self.program.emit("goto", result=self._continue_labels[-1])
        return None

    def visitReturnStatement(self, ctx):
        if ctx.expression() is None:
            self.program.emit("return")
        else:
            value = self.visit(ctx.expression())
            self.program.emit("return", arg1=value)
            self.release(value)
        return None

    def visitFunctionDeclaration(self, ctx):
        self._emit_function(ctx.Identifier().getText(), ctx.parameters(), ctx.block())
        return None

    def _emit_function(self, name, parameters, block, is_method=False, prelude=None):
        """Emite un cuerpo de funcion en `_deferred`, con sus propios temporales y bucles."""
        saved = (self.program.instructions, self.temps, self._break_labels, self._continue_labels)
        self.program.instructions = []
        self.temps = TempAllocator(self._reserved)
        self._break_labels, self._continue_labels = [], []
        slot = len(self._deferred)

        self.program.emit("function", result=name)
        if is_method:
            self.program.emit("param_decl", arg1="this")
        if parameters is not None:
            for parameter in parameters.parameter():
                self.program.emit("param_decl", arg1=parameter.Identifier().getText())
        if prelude is not None:
            prelude()
        if block is not None:
            self.visit(block)
        self.program.emit("end_function", result=name)

        body = self.program.instructions
        self.program.temp_counts[name] = self.temps.count
        self.program.instructions, self.temps, self._break_labels, self._continue_labels = saved
        # Las funciones anidadas ya se agregaron tras `slot`; el cuerpo externo va primero.
        self._deferred[slot:slot] = body

    def visitClassDeclaration(self, ctx):
        class_name = ctx.Identifier(0).getText()
        initializers = []
        constructor = None
        methods = []
        for member in ctx.classMember():
            if member.functionDeclaration() is not None:
                function = member.functionDeclaration()
                if function.Identifier().getText() == "constructor":
                    constructor = function
                else:
                    methods.append(function)
                continue
            declaration = member.variableDeclaration()
            if declaration is not None:
                expression = declaration.initializer().expression() if declaration.initializer() is not None else None
            else:
                declaration = member.constantDeclaration()
                expression = declaration.expression()
            if expression is not None:
                initializers.append((declaration.Identifier().getText(), expression))

        def initialize_fields():
            for field_name, expression in initializers:
                value = self.visit(expression)
                self.program.emit("member_store", arg1=field_name, arg2=value, result="this")
                self.release(value)

        if constructor is not None or initializers:
            self._emit_function(
                f"{class_name}.constructor",
                constructor.parameters() if constructor is not None else None,
                constructor.block() if constructor is not None else None,
                is_method=True,
                prelude=initialize_fields if initializers else None,
            )
        for method in methods:
            self._emit_function(
                f"{class_name}.{method.Identifier().getText()}", method.parameters(), method.block(), is_method=True
            )
        return None

    def visitTryCatchStatement(self, ctx):
        catch_label = self.label("catch")
        end_label = self.label("endtry")
        self.program.emit("try", result=catch_label)
        self.visit(ctx.block(0))
        self.program.emit("goto", result=end_label)
        self.emit_label(catch_label)
        self.program.emit("copy", arg1="exception", result=ctx.Identifier().getText())
        self.visit(ctx.block(1))
        self.emit_label(end_label)
        return None

    def visitSwitchStatement(self, ctx):
        value = self.visit(ctx.expression())
        end = self.label("endswitch")
        case_labels = [self.label("case") for _ in ctx.switchCase()]
        default_label = self.label("default") if ctx.defaultCase() is not None else end
        for case, case_label in zip(ctx.switchCase(), case_labels):
            case_value = self.visit(case.expression())
            self.program.emit("if_rel", arg1=value, arg2=f"== {case_value}", result=case_label)
            self.release(case_value)
        self.program.emit("goto", result=default_label)
        for case, case_label in zip(ctx.switchCase(), case_labels):
            self.emit_label(case_label)
            for statement in case.statement():
                self.visit(statement)
        if ctx.defaultCase() is not None:
            self.emit_label(default_label)
            for statement in ctx.defaultCase().statement():
                self.visit(statement)
        self.emit_label(end)
        self.release(value)
        return None

    def visitAssignExpr(self, ctx):
        value = self.visit(ctx.assignmentExpr())
        suffixes = list(ctx.lhs.suffixOp())
        if not suffixes:
            self.program.emit("copy", arg1=value, result=ctx.lhs.primaryAtom().getText())
            return value
        last = suffixes[-1]
        base = self._left_hand_side(ctx.lhs, len(suffixes) - 1)
        if isinstance(last, CompiscriptParser.IndexExprContext):
            index = self.visit(last.expression())
            self.program.emit("index_store", arg1=index, arg2=value, result=base)
            self.release(index)
        elif isinstance(last, CompiscriptParser.PropertyAccessExprContext):
            self.program.emit("member_store", arg1=last.Identifier().getText(), arg2=value, result=base)
        self.release(base)
        return value

    def visitPropertyAssignExpr(self, ctx):
        value = self.visit(ctx.assignmentExpr())
        target = self.visit(ctx.lhs)
        self.program.emit("member_store", arg1=ctx.Identifier().getText(), arg2=value, result=target)
        self.release(target)
        return value

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitTernaryExpr(self, ctx):
        condition = self.visit(ctx.logicalOrExpr())
        expressions = ctx.expression()
        if not expressions:
            return condition
        result = self.temp()
        false_label = self.label("false")
        end_label = self.label("endternary")
        self.program.emit("ifFalse", arg1=condition, result=false_label)
        self.release(condition)
        left = self.visit(expressions[0])
        self.program.emit("copy", arg1=left, result=result)
        self.release(left)
        self.program.emit("goto", result=end_label)
        self.emit_label(false_label)
        right = self.visit(expressions[1])
        self.program.emit("copy", arg1=right, result=result)
        self.release(right)
        self.emit_label(end_label)
        return result

    def _binary(self, children, operators):
        value = self.visit(children[0])
        for index, child in enumerate(children[1:]):
            right = self.visit(child)
            result = self.temp()
            self.program.emit("binary", arg1=f"{value} {operators[index]}", arg2=right, result=result)
            self.release(value)
            self.release(right)
            value = result
        return value

    def visitLogicalOrExpr(self, ctx):
        return self._binary(ctx.logicalAndExpr(), ["||"] * (len(ctx.logicalAndExpr()) - 1))

    def visitLogicalAndExpr(self, ctx):
        return self._binary(ctx.equalityExpr(), ["&&"] * (len(ctx.equalityExpr()) - 1))

    def visitEqualityExpr(self, ctx):
        children = ctx.relationalExpr()
        operators = [ctx.getChild(2 * i - 1).getText() for i in range(1, len(children))]
        return self._binary(children, operators)

    def visitRelationalExpr(self, ctx):
        children = ctx.additiveExpr()
        operators = [ctx.getChild(2 * i - 1).getText() for i in range(1, len(children))]
        return self._binary(children, operators)

    def visitAdditiveExpr(self, ctx):
        children = ctx.multiplicativeExpr()
        operators = [ctx.getChild(2 * i - 1).getText() for i in range(1, len(children))]
        return self._binary(children, operators)

    def visitMultiplicativeExpr(self, ctx):
        children = ctx.unaryExpr()
        operators = [ctx.getChild(2 * i - 1).getText() for i in range(1, len(children))]
        return self._binary(children, operators)

    def visitUnaryExpr(self, ctx):
        if ctx.primaryExpr() is not None:
            return self.visit(ctx.primaryExpr())
        value = self.visit(ctx.unaryExpr())
        result = self.temp()
        self.program.emit("unary", arg1=ctx.getChild(0).getText(), arg2=value, result=result)
        self.release(value)
        return result

    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx):
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        return ctx.getText()

    def visitArrayLiteral(self, ctx):
        values = [self.visit(expression) for expression in ctx.expression()]
        result = self.temp()
        self.program.emit("array", arg1=", ".join(values), result=result)
        for value in values:
            self.release(value)
        return result

    def _arguments(self, call_suffix) -> list[str]:
        if call_suffix.arguments() is None:
            return []
        return [self.visit(arg) for arg in call_suffix.arguments().expression()]

    def _left_hand_side(self, ctx, count=None):
        """Evalua el atomo y los primeros `count` sufijos (todos si es None)."""
        suffixes = list(ctx.suffixOp())
        if count is not None:
            suffixes = suffixes[:count]
        value = self.visit(ctx.primaryAtom())
        position = 0
        while position < len(suffixes):
            suffix = suffixes[position]
            following = suffixes[position + 1] if position + 1 < len(suffixes) else None
            if isinstance(suffix, CompiscriptParser.PropertyAccessExprContext) and isinstance(
                following, CompiscriptParser.CallExprContext
            ):
                # Llamada a metodo: el receptor viaja como `this` y el metodo se resuelve en ejecucion.
                arguments = self._arguments(following)
                self.program.emit("param", arg1=value)
                for argument in arguments:
                    self.program.emit("param", arg1=argument)
                result = self.temp()
                self.program.emit(
                    "invoke",
                    arg1=f"{value}.{suffix.Identifier().getText()}",
                    arg2=str(len(arguments) + 1),
                    result=result,
                )
                for argument in arguments:
                    self.release(argument)
                self.release(value)
                value = result
                position += 2
                continue
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                arguments = self._arguments(suffix)
                for argument in arguments:
                    self.program.emit("param", arg1=argument)
                result = self.temp()
                self.program.emit("call_result", arg1=value, arg2=str(len(arguments)), result=result)
                for argument in arguments:
                    self.release(argument)
                self.release(value)
                value = result
            elif isinstance(suffix, CompiscriptParser.IndexExprContext):
                index = self.visit(suffix.expression())
                result = self.temp()
                self.program.emit("index_load", arg1=value, arg2=index, result=result)
                self.release(value)
                self.release(index)
                value = result
            else:
                result = self.temp()
                self.program.emit("member_load", arg1=value, arg2=suffix.Identifier().getText(), result=result)
                self.release(value)
                value = result
            position += 1
        return value

    def visitLeftHandSide(self, ctx):
        return self._left_hand_side(ctx)

    def visitIdentifierExpr(self, ctx):
        return ctx.Identifier().getText()

    def visitNewExpr(self, ctx):
        arguments = []
        if ctx.arguments() is not None:
            arguments = [self.visit(arg) for arg in ctx.arguments().expression()]
        for argument in arguments:
            self.program.emit("param", arg1=argument)
        result = self.temp()
        self.program.emit("new", arg1=ctx.Identifier().getText(), arg2=str(len(arguments)), result=result)
        for argument in arguments:
            self.release(argument)
        return result

    def visitThisExpr(self, ctx):
        return "this"


def _parse(source: str):
    lexer = CompiscriptLexer(InputStream(source))
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()
    identifiers = frozenset(
        token.text for token in tokens.tokens if token.type == CompiscriptLexer.Identifier
    )
    return tree, identifiers


def generate_tac(source: str) -> TACProgram:
    """Genera TAC; el bridge llama esta funcion solo tras validar semantica."""
    tree, identifiers = _parse(source)
    generator = TACGenerator(identifiers)
    generator.visit(tree)
    return generator.program
