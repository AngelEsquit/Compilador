"""Representacion del programa en ensamblador MIPS.

El generador no concatena texto: produce una lista de `Line`. Asi el optimizador de
mirilla y el simulador trabajan sobre la misma estructura (`op` y `args`) y el texto
solo se arma al final.
"""
from __future__ import annotations

from dataclasses import dataclass, field

INSTR = "instr"
LABEL = "label"
COMMENT = "comment"
DIRECTIVE = "directive"


@dataclass
class Line:
    """Una linea: instruccion, etiqueta, comentario o directiva."""

    kind: str
    op: str = ""  # mnemonico, nombre de la etiqueta o directiva (`.word`)
    args: tuple[str, ...] = ()
    comment: str = ""

    def to_text(self) -> str:
        if self.kind == LABEL:
            return f"{self.op}:"
        if self.kind == COMMENT:
            return f"    # {self.comment}" if self.comment else ""
        body = self.op if not self.args else f"{self.op} {', '.join(self.args)}"
        text = f"    {body}"
        return f"{text:<36}# {self.comment}" if self.comment else text


def instr(op: str, *args: str, comment: str = "") -> Line:
    return Line(INSTR, op, tuple(args), comment)


def label(name: str) -> Line:
    return Line(LABEL, name)


def comment(text: str) -> Line:
    return Line(COMMENT, comment=text)


@dataclass
class AsmProgram:
    data: list[Line] = field(default_factory=list)
    text: list[Line] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [".data"]
        lines += [line.to_text() for line in self.data]
        lines += ["", ".text", ".globl main"]
        lines += [line.to_text() for line in self.text]
        return "\n".join(lines) + "\n"


def _split_args(text: str) -> tuple[str, ...]:
    """Separa por comas respetando las cadenas entre comillas."""
    parts, current, quoted, escaped = [], "", False, False
    for char in text:
        if quoted:
            current += char
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            current += char
        elif char == ",":
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    return tuple(parts)


def _strip_comment(raw: str) -> tuple[str, str]:
    quoted = escaped = False
    for position, char in enumerate(raw):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "#":
            return raw[:position], raw[position + 1 :].strip()
    return raw, ""


def parse_lines(source: str) -> list[Line]:
    """Convierte texto ensamblador en lineas. Lo usan la biblioteca de ejecucion y el simulador."""
    lines: list[Line] = []
    for raw in source.splitlines():
        code, note = _strip_comment(raw)
        code = code.strip()
        if not code:
            if note:
                lines.append(comment(note))
            continue
        while True:  # `nombre:` puede ir seguido de una instruccion o directiva en la misma linea
            head, colon, rest = code.partition(":")
            if not colon or not head.strip() or any(c in head for c in ' "$(,'):
                break
            lines.append(label(head.strip()))
            code = rest.strip()
            if not code:
                break
        if not code:
            continue
        op, _, rest = code.partition(" ")
        kind = DIRECTIVE if op.startswith(".") else INSTR
        lines.append(Line(kind, op, _split_args(rest.strip()), note))
    return lines
