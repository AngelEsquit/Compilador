"""Seleccion de registros con descriptores (algoritmo getReg).

Se mantienen dos tablas mientras se traduce un bloque basico:

- descriptor de registros: que variables tienen su valor actual en cada registro;
- descriptor de direcciones: en que lugares (memoria y registros) esta el valor actual
  de cada variable.

Para elegir registro se sigue este orden:

1. si el operando ya esta en un registro, se usa ese;
2. si hay un registro libre, se toma;
3. si no, se desaloja el registro mas barato: primero los que no obligan a guardar nada
   (su valor esta muerto o tambien esta en memoria) y, entre iguales, el que se usara
   mas tarde. Si el valor sigue vivo y solo existe en ese registro, se guarda en su casa
   (derrame).

Al terminar el bloque solo se guardan las variables vivas cuyo valor no esta en memoria.
"""
from __future__ import annotations

from compiscript.backend.operands import Const, Var

MEM = "mem"
ALLOCATABLE = ("$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "$t9")
MIN_REGISTERS = 3  # una instruccion usa a lo sumo dos operandos y un resultado, o tres operandos


class RegisterAllocator:
    def __init__(self, registers, emit) -> None:
        if len(registers) < MIN_REGISTERS:
            raise ValueError(f"se necesitan al menos {MIN_REGISTERS} registros")
        self.registers = tuple(registers)
        self._emit = emit
        self.reg_desc: dict[str, set[Var]] = {reg: set() for reg in self.registers}
        self.addr_desc: dict[Var, set[str]] = {}
        self.after: dict[Var, int] = {}
        self.current: frozenset[Var] = frozenset()
        self._pinned: list[str] = []
        self.events: list[dict] = []
        self.context = ""

    # ------------------------------------------------------------------ estado
    def reset(self) -> None:
        """Inicio de bloque: todo valor esta en su casa de memoria."""
        for held in self.reg_desc.values():
            held.clear()
        self.addr_desc.clear()
        self._pinned = []

    def begin(self, after: dict[Var, int], current=()) -> None:
        """Empieza una instruccion: `current` son las variables que lee y `after` las vivas despues."""
        self.after = after
        self.current = frozenset(current)
        self._pinned = []

    def unpin(self) -> None:
        """Libera los registros reservados por la instruccion en curso."""
        self._pinned = []

    def locations(self, var: Var) -> set[str]:
        return self.addr_desc.setdefault(var, {MEM})

    def register_of(self, var: Var):
        places = self.locations(var)
        return next((reg for reg in self.registers if reg in places), None)

    def _log(self, event: str, var: Var, reg: str) -> None:
        self.events.append({"function": self.context, "event": event, "variable": var.name, "register": reg})

    # ------------------------------------------------------------------ eleccion
    def _sole_holder(self, var: Var, reg: str, reading: bool = True) -> bool:
        """`reg` es el unico lugar con el valor de una variable que todavia se usara.

        Mientras se cargan operandos (`reading`) tambien cuentan los de la instruccion en curso.
        """
        needed = var in self.after or (reading and var in self.current)
        return needed and self.locations(var) == {reg}

    def _pick(self) -> str:
        candidates = [reg for reg in self.registers if reg not in self._pinned]
        if not candidates:
            raise RuntimeError("no quedan registros para la instruccion")
        for reg in candidates:
            if not self.reg_desc[reg]:
                return reg

        def cost(reg: str):
            held = self.reg_desc[reg]
            stores = sum(1 for var in held if self._sole_holder(var, reg))
            nearest = min(-1 if var in self.current else self.after.get(var, float("inf")) for var in held)
            return (stores, -nearest)

        return min(candidates, key=cost)

    def _evict(self, reg: str, keep: Var | None = None) -> None:
        """Vacia `reg`; guarda antes los valores vivos que solo existen ahi.

        Con `keep` se esta eligiendo el registro del resultado: los operandos ya se leyeron.
        """
        for var in sorted(self.reg_desc[reg], key=lambda v: (v.offset, v.name)):
            if var is keep:
                continue
            if self._sole_holder(var, reg, reading=keep is None):
                self.store(var, reg, "derrame")
            self.locations(var).discard(reg)
        self.reg_desc[reg] = set()

    def _pin(self, reg: str) -> str:
        if reg not in self._pinned:
            self._pinned.append(reg)
        return reg

    # ------------------------------------------------------------------ interfaz
    def store(self, var: Var, reg: str, reason: str = "guarda") -> None:
        self._emit("sb" if var.size == 1 else "sw", reg, var.home, comment=f"{reason} {var.name}")
        self.locations(var).add(MEM)
        self._log(reason, var, reg)

    def use(self, operand) -> str:
        """Registro con el valor del operando; lo carga si no esta en ninguno."""
        if isinstance(operand, Const):
            if not operand.is_label and operand.value == 0:
                return "$zero"
            reg = self._pick()
            self._evict(reg)
            self._emit("la" if operand.is_label else "li", reg, operand.text)
            return self._pin(reg)
        reg = self.register_of(operand)
        if reg is None:
            reg = self._pick()
            self._evict(reg)
            self._emit("lbu" if operand.size == 1 else "lw", reg, operand.home, comment=f"carga {operand.name}")
            self.reg_desc[reg] = {operand}
            self.locations(operand).add(reg)
            self._log("carga", operand, reg)
        return self._pin(reg)

    def define(self, var: Var) -> str:
        """Registro donde la instruccion dejara el nuevo valor de `var`."""
        reg = next((r for r in self.registers if self.reg_desc[r] == {var}), None)
        if reg is None:
            # el registro de un operando que muere en esta instruccion se puede reutilizar
            for candidate in self._pinned:
                held = self.reg_desc.get(candidate)
                if held is not None and all(v is var or v not in self.after for v in held):
                    reg = candidate
                    break
        if reg is None:
            reg = self._pick()
        self._evict(reg, keep=var)
        for other in self.registers:
            self.reg_desc[other].discard(var)
        self.reg_desc[reg] = {var}
        self.addr_desc[var] = {reg}
        self._log("asigna", var, reg)
        return self._pin(reg)

    def alias(self, var: Var, reg: str) -> None:
        """Copia `var = y`: no se emite codigo, `var` pasa a vivir en el registro de `y`."""
        for other in self.registers:
            self.reg_desc[other].discard(var)
        self.reg_desc[reg].add(var)
        self.addr_desc[var] = {reg}
        self._log("asigna", var, reg)

    def flush(self, live, clear: bool = True) -> None:
        """Guarda las variables de `live` cuyo valor no esta en memoria.

        Con `clear` (fin de bloque o llamada) los registros dejan de tener valores validos.
        """
        for var, places in list(self.addr_desc.items()):
            reg = self.register_of(var)
            if MEM not in places and var in live and reg is not None:
                self.store(var, reg)
        if clear:
            self.reset()
