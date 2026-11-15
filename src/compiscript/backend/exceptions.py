"""try/catch y errores de ejecucion en MIPS.

Pila de manejadores. Cada `try` apila una entrada de 12 bytes en `_handlers`:
la direccion de su `catch`, `$fp` y `$sp`. `_handler_top` es el desplazamiento de la primera
entrada libre. `endtry` desapila.

Un error de ejecucion (`_div_zero`, `_index_error`, `_null_error`) deja el mensaje en `$a0` y salta a
`_throw`. Si la pila esta vacia el programa termina con el mensaje. Si no, `_throw` desapila el manejador
mas reciente, guarda el mensaje en la celda `exception`, restaura `$fp` y `$sp` y salta al `catch`.
Restaurar `$fp` y `$sp` descarta de una vez todos los registros de activacion que quedaron entre el error
y el `try`: ese es el desenrollado, y no hace falta recorrer las funciones una por una.

Un error salta al `catch` sin pasar por el fin del bloque basico, asi que las variables que el `catch`
lee deben estar en memoria antes de cada operacion que puede fallar (`before_throwing`).
"""
from __future__ import annotations

from compiscript.backend import runtime

ENTRY_SIZE = 12  # catch, fp, sp
MAX_HANDLERS = 1024
_FATAL_THROW = runtime._ROUTINES["_throw"]  # `_throw` sin manejadores: imprime el error y termina

_FATAL_CODE = _FATAL_THROW[0].replace("_throw:", "_throw_fatal:", 1)

_THROW = """
_throw:
    lw $a1, _handler_top
    beqz $a1, _throw_fatal
    addiu $a1, $a1, -{entry}
    sw $a1, _handler_top
    la $a2, _handlers
    addu $a2, $a2, $a1
    sw $a0, {exception}($gp)
    lw $fp, 4($a2)
    lw $sp, 8($a2)
    lw $a2, 0($a2)
    jr $a2
""" + _FATAL_CODE

_OVERFLOW = """
_handler_overflow:
    la $a0, _text_handlers
    j _throw_fatal
"""

_HANDLER_DATA = """
.align 2
_handler_top: .word 0
_handlers: .space {size}
_text_handlers: .asciiz "demasiados try anidados"
""" + _FATAL_THROW[2] + "\n"


class ExceptionOps:
    def prepare_exceptions(self) -> None:
        """Deja `_throw` en su version sin manejadores; `_op_try` instala la completa si el programa usa `try`."""
        runtime.register_routine("_throw", *_FATAL_THROW)
        self._try_regions: dict[str, list[tuple[int, str, int]]] = {}

    # ------------------------------------------------------------------ regiones de try
    def _regions(self) -> list[tuple[int, str, int]]:
        """(posicion del `try`, etiqueta de su `catch`, posicion del `catch`) de la funcion en curso."""
        name = self.regs.context
        if name not in self._try_regions:
            instructions = next((body for unit, body in self._units() if unit == name), [])
            catches = {ins.result: position for position, ins in enumerate(instructions) if ins.op == "label"}
            self._try_regions[name] = [
                (position, ins.result, catches[ins.result])
                for position, ins in enumerate(instructions)
                if ins.op == "try" and ins.result in catches
            ]
        return self._try_regions[name]

    def before_throwing(self) -> None:
        """Se llama justo antes de emitir una comprobacion que puede saltar a `_throw`.

        Dentro de un `try` las variables vivas en el `catch` deben estar en memoria en
        ese punto, porque el salto al manejador no pasa por el fin del bloque.
        """
        live: set = set()
        for start, catch, end in self._regions():
            if start < self.position < end:
                live |= self.label_live.get(catch, set())
        if live:
            self.regs.flush(live, clear=False)

    # ------------------------------------------------------------------ instrucciones
    def _install_runtime(self) -> None:
        data = _HANDLER_DATA.format(size=ENTRY_SIZE * MAX_HANDLERS)
        code = _THROW.format(entry=ENTRY_SIZE, exception=self.resolver.exception_offset)
        runtime.register_routine("_throw", code, (), data)
        runtime.register_routine("_handler_overflow", _OVERFLOW, ("_throw",), "")
        self.runtime.add("_throw")

    def _op_try(self, ins) -> None:
        """`try goto L`: apila (L, $fp, $sp). Termina el bloque: el `catch` es un segundo sucesor."""
        self._install_runtime()
        self.regs.flush(self.live_out)
        self.emit("lw", "$a0", "_handler_top", comment="manejadores instalados")
        self.emit("li", "$a1", str(ENTRY_SIZE * MAX_HANDLERS))
        self.branch_runtime("bgeu", "$a0", "$a1", "_handler_overflow")
        self.emit("la", "$a1", "_handlers")
        self.emit("addu", "$a1", "$a1", "$a0")
        self.emit("la", "$v0", ins.result)
        self.emit("sw", "$v0", "0($a1)", comment=f"catch {ins.result}")
        self.emit("sw", "$fp", "4($a1)")
        self.emit("sw", "$sp", "8($a1)")
        self.emit("addiu", "$a0", "$a0", str(ENTRY_SIZE))
        self.emit("sw", "$a0", "_handler_top")

    def _op_endtry(self, ins) -> None:
        """Desapila el manejador mas reciente. No termina el bloque."""
        self._install_runtime()
        self.emit("lw", "$a0", "_handler_top")
        self.emit("addiu", "$a0", "$a0", str(-ENTRY_SIZE))
        self.emit("sw", "$a0", "_handler_top", comment="desinstala el manejador")
