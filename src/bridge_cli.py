"""Bridge JSON entre el IDE y el compilador de Compiscript.

El IDE lanza este script, escribe el payload por stdin y lee un unico objeto JSON por stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from compiscript.semantic.analyzer import analyze_source
from compiscript.intermediate.generator import generate_tac


def _normalize_path(raw: str) -> Path:
    r"""Normalize a path string coming from the Tauri/Windows layer.

    Handles two Windows-specific issues:
    1. Double-escaped separators (C:\\\\Users\\\\...) caused by the path
       being JSON-serialized more than once in the Rust/JS pipeline.
    2. Extended-length prefix (\\?\) added by Windows canonicalize().
    """
    s = raw.strip()
    # Detect double-escaped Windows paths: consecutive \\ where \ is the
    # intended separator. Only applies when there are no forward slashes.
    if "\\\\" in s and "/" not in s:
        s = s.replace("\\\\", "\\")
    # Strip Windows extended-length prefix \\?\ (after unescaping)
    if s.startswith("\\\\?\\"):
        s = s[4:]
    return Path(s)


def _read_text_from_payload_path(raw: str, *, label: str) -> str:
    path = _normalize_path(raw)
    if path.exists():
        return path.read_text(encoding="utf-8")

    # Fallback: Windows also accepts forward slashes.
    alt = Path(str(path).replace("\\", "/"))
    if alt.exists():
        return alt.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"{label} no encontrado. "
        f"normalized={path!r}, exists={path.exists()}, "
        f"alt={alt!r}, alt_exists={alt.exists()}, cwd={Path.cwd()}"
    )


def _diagnostic_to_dict(diagnostic) -> dict:
    return {
        "severity": diagnostic.severity.value,
        "code": diagnostic.code,
        "message": diagnostic.message,
        "line": diagnostic.line,
        "column": diagnostic.column,
    }


def _read_compiscript_source(payload: dict) -> str:
    cps_source_raw = payload.get("cpsSource")
    cps_path_raw = payload.get("cpsPath")

    if cps_source_raw is not None:
        return str(cps_source_raw)
    if cps_path_raw:
        return _read_text_from_payload_path(str(cps_path_raw), label="cpsPath")
    raise ValueError("Debe enviar 'cpsPath' o 'cpsSource'")


def _parse_tree_to_dict(node, rule_names: list[str]) -> dict:
    """Serializa un nodo del arbol sintactico de ANTLR a formato nodo/hijos.

    Generico para cualquier gramatica ANTLR: no conoce nada especifico de
    Compiscript, solo distingue nodos de regla (RuleContext) de hojas
    (TerminalNode) usando la API estandar del arbol de parseo.
    """
    from antlr4.tree.Tree import TerminalNode

    if isinstance(node, TerminalNode):
        token = node.getSymbol()
        return {
            "kind": "terminal",
            "label": node.getText(),
            "line": token.line if token is not None else None,
            "column": token.column if token is not None else None,
            "children": [],
        }

    rule_index = node.getRuleIndex()
    label = rule_names[rule_index] if 0 <= rule_index < len(rule_names) else type(node).__name__
    start_token = node.start
    children = [_parse_tree_to_dict(node.getChild(i), rule_names) for i in range(node.getChildCount())]

    return {
        "kind": "rule",
        "label": label,
        "line": start_token.line if start_token is not None else None,
        "column": start_token.column if start_token is not None else None,
        "children": children,
    }


def _parse_compiscript_tree(source: str):
    """Construye el arbol sintactico de Compiscript sin correr el analisis semantico."""
    from antlr4 import CommonTokenStream, InputStream
    from antlr4.error.ErrorListener import ErrorListener

    from compiscript.grammar.generated.CompiscriptLexer import CompiscriptLexer
    from compiscript.grammar.generated.CompiscriptParser import CompiscriptParser

    class _CollectingErrorListener(ErrorListener):
        def __init__(self) -> None:
            super().__init__()
            self.errors: list[str] = []

        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):  # noqa: N803
            self.errors.append(f"linea {line}:{column} {msg}")

    error_listener = _CollectingErrorListener()

    lexer = CompiscriptLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(error_listener)

    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    parser.removeErrorListeners()
    parser.addErrorListener(error_listener)

    tree = parser.program()
    return tree, parser.ruleNames, error_listener.errors


def _assemble_and_run(source: str, analyzer, payload: dict) -> dict:
    """Genera MIPS y lo ejecuta en el simulador.

    `registers` (opcional) limita cuantos registros reparte el asignador y `peephole`
    (opcional) desactiva la optimizacion por mirilla. Un fallo de esta etapa no es un
    error del bridge: se devuelve en `error` (generacion) o `runError` (ejecucion).
    """
    from compiscript.backend import ALLOCATABLE, UnsupportedFeature, compile_to_mips
    from compiscript.backend.asm import INSTR
    from compiscript.backend.simulator import SimulatorError, run_mips

    count = payload.get("registers")
    registers = ALLOCATABLE[: max(3, min(int(count), len(ALLOCATABLE)))] if count else ALLOCATABLE
    try:
        compiled = compile_to_mips(source, analyzer, registers, peephole=bool(payload.get("peephole", True)))
    except UnsupportedFeature as error:
        return {"error": f"El backend aun no traduce esta construccion: {error}"}

    summary: dict[str, dict[str, int]] = {}
    for event in compiled.allocation:
        counts = summary.setdefault(event["function"], {"carga": 0, "asigna": 0, "derrame": 0, "guarda": 0})
        counts[event["event"]] += 1
    result = {
        "asm": compiled.text,
        "instructionCount": sum(1 for line in compiled.program.text if line.kind == INSTR),
        "registers": list(compiled.registers),
        "allocation": compiled.allocation,
        "allocationSummary": [{"function": name, **counts} for name, counts in summary.items()],
        "peephole": compiled.peephole,
        "functions": list(compiled.functions.values()),
    }
    try:
        machine = run_mips(compiled.text, compiled.functions)
    except SimulatorError as error:
        result["runError"] = str(error)
        return result
    result.update(
        output=machine.output,
        exitCode=machine.exit_code,
        steps=machine.steps,
        tree=machine.root.to_dict(),
        treeText=machine.root.to_text(),
    )
    return result


def _run_action(payload: dict) -> dict:
    action = payload.get("action")

    if action is None:
        raise ValueError("Falta campo 'action' en request")

    if action == "compiscriptCheck":
        source = _read_compiscript_source(payload)
        analyzer, syntax_errors = analyze_source(source)

        diagnostics = [_diagnostic_to_dict(d) for d in analyzer.diagnostics]
        return {
            "ok": not syntax_errors and not analyzer.diagnostics.has_errors(),
            "syntaxErrors": syntax_errors,
            "diagnostics": diagnostics,
        }

    if action == "compiscriptTAC":
        source = _read_compiscript_source(payload)
        analyzer, syntax_errors = analyze_source(source)
        diagnostics = [_diagnostic_to_dict(d) for d in analyzer.diagnostics]
        result = {
            "ok": not syntax_errors and not analyzer.diagnostics.has_errors(),
            "syntaxErrors": syntax_errors,
            "diagnostics": diagnostics,
            "tac": [],
            "text": "",
            "symbols": analyzer.global_scope.to_dict(),
        }
        if result["ok"]:
            program = generate_tac(source, analyzer)
            result["tac"] = [instruction.to_dict() for instruction in program.instructions]
            result["text"] = program.to_text()
            analyzer.layout.apply_temps(program.temp_counts)
            result["symbols"] = analyzer.global_scope.to_dict()
            result["layout"] = analyzer.layout.to_dict()
            result["layoutText"] = analyzer.layout.to_text()
        return result

    if action == "compiscriptASM":
        source = _read_compiscript_source(payload)
        analyzer, syntax_errors = analyze_source(source)
        result = {
            "ok": not syntax_errors and not analyzer.diagnostics.has_errors(),
            "syntaxErrors": syntax_errors,
            "diagnostics": [_diagnostic_to_dict(d) for d in analyzer.diagnostics],
            "asm": "",
        }
        if result["ok"]:
            result.update(_assemble_and_run(source, analyzer, payload))
        return result

    if action == "compiscriptSymbols":
        source = _read_compiscript_source(payload)
        analyzer, syntax_errors = analyze_source(source)

        return {
            "syntaxErrors": syntax_errors,
            "scope": analyzer.global_scope.to_dict(),
            "layout": analyzer.layout.to_dict(),
        }

    if action == "compiscriptTree":
        source = _read_compiscript_source(payload)
        tree, rule_names, syntax_errors = _parse_compiscript_tree(source)

        return {
            "syntaxErrors": syntax_errors,
            "tree": _parse_tree_to_dict(tree, rule_names),
        }


    raise ValueError(f"Acción no soportada: {action}")


def main() -> int:
    # El IDE (Tauri) lee stdout como UTF-8. Sin esto, en Windows Python escribe con la
    # codificacion local (cp1252) y los acentos llegan corruptos.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        if not raw.strip():
            raise ValueError("Request vacío en stdin")
        result = _run_action(json.loads(raw))
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
