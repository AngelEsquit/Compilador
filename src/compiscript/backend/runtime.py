"""Biblioteca de ejecucion: rutinas MIPS que el codigo generado llama con `jal`.

Contrato: una rutina recibe sus argumentos en `$a0`-`$a1`, devuelve en `$v0` y solo
modifica `$a0`-`$a3`, `$v0`, `$v1` y `$ra`. Por eso el codigo generado no guarda sus
registros `$t` antes de llamarlas.

Solo se incluyen en el programa las rutinas que se usan.
"""
from __future__ import annotations

from compiscript.backend.asm import Line, parse_lines

# nombre -> (codigo, rutinas de las que depende, datos)
_ROUTINES: dict[str, tuple[str, tuple[str, ...], str]] = {
    "_print_int": (
        """
_print_int:
    li $v0, 1
    syscall
    j _print_newline
""",
        ("_print_newline",),
        "",
    ),
    "_print_newline": (
        """
_print_newline:
    li $a0, 10
    li $v0, 11
    syscall
    jr $ra
""",
        (),
        "",
    ),
    "_print_str": (
        """
_print_str:
    bnez $a0, _print_str_text
    la $a0, _text_null
_print_str_text:
    li $v0, 4
    syscall
    j _print_newline
""",
        ("_print_newline",),
        '_text_null: .asciiz "null"',
    ),
    "_print_bool": (
        """
_print_bool:
    la $v0, _text_false
    beqz $a0, _print_bool_text
    la $v0, _text_true
_print_bool_text:
    move $a0, $v0
    j _print_str
""",
        ("_print_str",),
        '_text_true: .asciiz "true"\n_text_false: .asciiz "false"',
    ),
    "_alloc": (
        """
_alloc:
    addiu $a0, $a0, 3
    srl $a0, $a0, 2
    sll $a0, $a0, 2
    li $v0, 9
    syscall
    jr $ra
""",
        (),
        "",
    ),
    "_concat": (
        """
_concat:
    move $a2, $a0
    move $a3, $a1
    li $v1, 1
_concat_len1:
    lbu $v0, 0($a0)
    beqz $v0, _concat_len2
    addiu $a0, $a0, 1
    addiu $v1, $v1, 1
    j _concat_len1
_concat_len2:
    lbu $v0, 0($a1)
    beqz $v0, _concat_alloc
    addiu $a1, $a1, 1
    addiu $v1, $v1, 1
    j _concat_len2
_concat_alloc:
    addiu $a0, $v1, 3
    srl $a0, $a0, 2
    sll $a0, $a0, 2
    li $v0, 9
    syscall
    move $a0, $v0
_concat_copy1:
    lbu $v1, 0($a2)
    beqz $v1, _concat_copy2
    sb $v1, 0($a0)
    addiu $a0, $a0, 1
    addiu $a2, $a2, 1
    j _concat_copy1
_concat_copy2:
    lbu $v1, 0($a3)
    sb $v1, 0($a0)
    beqz $v1, _concat_done
    addiu $a0, $a0, 1
    addiu $a3, $a3, 1
    j _concat_copy2
_concat_done:
    jr $ra
""",
        (),
        "",
    ),
    "_streq": (
        """
_streq:
    beq $a0, $a1, _streq_yes
    beqz $a0, _streq_no
    beqz $a1, _streq_no
_streq_loop:
    lbu $v0, 0($a0)
    lbu $v1, 0($a1)
    bne $v0, $v1, _streq_no
    beqz $v0, _streq_yes
    addiu $a0, $a0, 1
    addiu $a1, $a1, 1
    j _streq_loop
_streq_yes:
    li $v0, 1
    jr $ra
_streq_no:
    li $v0, 0
    jr $ra
""",
        (),
        "",
    ),
    # Error de ejecucion: `$a0` trae el mensaje. Sin manejadores de `try` instalados
    # el programa termina; el soporte de try/catch reemplaza esta rutina.
    "_throw": (
        """
_throw:
    move $a1, $a0
    la $a0, _text_error
    li $v0, 4
    syscall
    move $a0, $a1
    li $v0, 4
    syscall
    li $a0, 10
    li $v0, 11
    syscall
    li $a0, 1
    li $v0, 17
    syscall
""",
        (),
        '_text_error: .asciiz "Error de ejecucion: "',
    ),
    "_div_zero": (
        """
_div_zero:
    la $a0, _text_div_zero
    j _throw
""",
        ("_throw",),
        '_text_div_zero: .asciiz "division por cero"',
    ),
    "_index_error": (
        """
_index_error:
    la $a0, _text_index
    j _throw
""",
        ("_throw",),
        '_text_index: .asciiz "indice fuera de rango"',
    ),
    "_null_error": (
        """
_null_error:
    la $a0, _text_null_access
    j _throw
""",
        ("_throw",),
        '_text_null_access: .asciiz "acceso a null"',
    ),
}


def register_routine(name: str, code: str, depends: tuple[str, ...] = (), data: str = "") -> None:
    """Agrega o reemplaza una rutina (lo usan los modulos de clases y de try/catch)."""
    _ROUTINES[name] = (code, depends, data)


def runtime_lines(needed) -> tuple[list[Line], list[Line]]:
    """(texto, datos) de las rutinas pedidas y de las que dependen, en orden estable."""
    included: list[str] = []

    def include(name: str) -> None:
        if name in included:
            return
        included.append(name)
        for dependency in _ROUTINES[name][1]:
            include(dependency)

    for name in sorted(needed):
        include(name)
    text: list[Line] = []
    data: list[Line] = []
    for name in included:
        code, _, routine_data = _ROUTINES[name]
        text += parse_lines(code)
        data += parse_lines(routine_data)
    return text, data
