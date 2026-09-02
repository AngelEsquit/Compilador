# Compiscript: Analisis Semantico

Analizador semantico para Compiscript (subconjunto de TypeScript), construido
sobre un parser generado con ANTLR. Diseno completo en
[docs/Compiscript_Diseno_Semantico.md](../../docs/Compiscript_Diseno_Semantico.md)
y distribucion de tareas en [docs/DISTRIBUCION_TAREAS.md](../../docs/DISTRIBUCION_TAREAS.md).

## Estado de Implementacion

- **Parte 1 (40% - Implementado y Validado):**
  - **Tabla de Simbolos:** Jerarquia de ambitos (`GLOBAL`, `BLOCK`, `FUNCTION`, `CLASS`, `LOOP`), insercion (`define`), recuperacion (`resolve`, `resolve_local`), actualizacion (`update`) y serializacion a JSON (`to_dict`).
  - **Sistema de Tipos:** `IntegerType`, `StringType`, `BooleanType`, `NullType`, `VoidType`, `ArrayType`, `ClassType`, `FunctionType`, `ErrorType` y compatibilidad `is_assignable`.
  - **Reglas 2.1 (Tipos):** Operaciones aritmeticas (+, -, *, /, %), logicas (&&, ||, !), relacionales (<, <=, >, >=), igualdad (==, !=), ternario (?:), asignaciones y constantes (`const`).
  - **Reglas 2.2 (Ambitos):** Variables no declaradas (`SEM-SCOPE-001`), no redeclaracion (`SEM-SCOPE-002`) y sombreado (*shadowing*) permitido.
  - **Reglas 2.4 (Control de Flujo):** Condiciones booleanas (`SEM-FLOW-001`), validacion de `break`/`continue` en bucles (`SEM-FLOW-002`) y `return` en funciones (`SEM-FLOW-003`).

- **Parte 2 (30% - Implementado y Validado, Roberto Barreda):**
  - **Pasada de Pre-declaracion:** `declarations_pass.py` registra las firmas de funciones antes de validar cuerpos, habilitando recursion directa y mutua.
  - **Reglas 2.3 (Funciones):** Nombre duplicado (`SEM-FUNC-001`), parametro duplicado (`SEM-FUNC-002`), aridad de llamadas (`SEM-FUNC-003`), tipos de argumentos (`SEM-FUNC-004`), tipo de retorno contra la firma (`SEM-FUNC-005`), invocacion de algo no invocable (`SEM-FUNC-006`) y closures por encadenamiento lexico de ambitos.
  - **Reglas 2.6 (Arreglos):** Indice entero (`SEM-ARR-001`), homogeneidad de literales (`SEM-ARR-002`), `foreach` solo sobre arreglos (`SEM-ARR-003`) e indexacion solo sobre arreglos (`SEM-ARR-004`), con soporte de dimensiones `T[]` y `T[][]`.

- **Parte 3 (30% - Asignado a Angel Esquit):**
  - Reglas 2.5 (Clases, herencia, metodos, atributos, constructores y `this`), Reglas 2.7 (Codigo muerto e inalcanzable), e Integracion con IDE Tauri + React y Bridge.

## Estructura de Modulos

| Modulo | Contenido |
| --- | --- |
| `grammar/` | `Compiscript.g4` y el parser generado en `generated/` |
| `typesystem/types.py` | Modelado de tipos primitivos, compuestos y asignabilidad |
| `symbols/` | `symbol.py` (simbolos) y `scope.py` (arbol de ambitos) |
| `diagnostics.py` | Diagnosticos acumulativos (errores y warnings con codigos y posiciones) |
| `semantic/` | `analyzer.py` (visitor orquestador), `declarations_pass.py` (pasada 1), `type_resolution.py`, `rules_types.py`, `rules_scope.py`, `rules_control_flow.py`, `rules_functions.py`, `rules_arrays.py` |
| `run_demo.py` | CLI para analizar archivos `.cps` y listar diagnosticos |

## Como Correr las Pruebas

```bash
# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/compiscript/requirements.txt

# Ejecutar suite completa
.venv/bin/pytest -v

# Ejecutar solo pruebas de Compiscript
.venv/bin/pytest tests/compiscript/ -v

# Ejecutar script de pruebas del repositorio
./run_tests.sh
```

## Como Analizar un Archivo .cps

```bash
.venv/bin/python src/compiscript/run_demo.py tests/compiscript/types/valid/operaciones_aritmeticas.cps
```
