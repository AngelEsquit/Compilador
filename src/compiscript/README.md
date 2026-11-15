# Compiscript: mapa de módulos

Compilador de Compiscript sobre un parser generado con ANTLR. El uso y las pruebas están en el [README raíz](../../README.md).

| Módulo | Contenido |
| --- | --- |
| `grammar/` | `Compiscript.g4` y el parser generado en `generated/` |
| `typesystem/types.py` | Tipos, asignabilidad y jerarquía de clases |
| `symbols/` | `symbol.py` (símbolos), `scope.py` (árbol de ámbitos) y `layout.py` (registros de activación, área estática, clases) |
| `diagnostics.py` | Errores y advertencias con código y posición |
| `semantic/` | `analyzer.py` (visitor), `declarations_pass.py` y un archivo `rules_*.py` por grupo de reglas |
| `intermediate/` | `ir.py` (cuádruplas y temporales) y `generator.py` (visitor que emite el TAC) |
| `backend/` | Generación de ensamblador MIPS32 (ver abajo) |
| `run_demo.py` | Línea de comandos |

## Backend

| Archivo | Responsabilidad |
| --- | --- |
| `operands.py` | Ubica cada nombre del TAC (registro de activación o área estática) y deduce su tipo |
| `blocks.py` | Bloques básicos, variables vivas y siguiente uso |
| `registers.py` | Selección de registros con descriptores de registros y de direcciones |
| `mips.py` | Traduce cada instrucción del TAC; prólogo, epílogo y convención de llamada |
| `floats.py` | Aritmética de punto flotante y conversión de entero a `float` |
| `classes.py` | Clases, objetos y herencia |
| `exceptions.py` | `try`/`catch` y errores de ejecución |
| `runtime.py` | Rutinas MIPS de apoyo: impresión, cadenas, memoria y errores |
| `peephole.py` | Optimización por mirilla |
| `asm.py` | Líneas de ensamblador como datos (`op`, `args`) y su texto |
| `simulator.py` | Simulador de MIPS32 y árbol de activación |

Punto de entrada: `compile_to_mips(source)` en `backend/__init__.py` devuelve un `AsmResult` con el programa, la bitácora del asignador de registros y los datos de cada función.

## Regenerar el parser

```bash
pip install antlr4-tools
antlr4 -Dlanguage=Python3 -visitor -no-listener -o src/compiscript/grammar/generated src/compiscript/grammar/Compiscript.g4
```

La versión del runtime está fijada en `requirements.txt` y debe coincidir con la que generó el parser.
