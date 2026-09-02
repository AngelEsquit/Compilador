# Distribucion de Tareas y Arquitectura del Proyecto: Compiscript

Este documento describe la arquitectura modular, la distribucion oficial de tareas entre los tres integrantes del equipo y las guias tecnicas para el desarrollo del analizador semantico e IDE de **Compiscript**, siguiendo estrictamente los fundamentos teoricos y pautas de las presentaciones de clase.

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

## 2. Pautas y Fundamentos de las Presentaciones de Clase (`docs/presentaciones/`)

Todo el desarrollo debe alinearse con las lecciones y presentaciones de la materia:

### A. Tabla de Simbolos (Presentacion 02: `02 - Tabla de simbolos v 1.11.pptx`)
- **Atributos por Simbolo:** Lexema/nombre, tipo semantico, alcance (scope), posicion (linea y columna), inicializacion y constancia (`is_const`), parametros (en funciones) y miembros (en clases).
- **Operaciones Fundamentales:**
  - `define(symbol)` (Insertar): Agrega el simbolo al ambito local y rechaza colisiones en el mismo nivel.
  - `resolve(name)` (Recuperar): Sube por la jerarquia de ambitos hasta encontrar la declaracion.
  - `update(name, **kwargs)` (Actualizar): Modifica metadatos de un simbolo declarado.
- **Arbol de Ambitos (Scopes):** Cada bloque `{ ... }`, funcion, clase o bucle abre un entorno hijo. Se respeta el sombreado (*shadowing*).

### B. Analisis Semantico y Sistema de Tipos (Presentacion 03: `03 - Analisis semantico v 1.1.pptx`)
- **Formalismo de Deduccion:** `Gamma |- expresion : Tipo`, donde `Gamma` es el entorno/tabla de simbolos actual.
- **Chequeo no destructivo:** Ante un error de tipos, se registra el diagnostico y se propaga `ErrorType` (tipo comodin) para continuar el analisis sin causar errores en cascada.

### C. Traduccion Orientada por la Sintaxis (Presentaciones 04 y 05)
- **Atributos Sintetizados:** Calculo bottom-up de tipos en expresiones mediante el retorno de los metodos `visit*` en el Visitor.
- **Atributos Heredados:** Paso top-down de contextos (scope activo, contexto de bucle para `break`/`continue`, contexto de funcion para `return`).
- **Estructura de Tipos Compuestos:** Modelado explicito de `ArrayType(elem_type, dimensions)` y `ClassType(name)`.

---

## 3. Division del Trabajo en 3 Partes

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

## 4. Especificacion Detallada de Cada Parte

### PARTE 1: Motor Semantico Core, Tabla de Simbolos y Control de Flujo (40%)
*Estado: Implementado y verificado con 100% de tests passing.*

1. **Tabla de Simbolos Jerarquica (`src/compiscript/symbols/`):**
   - **Clase `Scope`:** Representa un entorno lexico con referencia a su `parent`.
     - `define(symbol: Symbol) -> bool`: Inserta un simbolo en el ambito local. Rechaza duplicados en el mismo ambito.
     - `resolve(name: str) -> Optional[Symbol]`: Busqueda lexica hacia arriba en la cadena de ambitos.
     - `resolve_local(name: str) -> Optional[Symbol]`: Busqueda exclusiva en el ambito actual.
     - `update(name: str, **kwargs) -> bool`: Actualiza metadatos del simbolo (por ejemplo, marcar `initialized = True`).
     - `child(kind: ScopeKind, name: str = "") -> Scope`: Genera un nuevo entorno hijo (`GLOBAL`, `BLOCK`, `FUNCTION`, `CLASS`, `LOOP`).
     - `to_dict() -> dict`: Serializa la estructura completa de ambitos y simbolos a formato JSON para integracion con el IDE y fases futuras.
   - **Clases de Simbolos (`symbol.py`):** `Symbol`, `VariableSymbol`, `ConstSymbol`, `ParameterSymbol`, `FunctionSymbol`, `ClassSymbol`.

2. **Sistema de Tipos (`src/compiscript/typesystem/`):**
   - Jerarquia de tipos: `IntegerType`, `StringType`, `BooleanType`, `NullType`, `VoidType`, `ArrayType`, `ClassType`, `FunctionType`, `ErrorType`.
   - Funcion `is_assignable(source: Type, target: Type) -> bool`: Valida compatibilidad y asignabilidad.
   - Manejo de `ErrorType`: Actua como comodin de recuperacion para evitar emision de errores en cascada.

