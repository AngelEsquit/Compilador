# Compiscript: análisis semántico

Analizador semántico para Compiscript (subconjunto de TypeScript), construido
sobre un parser generado con ANTLR. Diseño completo en
[docs/Compiscript_Diseno_Semantico.md](../../docs/Compiscript_Diseno_Semantico.md).

## Estado

Walking skeleton: el pipeline funciona de punta a punta con dos reglas.

| Módulo | Contenido |
|---|---|
| `grammar/` | `Compiscript.g4` y el parser generado en `generated/` (no editar a mano) |
| `typesystem/types.py` | `IntegerType`, `StringType`, `BooleanType`, `ErrorType` |
| `symbols/` | Tabla de símbolos como árbol de ámbitos (`GLOBAL` y `BLOCK`) |
| `diagnostics.py` | Lista acumulativa de errores y warnings |
| `semantic/analyzer.py` | Visitor con `SEM-SCOPE-001` (variable no declarada) y `SEM-SCOPE-002` (redeclaración) |
| `run_demo.py` | CLI que analiza un `.cps` y lista los diagnósticos |

Pendiente: tipos compuestos, funciones, clases, control de flujo, arreglos,
reglas generales, serialización de la tabla de símbolos y la integración con el IDE.

## Cómo correr

```bash
pip install -r src/compiscript/requirements.txt

# Suite de tests (desde la raiz del repo)
python -m pytest tests/compiscript/ -v

# Un archivo suelto
python src/compiscript/run_demo.py tests/compiscript/scope/invalid/redeclaracion.cps
```

## Cómo regenerar el parser

```bash
pip install antlr4-tools
cd src/compiscript/grammar
antlr4 -Dlanguage=Python3 -visitor -no-listener -o generated Compiscript.g4
```

El runtime de Python debe coincidir exactamente con la versión del `.jar` que
generó el código, o falla con "ANTLR runtime and generated code versions
disagree". `generated/` está hecho con ANTLR 4.11.1, la versión que fija
`requirements.txt`. Si regeneras con otra, actualiza ese pin.

## Por qué el paquete se llama `typesystem/` y no `types/`

Python trae un módulo `types` en su librería estándar. Si esta carpeta se
llamara `types/`, ejecutar un script parado dentro de `src/compiscript/` agrega
esa carpeta al `sys.path` y nuestro paquete tapa al de la librería estándar,
rompiendo imports internos de Python. No renombrar de vuelta a `types/`.

## Decisiones de diseño cerradas

- Solo `integer` como tipo numérico. La gramática no define `float`.
- Llaves obligatorias en `if`, `while` y `foreach`. La gramática exige `block`,
  así que los ejemplos sin llaves de [docs/Compiscript.md](../../docs/Compiscript.md)
  no parsean tal cual; `tests/compiscript/samples/animals.cps` usa la forma con llaves.
- `switch` sin fallthrough implícito.
- Sin sobrecarga de funciones: todo nombre duplicado en el mismo ámbito es error.
- Shadowing permitido entre ámbitos distintos.
