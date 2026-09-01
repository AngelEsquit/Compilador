# Distribucion de Tareas y Arquitectura del Proyecto: Compiscript

Este documento describe la arquitectura modular, la distribucion oficial de tareas entre los tres integrantes del equipo y las guias tecnicas para el desarrollo del analizador semantico e IDE de **Compiscript**.

---

## 1. Vision General del Proyecto y Ponderacion

El objetivo es construir un compilador (analizador lexico, sintactico y semantico) para **Compiscript** (un subconjunto estricto de TypeScript) con soporte de recuperacion de errores, tabla de simbolos jerarquica, inferencia de tipos y una IDE de escritorio visual e interactiva.

### Distribucion de Ponderacion (Rubrica Oficial - 24 Pts / 100%)

| Componente | Rubrica Oficial | Ponderacion |
| --- | --- | --- |
| **Tabla de Simbolos** | Insertar (2 pts), Recuperar (2 pts), Actualizar (2 pts), Manejo de Alcances (3 pts) | 9 pts (37.5%) |
| **Analizador Semantico y Tipos** | 5 reglas semanticas evaluadas al azar (3 pts c/u) | 15 pts (62.5%) |
| **IDE de Escritorio** | Interfaz grafica estetica, seleccion de archivo, visor de resultados | Requisito obligatorio (Penalizacion de hasta -15 pts si no cumple) |

---

## 2. Division del Trabajo en 3 Partes

El proyecto se divide de manera modular en 3 bloques de trabajo equilibrados e independientes:

```text
+---------------------------------------------------------------------------------------+
|                                    COMPISCRIPT                                        |
+---------------------------------------------------------------------------------------+
|  PARTE 1 (40%) - NUCLEO Y MOTOR BASE                                                  |
|  - Tabla de simbolos completa (Insertar, Recuperar, Actualizar, Alcances, JSON)       |
|  - Sistema de tipos base y unificacion (primitivos, void, null, error)                |
|  - Reglas semanticas 2.1 (Tipos en operaciones y asignaciones)                        |
|  - Reglas semanticas 2.2 (Ambitos, shadowing, no declaradas, colisiones)              |
|  - Reglas semanticas 2.4 (Control de flujo: if, while, do-while, for, break/continue)  |
|  - Suite de pruebas unitarias y de integracion automatizada                           |
+-------------------------------------------+-------------------------------------------+
|  PARTE 2 (30%) - ROBERTO BARREDA          |  PARTE 3 (30%) - ANGEL ESQUIT             |
|  - Reglas 2.3 (Funciones y Procedimientos)|  - Reglas 2.5 (Clases, Objetos y POO)     |
|    * DeclarationsPass (pre-declaracion)   |    * Herencia, metodos, atributos         |
|    * Aridad y tipos de parametros         |    * Constructor, new, this               |
|    * Retornos de funciones y recursion    |  - Reglas 2.7 (Generales)                 |
|    * Closures y funciones anidadas        |    * Codigo muerto (unreachable code)     |
|  - Reglas 2.6 (Arreglos y Listas)         |    * Expresiones invalidas                |
|    * ArrayType (T[], T[][])               |  - IDE de Escritorio (Tauri + React)      |
|    * Homogeneidad de literales            |    * Bridge JSON (bridge_compiscript.py)  |
|    * Indexacion entera (arr[i])           |    * Visor de tabla de simbolos y AST     |
|    * Bucle foreach                        |    * Panel interactivo de diagnosticos    |
|  - Bateria de pruebas .cps (2.3 y 2.6)    |  - Bateria de pruebas .cps (2.5 y 2.7)    |
+-------------------------------------------+-------------------------------------------+
```

---

## 3. Especificacion Detallada de Cada Parte

### PARTE 1: Motor Semantico Core, Tabla de Simbolos y Control de Flujo (40%)
*Estado: Implementado y verificado con 100% de tests passing.*

