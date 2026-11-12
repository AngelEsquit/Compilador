"""try/catch y errores de ejecucion en MIPS.

Pendiente. `MipsGenerator` hereda de `ExceptionOps`, asi que aqui se dispone de todo el
generador. Mientras tanto, un error de ejecucion termina el programa (`_throw` en
`runtime.py`).
"""
from __future__ import annotations

from compiscript.backend.operands import UnsupportedFeature


class ExceptionOps:
    def before_throwing(self) -> None:
        """Se llama justo antes de emitir una comprobacion que puede saltar a `_throw`.

        Dentro de un `try` las variables vivas en el `catch` deben estar en memoria en
        ese punto, porque el salto al manejador no pasa por el fin del bloque.
        """

    def _op_try(self, ins) -> None:
        raise UnsupportedFeature("try/catch", ins.to_text())

    def _op_endtry(self, ins) -> None:
        raise UnsupportedFeature("try/catch", ins.to_text())
