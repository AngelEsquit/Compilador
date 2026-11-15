"""Clases, objetos y herencia en MIPS.

Un objeto es un bloque del monticulo. Su primera palabra (`0(obj)`) apunta a la tabla de
metodos de su clase y los campos siguen en el offset que fijo `symbols/layout.py`. Los campos
heredados conservan su offset, de modo que un metodo de la superclase los lee igual en una
instancia de cualquier subclase.

La tabla (`_vt_Clase`, en `.data`) tiene una palabra por metodo, en el orden de su `slot`. Una
subclase copia la tabla de su superclase y cambia las entradas que sobrescribe, asi que el
`slot` de un metodo es el mismo en toda la jerarquia. `r = invoke o.m, n` lee la tabla del
objeto real y salta con `jalr`: la clase estatica de `o` solo sirve para saber el `slot`.

Los metodos y constructores son funciones normales con `this` como primer parametro, es decir,
el primer argumento apilado (el que queda mas arriba en la pila).
"""
from __future__ import annotations

from compiscript.backend.asm import Line, label
from compiscript.backend.operands import UnsupportedFeature, access_size
from compiscript.typesystem.types import ClassType

ARG_SIZE = 4
TABLE_OFFSET = 0  # `0(obj)`: puntero a la tabla de metodos


def table_label(name: str) -> str:
    return f"_vt_{name}"


class ClassOps:
    # ------------------------------------------------------------------ datos
    def class_data(self) -> list[Line]:
        """Una tabla de metodos por clase, con la etiqueta MIPS de cada metodo en su `slot`."""
        lines: list[Line] = []
        for name, cls in self.layout.classes.items():
            if not lines:
                lines.append(Line("directive", ".align", ("2",)))
            entries = [self.function_label(method["label"]) for method in sorted(cls.methods, key=lambda m: m["slot"])]
            lines.append(label(table_label(name)))
            lines.append(Line("directive", ".word", tuple(entries) if entries else ("0",)))
        return lines

    # ------------------------------------------------------------------ busquedas
    def _class_of(self, token: str, ins) -> str:
        owner = self.type_of(token)
        if not isinstance(owner, ClassType) or owner.class_name not in self.layout.classes:
            raise UnsupportedFeature("clases", f"'{token}' no es un objeto de una clase conocida: {ins.to_text()}")
        return owner.class_name

    def _field(self, class_name: str, field: str, ins):
        for slot in self.layout.classes[class_name].fields:
            if slot.name == field:
                return slot
        raise UnsupportedFeature("clases", f"la clase {class_name} no tiene el campo '{field}': {ins.to_text()}")

    def _constructor(self, class_name: str):
        """Etiqueta MIPS del constructor de la clase o del ancestro mas cercano que tenga uno."""
        name = class_name
        while name is not None:
            if f"{name}.constructor" in self.layout.records:
                return self.function_label(f"{name}.constructor")
            name = self.layout.classes[name].superclass
        return None

    def _null_check(self, token: str, reg: str) -> None:
        if token != "this":
            self.before_throwing()
            self.branch_runtime("beqz", reg, "_null_error")

    # ------------------------------------------------------------------ instrucciones
    def _op_new(self, ins) -> None:
        """`r = new C, n`: reserva el objeto, guarda su tabla y llama al constructor con `this` primero."""
        if ins.arg1 not in self.layout.classes:
            raise UnsupportedFeature("clases", f"clase desconocida '{ins.arg1}': {ins.to_text()}")
        count = int(ins.arg2)
        constructor = self._constructor(ins.arg1)
        self.save_for_call()
        self.emit("li", "$a0", str(self.layout.classes[ins.arg1].size), comment=f"tamano de {ins.arg1}")
        self.call_runtime("_alloc")
        self.emit("la", "$a1", table_label(ins.arg1))
        self.emit("sw", "$a1", f"{TABLE_OFFSET}($v0)", comment="tabla de metodos")
        if constructor is None:
            self.pop_arguments(count)
            self.result(ins.result)
            return
        # `this` debe quedar debajo de los argumentos: se baja el tope y se corre cada argumento
        self.emit("addiu", "$sp", "$sp", str(-ARG_SIZE), comment="hueco para this")
        for position in range(count):
            self.emit("lw", "$a1", f"{ARG_SIZE * (position + 1)}($sp)")
            self.emit("sw", "$a1", f"{ARG_SIZE * position}($sp)")
        self.emit("sw", "$v0", f"{ARG_SIZE * count}($sp)", comment="this")
        self.emit("jal", constructor)
        self.emit("lw", "$v0", f"{ARG_SIZE * count}($sp)", comment="el objeto nuevo")
        self.pop_arguments(count + 1)
        self.result(ins.result)

    def _op_member_load(self, ins) -> None:
        """`r = o.f`"""
        slot = self._field(self._class_of(ins.arg1, ins), ins.arg2, ins)
        obj = self.regs.use(self.operand(ins.arg1))
        self._null_check(ins.arg1, obj)
        load = "lbu" if access_size(slot.size) == 1 else "lw"
        self.emit(load, self.regs.define(self.operand(ins.result)), f"{slot.offset}({obj})", comment=ins.arg2)

    def _op_member_store(self, ins) -> None:
        """`o.f = v` (`result` es `o`, `arg1` es `f` y `arg2` es `v`)."""
        class_name = self._class_of(ins.result, ins)
        slot = self._field(class_name, ins.arg1, ins)
        obj = self.regs.use(self.operand(ins.result))
        symbol = self.resolver.classes[class_name].resolve_member(ins.arg1)
        if self.needs_widening(ins.arg2, getattr(symbol, "decl_type", None)):
            self.int_to_float(ins.arg2, "$a0")
            value = "$a0"
        else:
            value = self.regs.use(self.operand(ins.arg2))
        self._null_check(ins.result, obj)
        store = "sb" if access_size(slot.size) == 1 else "sw"
        self.emit(store, value, f"{slot.offset}({obj})", comment=ins.arg1)

    def _op_invoke(self, ins) -> None:
        """`r = invoke o.m, n`: despacho dinamico por la tabla de metodos del objeto."""
        receiver, method = ins.arg1.rsplit(".", 1)
        count = int(ins.arg2)
        class_name = self._class_of(receiver, ins)
        entry = next((m for m in self.layout.classes[class_name].methods if m["name"] == method), None)
        if entry is None:
            raise UnsupportedFeature("clases", f"la clase {class_name} no tiene el metodo '{method}': {ins.to_text()}")
        self.save_for_call()
        self.emit("lw", "$a0", f"{ARG_SIZE * (count - 1)}($sp)", comment="receptor")
        self._null_check(receiver, "$a0")
        self.emit("lw", "$a1", f"{TABLE_OFFSET}($a0)", comment="tabla de metodos")
        self.emit("lw", "$a1", f"{ARG_SIZE * entry['slot']}($a1)", comment=f"metodo {method} (slot {entry['slot']})")
        self.emit("jalr", "$a1")
        self.pop_arguments(count)
        self.result(ins.result)
