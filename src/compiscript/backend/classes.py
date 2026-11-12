"""Clases, objetos y herencia en MIPS.

Pendiente. `MipsGenerator` hereda de `ClassOps`, asi que aqui se dispone de todo el
generador (`self.emit`, `self.regs`, `self.operand`, `self.layout`...).
"""
from __future__ import annotations

from compiscript.backend.asm import Line
from compiscript.backend.operands import UnsupportedFeature


class ClassOps:
    def class_data(self) -> list[Line]:
        """Lineas de `.data` propias de las clases (por ejemplo, las tablas de metodos)."""
        return []

    def _op_new(self, ins) -> None:
        raise UnsupportedFeature("clases", ins.to_text())

    def _op_member_load(self, ins) -> None:
        raise UnsupportedFeature("clases", ins.to_text())

    def _op_member_store(self, ins) -> None:
        raise UnsupportedFeature("clases", ins.to_text())

    def _op_invoke(self, ins) -> None:
        raise UnsupportedFeature("clases", ins.to_text())
