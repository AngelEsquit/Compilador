"""Representacion intermedia de tres direcciones para Compiscript."""

from compiscript.intermediate.generator import generate_tac
from compiscript.intermediate.ir import Instruction, TACProgram

__all__ = ["Instruction", "TACProgram", "generate_tac"]