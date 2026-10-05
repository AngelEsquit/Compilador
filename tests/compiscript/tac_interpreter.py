"""Interprete de referencia del TAC de Compiscript, solo para las pruebas.

Ejecuta las cuadruplas que devuelve la accion `compiscriptTAC` y devuelve lo que
imprime el programa. Sirve para comprobar el *comportamiento* del codigo
intermedio (que los bucles terminen, que las closures lean la variable correcta,
que un metodo se resuelva segun la clase, que un `catch` capture el error...) y no
solo su texto.

Supuestos del interprete (documentados en docs/Lenguaje_Intermedio.md):
- `/` entre enteros es division entera.
- `print` muestra true/false/null en minusculas; las cadenas sin comillas.
- Los programas de prueba no declaran una variable local con el nombre de una global.
- Errores de ejecucion: division o modulo por cero ("division por cero"), indice fuera de
  rango ("indice fuera de rango") y acceso a null ("acceso a null"). Cada `try` instala un
  manejador en su registro; un error desenrolla los registros hasta el primero que tenga
  uno, salta a su etiqueta y deja el mensaje en `exception`. Sin manejador, el programa
  termina con `TACRuntimeError`.
"""
from __future__ import annotations

import re

STEP_LIMIT = 200_000
_TEMP = re.compile(r"t\d+")
_BINARY = ("+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=")


class TACRuntimeError(Exception):
    pass


