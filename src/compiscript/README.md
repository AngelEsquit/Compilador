# Compiscript — walking skeleton (fase de análisis semántico)

Primera implementación descrita en la sección 0 de
`docs/Compiscript_Diseno_Semantico.md`: un corte mínimo de punta a
punta (parser ANTLR → analizador semántico → tabla de símbolos →
diagnósticos), con solo dos reglas implementadas, para validar que el
diseño de `Scope`/`Type` funciona antes de construir las ~23 reglas
restantes.

## Qué incluye

- `grammar/Compiscript.g4` — copia de `docs/Compiscript.g4`.
- `grammar/generated/` — código generado por ANTLR (**no editar a
  mano**, se regenera con el comando de abajo).
- `typesystem/types.py` — `IntegerType`, `StringType`, `BooleanType`,
  `ErrorType` (todavía sin `ArrayType`/`ClassType`/`FunctionType`).
- `symbols/scope.py`, `symbols/symbol.py` — tabla de símbolos como
  árbol de ámbitos (`GLOBAL`/`BLOCK` por ahora).
- `diagnostics.py` — lista acumulativa de errores/warnings.
- `semantic/analyzer.py` — el `SemanticAnalyzer` (ANTLR Visitor) con
  dos reglas: `SEM-SCOPE-001` (variable no declarada) y
  `SEM-SCOPE-002` (redeclaración en el mismo ámbito).
- `run_demo.py` — corre el analizador sobre un `.cps` y muestra los
  diagnósticos por consola.

Los tests viven en `tests/compiscript/` (fuera de `src/`, como el
resto del proyecto): `test_scope_unit.py` y `test_types_unit.py` son
unitarios (sin pasar por el parser); `test_walking_skeleton.py` es
end-to-end.

**Importante — por qué el paquete se llama `typesystem/` y no
`types/`:** Python trae un módulo `types` en su librería estándar. Si
esta carpeta se llamara `types/`, al ejecutar un script directamente
desde dentro de `src/compiscript/` (por ejemplo `python3
run_demo.py ...` parado en esa carpeta) Python agrega esa carpeta a
`sys.path` y nuestro paquete `types/` tapa al de la librería
estándar, rompiendo imports internos de Python (pasó durante el
desarrollo de este walking skeleton). No renombrar de vuelta a `types/`.

## Cómo regenerar el parser

```bash
pip install antlr4-tools
cd src/compiscript/grammar
antlr4 -Dlanguage=Python3 -visitor -no-listener -o generated Compiscript.g4
```

**Sobre versiones:** el código en `generated/` de este primer commit
se generó con ANTLR **4.11.1** (fue la versión disponible en el
entorno donde se armó este walking skeleton; `antlr4-tools` por
defecto baja la última versión estable, hoy 4.13.x). El runtime de
Python tiene que coincidir exactamente con la versión del `.jar` que
generó el código, si no truena con un error de "ANTLR runtime and
generated code versions disagree". Dos caminos:

1. Instalar el runtime pineado a 4.11.1 (`pip install
   antlr4-python3-runtime==4.11.1`) y dejar `generated/` como está.
2. O regenerar `generated/` con lo que baje `antlr4-tools` en tu
   máquina (probablemente 4.13.x) e instalar
   `antlr4-python3-runtime` en esa misma versión. Este es el camino
   recomendado para que el equipo trabaje con una versión moderna;
   el primero es solo para no bloquearse si alguien no tiene
   conexión a Maven Central en el momento.

`requirements.txt` en esta carpeta documenta la versión que se usó
para este commit — actualízalo si regeneran con otra.

## Cómo correr

```bash
# Desde la raíz del repo, con PYTHONPATH apuntando a src/:
PYTHONPATH=src python3 -m pytest tests/compiscript/ -v

# Probar un archivo suelto:
python3 src/compiscript/run_demo.py tests/compiscript/scope/invalid/redeclaracion.cps
```

## Qué NO hace todavía (a propósito)

Funciones, clases, `foreach`/`this`/parámetros, arreglos, control de
flujo y las reglas "generales" quedan fuera de este primer corte (ver
sección 0 del documento de diseño). `tests/compiscript/samples/animals.cps`
ya ejercita esas construcciones y **parsea sintácticamente**, pero el
analizador semántico actual va a marcar `SEM-SCOPE-001` sobre
parámetros de función, la variable de `foreach`, etc. — es esperado;
ese archivo se reutiliza como caso de integración cuando existan
`rules_functions.py`, `rules_classes.py`, etc.

## Hallazgo durante la construcción de este skeleton

La gramática exige llaves en el cuerpo de `if`/`while`/`foreach`
(`ifStatement: 'if' '(' expression ')' block ...`, y `block` requiere
`{ }`). Los ejemplos de `docs/Compiscript.md` (p. ej. `if (n <= 1)
return 1;` en el factorial recursivo) están escritos **sin** llaves y
no parsean tal cual con `Compiscript.g4`. `tests/compiscript/samples/animals.cps`
ya usa la forma con llaves. Si el equipo prefiere permitir la forma
sin llaves, hay que ajustar la gramática (`ifStatement`/`whileStatement`/
`foreachStatement` aceptando `statement` además de `block`), y eso es
una decisión a tomar en equipo, no algo que yo haya resuelto acá.
