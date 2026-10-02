"""Generador de codigo de tres direcciones para el arbol ANTLR de Compiscript."""
from __future__ import annotations

from antlr4 import CommonTokenStream, InputStream

from compiscript.grammar.generated.CompiscriptLexer import CompiscriptLexer
from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser
from compiscript.grammar.generated.CompiscriptVisitor import CompiscriptVisitor
from compiscript.intermediate.ir import TACProgram, TempAllocator


class TACGenerator(CompiscriptVisitor):
    """Traduce el arbol sintactico a instrucciones TAC legibles y serializables."""

    def __init__(self) -> None:
        super().__init__()
        self.program = TACProgram()
        self.temps = TempAllocator()
        self._label_number = 0
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

    @staticmethod
    def _is_temp(value: str) -> bool:
        return value.startswith("t") and value[1:].isdigit()

    def visitProgram(self, ctx):
        for statement in ctx.statement():
            self.visit(statement)
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
        name = ctx.Identifier().getText()
        self.program.emit("function", result=name)
        if ctx.parameters() is not None:
            for parameter in ctx.parameters().parameter():
                self.program.emit("param_decl", arg1=parameter.Identifier().getText())
        self.visit(ctx.block())
        self.program.emit("end_function", result=name)
        return None

    def visitClassDeclaration(self, ctx):
        for member in ctx.classMember():
            self.visit(member)
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
        target = ctx.lhs.getText()
        self.program.emit("copy", arg1=value, result=target)
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

    def visitLeftHandSide(self, ctx):
        value = self.visit(ctx.primaryAtom())
        for suffix in ctx.suffixOp():
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                arguments = []
                if suffix.arguments() is not None:
                    arguments = [self.visit(arg) for arg in suffix.arguments().expression()]
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
        return value

    def visitIdentifierExpr(self, ctx):
        return ctx.Identifier().getText()

    def visitNewExpr(self, ctx):
        arguments = []
        if ctx.arguments() is not None:
            arguments = [self.visit(arg) for arg in ctx.arguments().expression()]
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
    return parser.program()


def generate_tac(source: str) -> TACProgram:
    """Genera TAC; el bridge llama esta funcion solo tras validar semantica."""
    tree = _parse(source)
    generator = TACGenerator()
    generator.visit(tree)
    return generator.program