3. **Reglas Semanticas Core (`src/compiscript/semantic/`):**
   - `rules_types.py`:
     - Operaciones aritmeticas (`+`, `-`, `*`, `/`, `%`): operandos deben ser enteros (`integer`). El operador `+` tambien permite concatenacion de cadenas (`string + string`).
     - Operaciones logicas (`&&`, `||`, `!`): operandos booleanos (`boolean`).
     - Comparaciones relacionales (`<`, `<=`, `>`, `>=`): operandos de tipo `integer`.
     - Comparaciones de igualdad (`==`, `!=`): operandos del mismo tipo o comparacion con `null`.
     - Expresion condicional ternaria (`cond ? a : b`): condicion `boolean`, unificacion de ramas.
     - Asignacion: compatibilidad de tipo del valor con la variable de destino.
     - Constantes: inicializacion obligatoria y prohibicion de reasignacion a `const`.
   - `rules_scope.py`:
     - Identificador no declarado (`SEM-SCOPE-001`).
     - Redeclaracion en el mismo ambito (`SEM-SCOPE-002`).
     - Permitir sombreado (*shadowing*) de variables en ambitos hijos.
   - `rules_control_flow.py`:
     - Expresion de condicion en `if`, `while`, `do-while`, `for`, `switch` debe ser `boolean` (`SEM-FLOW-001`).
     - Sentencias `break` y `continue` solo permitidas dentro de bucles (`SEM-FLOW-002`).
     - Sentencia `return` solo permitida dentro de funciones (`SEM-FLOW-003`).

---

### PARTE 2: Funciones, Procedimientos, Closures y Arreglos (30%)
*Asignado a: **Roberto Barreda***
*Estado: Implementado y verificado. Ver `tests/compiscript/functions/` y `tests/compiscript/arrays/`.*

#### Responsabilidades:
1. **Reglas 2.3: Funciones y Procedimientos (`src/compiscript/semantic/rules_functions.py`):**
   - **Pasada de Pre-declaracion (`declarations_pass.py`):**
     - Recorrer el arbol antes de la pasada de tipos para registrar firmas de funciones (`FunctionSymbol`) y clases. Esto permite que una funcion pueda llamar a otra que se defina mas abajo en el archivo y soporte recursion directa y mutua.
   - **Validacion de Llamadas (`CallExpr`):**
     - Verificar que el identificador llamado sea una funcion o metodo.
     - Validar que el numero de argumentos coincida con el numero de parametros (aridad posicional).
     - Validar que el tipo de cada argumento sea asignable al tipo del parametro correspondiente (`is_assignable`).
   - **Validacion de Retornos (`ReturnStatement`):**
     - Verificar que el tipo devuelto por `return expr;` sea asignable al tipo de retorno declarado en la firma de la funcion.
     - En funciones sin tipo declarado o tipo `void`, el `return;` debe ser vacio (sin valor).
   - **Funciones Anidadas y Closures:**
     - Permitir funciones dentro de funciones. La funcion interna abre su propio ambito `FUNCTION` cuyo `parent` es el ambito de la funcion externa, capturando variables lexicas transparentemente.
   - **Duplicados:**
     - Prohibir multiples funciones con el mismo nombre en el mismo ambito (`SEM-FUNC-001`).
     - Prohibir parametros con nombres duplicados en la firma (`SEM-FUNC-002`).

2. **Reglas 2.6: Arreglos y Listas (`src/compiscript/semantic/rules_arrays.py`):**
   - **Literales de Arreglo (`[e1, e2, ...]`):**
     - Validar que todos los elementos sean del mismo tipo (homogeneos). Si estan vacios `[]`, inferir tipo base comodin o segun la anotacion.
     - Retornar `ArrayType(element_type, dimensions)`.
   - **Acceso a Arreglos (`arr[index]`):**
     - Verificar que la expresion que se indexa sea de tipo `ArrayType`.
     - Validar que la expresion de indice `index` sea de tipo `integer` (`SEM-ARR-001`).
     - El tipo resultante de la indexacion es el tipo base del arreglo reducido en 1 dimension.
   - **Iteracion Foreach (`foreach (item in collection)`):**
     - Validar que `collection` sea de tipo `ArrayType`.
     - Declarar la variable `item` en el ambito del bucle con el tipo de los elementos del arreglo.

3. **Bateria de Pruebas (.cps y pytest):**
   - Crear casos de prueba en `tests/compiscript/functions/` (validos e invalidos).
   - Crear casos de prueba en `tests/compiscript/arrays/` (validos e invalidos).
   - Anadir tests a `tests/compiscript/test_semantic_rules.py`.

---

### PARTE 3: Programacion Orientada a Objetos, Reglas Generales e IDE (30%)
*Asignado a: **Angel Esquit***

#### Responsabilidades:
1. **Reglas 2.5: Clases y Objetos (`src/compiscript/semantic/rules_classes.py`):**
   - **Declaracion de Clases y Miembros:**
     - Registrar `ClassSymbol` con sus campos (`VariableSymbol`) y metodos (`FunctionSymbol`).
     - Crear un ambito `CLASS` para el cuerpo de la clase.
   - **Herencia (`class B : A`):**
     - Validar que la superclase `A` exista y este declarada.
     - Evitar ciclos de herencia (por ejemplo, `A : B` y `B : A`).
     - En `resolve_member()`, buscar primero en los miembros de la clase actual y, si no se encuentra, buscar recursivamente en la superclase.
   - **Acceso a Miembros (`obj.prop`, `obj.metodo()`):**
     - Validar que `obj` sea de tipo `ClassType`.
     - Validar que la propiedad o metodo exista en la clase o en su jerarquia (`SEM-CLASS-001`).
   - **Instanciacion (`new ClassName(args)`):**
     - Validar que la clase exista.
     - Si la clase define un metodo `constructor`, validar que los argumentos coincidan en aridad y tipos.
   - **Manejo de `this` (`ThisExpr`):**
     - Validar que `this` solo se use dentro del cuerpo de metodos de una clase (`SEM-CLASS-002`).
     - El tipo de `this` es el `ClassType` de la clase contenedora.
   - **Asignacion a Propiedades (`obj.prop = val`):**
     - Validar que `prop` exista y no sea de solo lectura.
     - Validar compatibilidad de tipo (`is_assignable(val_type, prop_type)`).