1. **Tabla de Simbolos Jerarquica (`src/compiscript/symbols/`):**
   - **Clase `Scope`:** Representa un entorno léxico con referencia a su `parent`.
     - `define(symbol: Symbol) -> bool`: Inserta un símbolo en el ámbito local. Rechaza duplicados en el mismo ámbito.
     - `resolve(name: str) -> Optional[Symbol]`: Búsqueda léxica hacia arriba en la cadena de ámbitos.
     - `resolve_local(name: str) -> Optional[Symbol]`: Búsqueda exclusiva en el ámbito actual.
     - `update(name: str, **kwargs) -> bool`: Actualiza metadatos del símbolo (por ejemplo, marcar `initialized = True`).
     - `child(kind: ScopeKind, name: str = "") -> Scope`: Genera un nuevo entorno hijo (`GLOBAL`, `BLOCK`, `FUNCTION`, `CLASS`, `LOOP`).
     - `to_dict() -> dict`: Serializa la estructura completa de ámbitos y símbolos a formato JSON para integración con el IDE y fases futuras.
   - **Clases de Simbolos (`symbol.py`):** `Symbol`, `VariableSymbol`, `ConstSymbol`, `ParameterSymbol`, `FunctionSymbol`, `ClassSymbol`.

2. **Sistema de Tipos (`src/compiscript/typesystem/`):**
   - Jerarquía de tipos: `IntegerType`, `StringType`, `BooleanType`, `NullType`, `VoidType`, `ArrayType`, `ClassType`, `FunctionType`, `ErrorType`.
   - Función `is_assignable(source: Type, target: Type) -> bool`: Valida compatibilidad y asignabilidad.
   - Manejo de `ErrorType`: Actúa como comodín de recuperación para evitar emisión de errores en cascada.

3. **Reglas Semanticas Core (`src/compiscript/semantic/`):**
   - `rules_types.py`:
     - Operaciones aritméticas (`+`, `-`, `*`, `/`, `%`): operandos deben ser enteros (`integer`). El operador `+` también permite concatenación de cadenas (`string + string`).
     - Operaciones lógicas (`&&`, `||`, `!`): operandos booleanos (`boolean`).
     - Comparaciones relacionales (`<`, `<=`, `>`, `>=`): operandos de tipo `integer`.
     - Comparaciones de igualdad (`==`, `!=`): operandos del mismo tipo o comparación con `null`.
     - Expresión condicional ternaria (`cond ? a : b`): condición `boolean`, unificación de ramas.
     - Asignación: compatibilidad de tipo del valor con la variable de destino.
     - Constantes: inicialización obligatoria y prohibición de reasignación a `const`.
   - `rules_scope.py`:
     - Identificador no declarado (`SEM-SCOPE-001`).
     - Redeclaración en el mismo ámbito (`SEM-SCOPE-002`).
     - Permitir sombreado (*shadowing*) de variables en ámbitos hijos.
   - `rules_control_flow.py`:
     - Expresión de condición en `if`, `while`, `do-while`, `for`, `switch` debe ser `boolean` (`SEM-FLOW-001`).
     - Sentencias `break` y `continue` solo permitidas dentro de bucles (`SEM-FLOW-002`).
     - Sentencia `return` solo permitida dentro de funciones (`SEM-FLOW-003`).

---

### PARTE 2: Funciones, Procedimientos, Closures y Arreglos (30%)
*Asignado a: **Roberto Barreda***

#### Responsabilidades:
1. **Reglas 2.3: Funciones y Procedimientos (`src/compiscript/semantic/rules_functions.py`):**
   - **Pasada de Pre-declaracion (`declarations_pass.py`):**
     - Recorrer el árbol antes de la pasada de tipos para registrar firmas de funciones (`FunctionSymbol`) y clases. Esto permite que una función pueda llamar a otra que se defina más abajo en el archivo y soporte recursión directa y mutua.
   - **Validacion de Llamadas (`CallExpr`):**
     - Verificar que el identificador llamado sea una función o método.
     - Validar que el número de argumentos coincida con el número de parámetros (aridad posicional).
     - Validar que el tipo de cada argumento sea asignable al tipo del parámetro correspondiente (`is_assignable`).
   - **Validacion de Retornos (`ReturnStatement`):**
     - Verificar que el tipo devuelto por `return expr;` sea asignable al tipo de retorno declarado en la firma de la función.
     - En funciones sin tipo declarado o tipo `void`, el `return;` debe ser vacío (sin valor).
   - **Funciones Anidadas y Closures:**
     - Permitir funciones dentro de funciones. La función interna abre su propio ámbito `FUNCTION` cuyo `parent` es el ámbito de la función externa, capturando variables léxicas transparentemente.
   - **Duplicados:**
     - Prohibir múltiples funciones con el mismo nombre en el mismo ámbito (`SEM-FUNC-001`).
     - Prohibir parámetros con nombres duplicados en la firma (`SEM-FUNC-002`).

