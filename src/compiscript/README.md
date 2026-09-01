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

- **Parte 2 (30% - Asignado a Roberto Barreda):**
  - Reglas 2.3 (Funciones, recursion, closures, aridad y retornos) y Reglas 2.6 (Arreglos, dimensiones `T[]`, `T[][]`, indices enteros y `foreach`).

- **Parte 3 (30% - Asignado a Angel Esquit):**
  - Reglas 2.5 (Clases, herencia, metodos, atributos, constructores y `this`), Reglas 2.7 (Codigo muerto e inalcanzable), e Integracion con IDE Tauri + React y Bridge.

## Estructura de Modulos

| Modulo | Contenido |
| --- | --- |
| `grammar/` | `Compiscript.g4` y el parser generado en `generated/` |
| `typesystem/types.py` | Modelado de tipos primitivos, compuestos y asignabilidad |
| `symbols/` | `symbol.py` (simbolos) y `scope.py` (arbol de ambitos) |
| `diagnostics.py` | Diagnosticos acumulativos (errores y warnings con codigos y posiciones) |
| `semantic/` | `analyzer.py` (visitor orquestador), `rules_types.py`, `rules_scope.py`, `rules_control_flow.py` |
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