class _Raise(Exception):
    """Error de ejecucion del programa interpretado (lo captura un `catch`)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class _Frame:
    def __init__(self, link=None, variables=None):
        self.vars = variables if variables is not None else {}
        self.link = link
        self.handlers: list[str] = []  # etiquetas de los `try` activos en este registro


class _Machine:
    def __init__(self, tac: list[dict], layout: dict):
        self.tac = tac
        self.labels = {i["result"]: n for n, i in enumerate(tac) if i["op"] == "label"}
        self.functions = {i["result"]: n for n, i in enumerate(tac) if i["op"] == "function"}
        self.methods = {
            cls["name"]: {m["name"]: m["label"] for m in cls["methods"]} for cls in layout["classes"]
        }
        self.superclass = {cls["name"]: cls["superclass"] for cls in layout["classes"]}
        self.main = _Frame()
        self.params: list = []
        self.output: list[str] = []
        self.steps = 0

    # ---------------------------------------------------------------- valores
    def read(self, frame: _Frame, token: str):
        if token == "true":
            return True
        if token == "false":
            return False
        if token == "null":
            return None
        if token.startswith('"'):
            return token[1:-1]
        try:
            return int(token)
        except ValueError:
            pass
        try:
            return float(token)
        except ValueError:
            pass
        if token in frame.vars:
            return frame.vars[token]
        if token in self.main.vars:
            return self.main.vars[token]
        raise TACRuntimeError(f"variable sin valor: {token}")

    def write(self, frame: _Frame, name: str, value) -> None:
        if _TEMP.fullmatch(name) or name == "exception" or name in frame.vars or name not in self.main.vars:
            frame.vars[name] = value
        else:
            self.main.vars[name] = value

    @staticmethod
    def format(value) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return "null"
        return str(value)

    @staticmethod
    def binary(op: str, a, b):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op in ("/", "%"):
            if b == 0:
                raise _Raise("division por cero")
            if op == "%":
                return a % b
            return a // b if isinstance(a, int) and isinstance(b, int) else a / b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        raise TACRuntimeError(f"operador desconocido: {op}")

    @staticmethod
    def not_null(value):
        if value is None:
            raise _Raise("acceso a null")
        return value

    @staticmethod
    def in_range(items, index):
        if index < 0 or index >= len(items):
            raise _Raise("indice fuera de rango")
        return index

    @staticmethod
    def check_handlers(frame: _Frame) -> None:
        if frame.handlers:
            raise TACRuntimeError(f"se sale del registro con manejadores sin desinstalar: {frame.handlers}")

    # ---------------------------------------------------------------- ejecucion
    def run(self) -> list[str]:
        try:
            self.execute(self.main, 0)
        except _Raise as error:
            raise TACRuntimeError(f"excepcion no capturada: {error.message}") from None
        return self.output

    def call(self, label: str, args: list, link):
        start = self.functions[label]
        frame = _Frame(link)
        position = start + 1
        index = 0
        while self.tac[position]["op"] == "param_decl":
            frame.vars[self.tac[position]["arg1"]] = args[index]
            index += 1
            position += 1
        return self.execute(frame, position)

    def execute(self, frame: _Frame, pc: int):
        hops = None  # `link n` pendiente para la siguiente llamada
        while True:
            self.steps += 1
            if self.steps > STEP_LIMIT:
                raise TACRuntimeError("el programa no termina (limite de pasos)")
            try:
                outcome = self.step(frame, pc, hops)
            except _Raise as error:
                if not frame.handlers:
                    raise  # desenrolla: lo atiende el registro del llamador
                handler = frame.handlers.pop()
                self.write(frame, "exception", error.message)
                pc = self.labels[handler]
                continue
            if outcome[0] == "return":
                return outcome[1]
            pc, hops = outcome[1], outcome[2]

    def step(self, frame: _Frame, pc: int, hops):
        ins = self.tac[pc]
        op, a1, a2, res = ins["op"], ins["arg1"], ins["arg2"], ins["result"]
        pc += 1

        if op == "label":
            pass
        elif op == "copy":
            self.write(frame, res, self.read(frame, a1))
        elif op in _BINARY:
            self.write(frame, res, self.binary(op, self.read(frame, a1), self.read(frame, a2)))
        elif op == "neg":
            self.write(frame, res, -self.read(frame, a1))
        elif op == "not":
            self.write(frame, res, not self.read(frame, a1))
        elif op == "goto":
            pc = self.labels[res]
        elif op == "if":
            if self.read(frame, a1):
                pc = self.labels[res]
        elif op == "ifFalse":
            if not self.read(frame, a1):
                pc = self.labels[res]
        elif op == "print":
            self.output.append(self.format(self.read(frame, a1)))
        elif op == "array":
            items = [] if not a1 else [self.read(frame, part) for part in a1.split(", ")]
            self.write(frame, res, items)
        elif op == "length":
            self.write(frame, res, len(self.not_null(self.read(frame, a1))))
        elif op == "index_load":
            items = self.not_null(self.read(frame, a1))
            self.write(frame, res, items[self.in_range(items, self.read(frame, a2))])
        elif op == "index_store":
            items = self.not_null(self.read(frame, res))
            items[self.in_range(items, self.read(frame, a1))] = self.read(frame, a2)
        elif op == "member_load":
            self.write(frame, res, self.not_null(self.read(frame, a1))[a2])
        elif op == "member_store":
            self.not_null(self.read(frame, res))[a1] = self.read(frame, a2)
        elif op == "env_load":
            owner = frame
            for _ in range(int(a1)):
                owner = owner.link
            self.write(frame, res, owner.vars[a2])
        elif op == "env_store":
            owner = frame
            for _ in range(int(a2)):
                owner = owner.link
            owner.vars[res] = self.read(frame, a1)
        elif op == "param":
            self.params.append(self.read(frame, a1))
        elif op == "link":
            hops = int(a1)
        elif op == "call_result":
            count = int(a2)
            args = self.params[len(self.params) - count :]
            del self.params[len(self.params) - count :]
            link = None
            if hops is not None:
                link = frame
                for _ in range(hops):
                    link = link.link
                hops = None
            self.write(frame, res, self.call(a1, args, link))
        elif op == "invoke":
            count = int(a2)
            args = self.params[len(self.params) - count :]
            del self.params[len(self.params) - count :]
            method = a1.rsplit(".", 1)[1]
            receiver = self.not_null(args[0])
            self.write(frame, res, self.call(self.methods[receiver["__class__"]][method], args, None))
        elif op == "new":
            count = int(a2)
            args = self.params[len(self.params) - count :]
            del self.params[len(self.params) - count :]
            instance = {"__class__": a1}
            owner = a1  # el constructor es el de la clase o, si no declara uno, el del ancestro mas cercano
            while owner and f"{owner}.constructor" not in self.functions:
                owner = self.superclass.get(owner)
            if owner:
                self.call(f"{owner}.constructor", [instance] + args, None)
            self.write(frame, res, instance)
        elif op == "try":
            frame.handlers.append(res)
        elif op == "endtry":
            if not frame.handlers:
                raise TACRuntimeError("endtry sin un try activo")
            frame.handlers.pop()
        elif op == "return":
            self.check_handlers(frame)
            return ("return", self.read(frame, a1) if a1 else None)
        elif op in ("end_function", "halt"):
            self.check_handlers(frame)
            return ("return", None)
        elif op in ("function", "param_decl"):
            raise TACRuntimeError(f"el flujo entro en un cuerpo de funcion: {op} {res or a1}")
        else:
            raise TACRuntimeError(f"instruccion desconocida: {op}")
        return ("next", pc, hops)


def run_tac(tac: list[dict], layout: dict) -> list[str]:
    """Ejecuta el TAC y devuelve las lineas que imprime el programa."""
    return _Machine(tac, layout).run()