2. **Reglas 2.6: Arreglos y Listas (`src/compiscript/semantic/rules_arrays.py`):**
   - **Literales de Arreglo (`[e1, e2, ...]`):**
     - Validar que todos los elementos sean del mismo tipo (homogéneos). Si están vacíos `[]`, inferir tipo base comodín o según la anotación.
     - Retornar `ArrayType(element_type, dimensions)`.
   - **Acceso a Arreglos (`arr[index]`):**
     - Verificar que la expresión que se indexa sea de tipo `ArrayType`.
     - Validar que la expresión de índice `index` sea de tipo `integer` (`SEM-ARR-001`).
     - El tipo resultante de la indexación es el tipo base del arreglo reducido en 1 dimensión.
   - **Iteracion Foreach (`foreach (item in collection)`):**
     - Validar que `collection` sea de tipo `ArrayType`.
     - Declarar la variable `item` en el ámbito del bucle con el tipo de los elementos del arreglo.

3. **Bateria de Pruebas (.cps y pytest):**
   - Crear casos de prueba en `tests/compiscript/functions/` (válidos e inválidos).
   - Crear casos de prueba en `tests/compiscript/arrays/` (válidos e inválidos).
   - Añadir tests a `tests/compiscript/test_semantic_rules.py`.

---

### PARTE 3: Programacion Orientada a Objetos, Reglas Generales e IDE (30%)
*Asignado a: **Angel Esquit***

#### Responsabilidades:
1. **Reglas 2.5: Clases y Objetos (`src/compiscript/semantic/rules_classes.py`):**
   - **Declaracion de Clases y Miembros:**
     - Registrar `ClassSymbol` con sus campos (`VariableSymbol`) y métodos (`FunctionSymbol`).
     - Crear un ámbito `CLASS` para el cuerpo de la clase.
   - **Herencia (`class B : A`):**
     - Validar que la superclase `A` exista y esté declarada.
     - Evitar ciclos de herencia (por ejemplo, `A : B` y `B : A`).
     - En `resolve_member()`, buscar primero en los miembros de la clase actual y, si no se encuentra, buscar recursivamente en la superclase.
   - **Acceso a Miembros (`obj.prop`, `obj.metodo()`):**
     - Validar que `obj` sea de tipo `ClassType`.
     - Validar que la propiedad o método exista en la clase o en su jerarquía (`SEM-CLASS-001`).
   - **Instanciacion (`new ClassName(args)`):**
     - Validar que la clase exista.
     - Si la clase define un método `constructor`, validar que los argumentos coincidan en aridad y tipos.
   - **Manejo de `this` (`ThisExpr`):**
     - Validar que `this` solo se use dentro del cuerpo de métodos de una clase (`SEM-CLASS-002`).
     - El tipo de `this` es el `ClassType` de la clase contenedora.
   - **Asignacion a Propiedades (`obj.prop = val`):**
     - Validar que `prop` exista y no sea de solo lectura.
     - Validar compatibilidad de tipo (`is_assignable(val_type, prop_type)`).

2. **Reglas 2.7: Reglas Generales y Codigo Muerto (`src/compiscript/semantic/rules_general.py`):**
   - **Deteccion de Codigo Muerto (`SEM-GEN-001` - Warning/Error):**
     - Detectar sentencias inalcanzables que aparezcan inmediatamente después de un `return`, `break` o `continue` incondicional en el mismo bloque.
   - **Expresiones sin Sentido Semantico (`SEM-GEN-002`):**
     - Detectar operaciones inválidas como intentar operar aritméticamente con funciones o clases.

