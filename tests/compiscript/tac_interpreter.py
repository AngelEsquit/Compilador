"""Interprete de referencia del TAC de Compiscript, solo para las pruebas.

Ejecuta las cuadruplas que devuelve la accion `compiscriptTAC` y devuelve lo que
imprime el programa. Sirve para comprobar el *comportamiento* del codigo
intermedio (que los bucles terminen, que las closures lean la variable correcta,
que un metodo se resuelva segun la clase...) y no solo su texto.

Supuestos del interprete (documentados en docs/Lenguaje_Intermedio.md):
- `/` entre enteros es division entera.
- `print` muestra true/false/null en minusculas; las cadenas sin comillas.
- Los programas de prueba no declaran una variable local con el nombre de una global.
"""
from __future__ import annotations

import re

STEP_LIMIT = 200_000
_TEMP = re.compile(r"t\d+")


class TACRuntimeError(Exception):
    pass


class _Frame:
    def __init__(self, link=None, variables=None):
        self.vars = variables if variables is not None else {}
        self.link = link


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
        if _TEMP.fullmatch(name) or name in frame.vars or name not in self.main.vars:
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
        if op == "/":
            return a // b if isinstance(a, int) and isinstance(b, int) else a / b
        if op == "%":
            return a % b
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

    # ---------------------------------------------------------------- ejecucion
    def run(self) -> list[str]:
        self.execute(self.main, 0)
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
            ins = self.tac[pc]
            op, a1, a2, res = ins["op"], ins["arg1"], ins["arg2"], ins["result"]
            pc += 1

            if op == "label":
                pass
            elif op == "copy":
                self.write(frame, res, self.read(frame, a1))
            elif op in ("+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!="):
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
                self.write(frame, res, len(self.read(frame, a1)))
            elif op == "index_load":
                self.write(frame, res, self.read(frame, a1)[self.read(frame, a2)])
            elif op == "index_store":
                self.read(frame, res)[self.read(frame, a1)] = self.read(frame, a2)
            elif op == "member_load":
                self.write(frame, res, self.read(frame, a1)[a2])
            elif op == "member_store":
                self.read(frame, res)[a1] = self.read(frame, a2)
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
                label = self.methods[args[0]["__class__"]][method]
                self.write(frame, res, self.call(label, args, None))
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
            elif op == "return":
                return self.read(frame, a1) if a1 else None
            elif op == "end_function":
                return None
            elif op == "halt":
                return None
            elif op == "try":
                pass  # el lenguaje no tiene `throw`: el manejador nunca se activa
            elif op in ("function", "param_decl"):
                raise TACRuntimeError(f"el flujo entro en un cuerpo de funcion: {op} {res or a1}")
            else:
                raise TACRuntimeError(f"instruccion desconocida: {op}")


def run_tac(tac: list[dict], layout: dict) -> list[str]:
    """Ejecuta el TAC y devuelve las lineas que imprime el programa."""
    return _Machine(tac, layout).run()