2. **Reglas 2.7: Reglas Generales y Codigo Muerto (`src/compiscript/semantic/rules_general.py`):**
   - **Deteccion de Codigo Muerto (`SEM-GEN-001` - Warning/Error):**
     - Detectar sentencias inalcanzables que aparezcan inmediatamente despues de un `return`, `break` o `continue` incondicional en el mismo bloque.
   - **Expresiones sin Sentido Semantico (`SEM-GEN-002`):**
     - Detectar operaciones invalidas como intentar operar aritmeticamente con funciones o clases.

3. **Integracion con la IDE de Escritorio (Tauri + React + Monaco Editor):**
   - **Bridge JSON (`src/compiscript/bridge_compiscript.py` o en `src/bridge_cli.py`):**
     - Implementar las acciones JSON:
       - `compiscriptCheck`: Ejecuta el analisis lexico, sintactico y semantico sobre el codigo `.cps` recibido o ruta de archivo, devolviendo la lista de diagnosticos (`Diagnostic`).
       - `compiscriptSymbols`: Devuelve el arbol serializado de la tabla de simbolos (`Scope.to_dict()`).
       - `compiscriptTree`: Devuelve el arbol sintactico (AST / Parse Tree) serializado en formato nodo/hijos para representacion grafica en el visualizador.
   - **Frontend React (`src/desktop-app/`):**
     - Agregar el tab/panel para archivos Compiscript (`.cps`).
     - Visualizador interactivo de la Tabla de Simbolos (arbol de scopes con variables, tipos, constantes, funciones y clases).
     - Panel de diagnosticos con subrayado y salto directo a la linea/columna en Monaco Editor al hacer click en el error.
     - Visor visual del arbol sintactico (usando el renderizador de grafos SVG existente).

4. **Bateria de Pruebas (.cps y pytest):**
   - Crear casos de prueba en `tests/compiscript/classes/` (validos e invalidos).
   - Crear casos de prueba en `tests/compiscript/general/` (validos e invalidos).
   - Casos de prueba end-to-end con el bridge (`tests/compiscript/test_bridge.py`).

---

## 5. Convenciones de Codigos de Diagnostico

Para mantener consistencia en la bateria de pruebas y la interfaz visual, se utiliza el siguiente estandar de codigos:

| Prefijo | Categoria | Ejemplos de Codigo |
| --- | --- | --- |
| `SEM-TYPE-` | Errores de Tipos | `SEM-TYPE-001` (Operando aritmetico no entero), `SEM-TYPE-002` (Operando logico no booleano), `SEM-TYPE-003` (Asignacion incompatible), `SEM-TYPE-004` (Comparacion incompatible), `SEM-TYPE-005` (Constante no inicializada), `SEM-TYPE-006` (Reasignacion a constante) |
| `SEM-SCOPE-` | Errores de Ambito | `SEM-SCOPE-001` (Variable no declarada), `SEM-SCOPE-002` (Redeclaracion en mismo ambito) |
| `SEM-FLOW-` | Errores de Control de Flujo | `SEM-FLOW-001` (Condicion no booleana), `SEM-FLOW-002` (break/continue fuera de bucle), `SEM-FLOW-003` (return fuera de funcion) |
| `SEM-FUNC-` | Errores de Funciones | `SEM-FUNC-001` (Funcion duplicada), `SEM-FUNC-002` (Parametro duplicado), `SEM-FUNC-003` (Aridad incorrecta), `SEM-FUNC-004` (Tipo de argumento incompatible), `SEM-FUNC-005` (Tipo de retorno incompatible), `SEM-FUNC-006` (Expresion no invocable) |
| `SEM-ARR-` | Errores de Arreglos | `SEM-ARR-001` (Indice no entero), `SEM-ARR-002` (Arreglo con elementos heterogeneos), `SEM-ARR-003` (Iteracion foreach sobre no arreglo), `SEM-ARR-004` (Indexacion sobre algo que no es arreglo) |
| `SEM-CLASS-` | Errores de Clases | `SEM-CLASS-001` (Propiedad o metodo inexistente), `SEM-CLASS-002` (this fuera de clase), `SEM-CLASS-003` (Superclase no encontrada), `SEM-CLASS-004` (Constructor incorrecto) |
| `SEM-GEN-` | Errores Generales | `SEM-GEN-001` (Codigo inalcanzable/muerto), `SEM-GEN-002` (Expresion sin sentido semantico) |

---

## 6. Como Ejecutar y Probar el Proyecto

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