3. **Integracion con la IDE de Escritorio (Tauri + React + Monaco Editor):**
   - **Bridge JSON (`src/compiscript/bridge_compiscript.py` o en `src/bridge_cli.py`):**
     - Implementar las acciones JSON:
       - `compiscriptCheck`: Ejecuta el análisis léxico, sintáctico y semántico sobre el código `.cps` recibido o ruta de archivo, devolviendo la lista de diagnósticos (`Diagnostic`).
       - `compiscriptSymbols`: Devuelve el árbol serializado de la tabla de símbolos (`Scope.to_dict()`).
       - `compiscriptTree`: Devuelve el árbol sintáctico (AST / Parse Tree) serializado en formato nodo/hijos para representación gráfica en el visualizador.
   - **Frontend React (`src/desktop-app/`):**
     - Agregar el tab/panel para archivos Compiscript (`.cps`).
     - Visualizador interactivo de la Tabla de Símbolos (árbol de scopes con variables, tipos, constantes, funciones y clases).
     - Panel de diagnósticos con subrayado y salto directo a la línea/columna en Monaco Editor al hacer click en el error.
     - Visor visual del árbol sintáctico (usando el renderizador de grafos SVG existente).

4. **Bateria de Pruebas (.cps y pytest):**
   - Crear casos de prueba en `tests/compiscript/classes/` (válidos e inválidos).
   - Crear casos de prueba en `tests/compiscript/general/` (válidos e inválidos).
   - Casos de prueba end-to-end con el bridge (`tests/compiscript/test_bridge.py`).

---

## 4. Convenciones de Codigos de Diagnostico

Para mantener consistencia en la batería de pruebas y la interfaz visual, se utiliza el siguiente estándar de códigos:

| Prefijo | Categoria | Ejemplos de Codigo |
| --- | --- | --- |
| `SEM-TYPE-` | Errores de Tipos | `SEM-TYPE-001` (Operando aritmetico no entero), `SEM-TYPE-002` (Operando logico no booleano), `SEM-TYPE-003` (Asignacion incompatible), `SEM-TYPE-004` (Comparacion incompatible), `SEM-TYPE-005` (Constante no inicializada), `SEM-TYPE-006` (Reasignacion a constante) |
| `SEM-SCOPE-` | Errores de Ambito | `SEM-SCOPE-001` (Variable no declarada), `SEM-SCOPE-002` (Redeclaracion en mismo ambito) |
| `SEM-FLOW-` | Errores de Control de Flujo | `SEM-FLOW-001` (Condicion no booleana), `SEM-FLOW-002` (break/continue fuera de bucle), `SEM-FLOW-003` (return fuera de funcion) |
| `SEM-FUNC-` | Errores de Funciones | `SEM-FUNC-001` (Funcion duplicada), `SEM-FUNC-002` (Parametro duplicado), `SEM-FUNC-003` (Aridad incorrecta), `SEM-FUNC-004` (Tipo de argumento incompatible), `SEM-FUNC-005` (Tipo de retorno incompatible) |
| `SEM-ARR-` | Errores de Arreglos | `SEM-ARR-001` (Indice no entero), `SEM-ARR-002` (Arreglo con elementos heterogeneos), `SEM-ARR-003` (Iteracion foreach sobre no arreglo) |
| `SEM-CLASS-` | Errores de Clases | `SEM-CLASS-001` (Propiedad o metodo inexistente), `SEM-CLASS-002` (this fuera de clase), `SEM-CLASS-003` (Superclase no encontrada), `SEM-CLASS-004` (Constructor incorrecto) |
| `SEM-GEN-` | Errores Generales | `SEM-GEN-001` (Codigo inalcanzable/muerto), `SEM-GEN-002` (Expresion sin sentido semantico) |

---

## 5. Como Ejecutar y Probar el Proyecto

### Requisitos Previos:
```bash
python3 -m venv .venv
source .venv/bin/activate  # En Linux/Mac
# o en Windows: .venv\Scripts\activate
pip install -r src/compiscript/requirements.txt
```

### Ejecutar las Pruebas Automatizadas:
```bash
# Correr toda la suite de pruebas
.venv/bin/pytest -v

# Correr solo las pruebas de Compiscript
.venv/bin/pytest tests/compiscript/ -v

# Correr el verificador de estilo del repositorio (sin emojis ni guiones largos)
.venv/bin/pytest tests/test_repo_style.py
```

### Ejecutar el Analizador sobre un archivo Compiscript:
```bash
.venv/bin/python src/compiscript/run_demo.py tests/compiscript/samples/animals.cps
```

### Ejecutar la IDE de Escritorio:
```bash
cd src/desktop-app
npm install
npm run tauri:nowatch
```
