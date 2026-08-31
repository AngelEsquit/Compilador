# Compiscript — Fase de Análisis Semántico
### Documento de diseño de arquitectura

## 0. Primera implementación (walking skeleton)

Antes de repartir el trabajo por categorías de reglas, conviene construir primero un "walking skeleton": la porción más chica posible que atraviese *todas* las capas del pipeline (parser → visitor → tabla de símbolos → diagnóstico), en vez de construir una capa completa a la vez. El riesgo más grande al inicio no es "¿sabemos escribir las ~25 reglas semánticas?" sino "¿el diseño de `Scope`/`Type` propuesto en las secciones 4 y 5 realmente funciona conectado a un parser de verdad?" — y eso solo se descubre integrando de punta a punta, aunque sea con una sola regla.

Orden recomendado para este primer corte:

1. **Generar el parser y verificarlo** (prerrequisito, no es diseño): `antlr4-tools` sobre `Compiscript.g4`, correrlo contra 2-3 ejemplos de `Compiscript.md` y confirmar que no hay errores de sintaxis.
2. **`symbols/scope.py` en su versión mínima**: solo `Scope` con `kind` GLOBAL/BLOCK (todavía sin FUNCTION ni CLASS), y `define()`/`resolve()`. No diseñarlo completo desde el inicio pensando en clases y funciones — eso se agrega cuando se implementen esas reglas, no antes.
3. **`types/types.py` en su versión mínima**: solo `IntegerType`, `StringType`, `BooleanType`, `ErrorType`. Nada de arrays ni clases todavía.
4. **Las dos reglas semánticas más simples y que más dependen de `Scope`**: "variable no declarada" y "prohibir redeclaración en el mismo ámbito" (sección 2.2 del enunciado). Son casi puramente un test de `Scope.resolve()`/`define()` — si estas dos reglas funcionan de punta a punta, el diseño de la tabla de símbolos queda validado con código real, no solo en el papel.
5. **`diagnostics.py`** con la lista simple de `Diagnostic` para que esas dos reglas reporten errores en vez de lanzar excepciones.
6. **Un test end-to-end** (2 archivos `.cps`: uno válido, uno con una variable sin declarar) que corra parser → visitor → diagnostics y compare el resultado. Es la primera prueba real de que el pipeline completo funciona.

Deliberadamente quedan fuera de este primer corte: funciones, clases, arreglos, control de flujo, y sobre todo la IDE y el bridge. Construir la IDE antes de tener siquiera una regla funcionando significa terminar mockeando datos, que después hay que rehacer — primero se valida el motor, después se le construye la ventana.

## 1. Alcance de esta fase

El enunciado (`README_SEMANTIC_ANALYSIS.md`) pide construir, sobre la gramática `Compiscript.g4` (subconjunto de TypeScript), un analizador sintáctico con acciones semánticas, un sistema de tipos, manejo de ámbitos, validación de funciones y clases, control de flujo, listas, una tabla de símbolos que sirva a futuras fases, una batería de pruebas por cada regla, y una IDE para escribir y compilar código. La ponderación (100 pts) se reparte en IDE (15), analizador sintáctico/semántico (60) y tabla de símbolos (25) — este documento cubre el diseño técnico de las tres partes.

Decisiones ya tomadas para este diseño:

- Parser generado con ANTLR (target Python3), tal como recomienda el curso.
- La IDE es una extensión de YALex Studio (la app Tauri + React que ya existe), no un proyecto nuevo.
- El analizador semántico y la tabla de símbolos se implementan en Python, consistente con el resto del repositorio (`yalex_parser`, `yapar_generator`, `bridge_cli.py`).

Este documento es solo de arquitectura y diseño técnico: no incluye calendario ni repartición de tareas por integrante.

## 2. Estructura de proyecto propuesta

Se agrega un nuevo paquete hermano a `yalex_parser/` y `yapar_generator/`, sin tocar el código de la fase anterior:

```
src/
  compiscript/
    grammar/
      Compiscript.g4            (copiado/ajustado desde docs/)
      generated/                (salida de antlr4 -Dlanguage=Python3, no se edita a mano)
    ast/
      builder.py                (ParseTree -> AST propio, opcional pero recomendado)
      nodes.py
    types/
      types.py                  (IntegerType, StringType, BooleanType, ArrayType, ClassType, FunctionType, ErrorType)
      coercion.py                (reglas de compatibilidad: is_assignable(from, to), etc.)
    symbols/
      symbol.py                 (VariableSymbol, ConstSymbol, FunctionSymbol, ClassSymbol, ParameterSymbol)
      scope.py                  (Scope, ScopeKind, tabla de símbolos como árbol de ámbitos)
    semantic/
      analyzer.py               (orquesta las pasadas del visitor)
      declarations_pass.py       (pre-declara funciones/clases del ámbito para soportar recursión)
      rules_types.py             (reglas 2.1)
      rules_scope.py             (reglas 2.2)
      rules_functions.py         (reglas 2.3)
      rules_control_flow.py      (reglas 2.4)
      rules_classes.py           (reglas 2.5)
      rules_arrays.py            (reglas 2.6)
      rules_general.py           (reglas 2.7: código muerto, expresiones sin sentido)
    diagnostics.py               (SemanticError/Warning, códigos, formato)
    bridge_compiscript.py        (protocolo JSON de acciones, igual patrón que bridge_cli.py)
tests/
  compiscript/
    types/        valid/*.cps  invalid/*.cps
    scope/        valid/*.cps  invalid/*.cps
    functions/     valid/*.cps  invalid/*.cps
    control_flow/  ...
    classes/       ...
    arrays/        ...
    general/       ...
    test_semantic_rules.py     (recorre cada carpeta y verifica diagnósticos esperados)
```

Mantener el árbol generado por ANTLR (`grammar/generated/`) fuera del control manual — se regenera con `antlr4 -Dlanguage=Python3 Compiscript.g4`, usando `antlr4-tools` (pip) en vez de Docker — evita ediciones accidentales sobre código autogenerado.

Dos paquetes de pip distintos entran en juego, no confundirlos: `antlr4-tools` es la herramienta de generación (solo se usa en desarrollo, para producir `grammar/generated/`) y `antlr4-python3-runtime` es la librería que ese código generado importa en tiempo de ejecución (`import antlr4`) — esta segunda sí va como dependencia del proyecto (`requirements.txt` / lo que use `bridge_compiscript.py`), la primera no.

## 3. Pipeline de análisis

El flujo, de extremo a extremo, para un archivo `.cps`:

```
código fuente (.cps)
   -> CompiscriptLexer (ANTLR)              tokens
   -> CompiscriptParser (ANTLR)             parse tree + errores sintácticos
   -> ASTBuilder (opcional)                 AST propio, más liviano para recorrer
   -> DeclarationsPass (visitor, pasada 1)   pre-declara funciones y clases del ámbito actual
   -> SemanticAnalyzer (visitor, pasada 2)   valida tipos/ámbito/funciones/control de flujo/clases
        construye la Tabla de Símbolos en simultáneo
   -> lista de Diagnostics (errores + warnings)
   -> IDE: árbol sintáctico, tabla de símbolos y diagnósticos, todo serializado a JSON
```

### ¿Por qué dos pasadas y no una?

El enunciado exige soportar recursión y (por construcción del lenguaje) funciones que se llaman entre sí antes de estar declaradas en el orden textual. Con una sola pasada top-to-bottom, una función A que llama a B definida después fallaría por "no declarada". La primera pasada solo registra las firmas (nombre, parámetros, tipo de retorno, y las clases con sus miembros) en el ámbito correspondiente sin bajar a validar cuerpos; la segunda pasada ya encuentra todo declarado y valida cuerpos con tipos completos.

### Visitor vs. Listener

Se recomienda ANTLR Visitor (`ParseTreeVisitor`) en vez de Listener para la pasada semántica: el chequeo de tipos es naturalmente bottom-up (una expresión como `a + b` necesita el tipo ya resuelto de `a` y de `b` antes de decidir el tipo del `+` y si es válido). Con Visitor cada `visit_X` devuelve un `Type` y el nodo padre lo consume directamente; con Listener habría que mantener una pila de tipos en el analizador, que es más frágil y difícil de depurar. Para el análisis de declaraciones (la pasada 1) sí se puede usar Listener, ya que ahí no se necesita propagar valores hacia arriba.

## 4. Sistema de tipos

Tipos a modelar (clase `Type` con subclases o un enum + metadatos, cualquiera funciona; se sugiere clases para poder adjuntar datos como `elementType` o `params`):

| Tipo | Ejemplo Compiscript | Notas de diseño |
|---|---|---|
| `IntegerType` | `let a: integer = 10;` | Único tipo numérico que existe hoy en la gramática. |
| `StringType` | `let b: string = "hola";` | |
| `BooleanType` | `let c: boolean = true;` | |
| `NullType` | `let d = null;` | Compatible con cualquier `ClassType` (asignar `null` a una referencia de objeto); no compatible con integer/string/boolean. |
| `VoidType` | `function f(): void { ... }` | La gramática actual no tiene `void` como `baseType` — ver sección 8, riesgo #1. |
| `ArrayType(elem, dims)` | `integer[]`, `integer[][]` | `dims=1,2,...` Comparar por elemento + dimensión. |
| `ClassType(name)` | `let p: Perro = new Perro(...);` | Guarda referencia al `ClassSymbol` para resolver miembros y herencia. |
| `FunctionType(params, ret)` | tipo de una función como valor | Necesario si se permite pasar funciones o solo para validar llamadas; ver riesgo #3 (closures). |
| `ErrorType` | — | Tipo "comodín" que se devuelve tras un error ya reportado, para no generar errores en cascada sobre el mismo símbolo. |

### Compatibilidad y coerción

- Aritmética (`+ - * /`): ambos operandos `IntegerType` (o `ErrorType`, que no genera error nuevo). Resultado: `IntegerType`.
- `+` con `StringType`: decidir explícitamente si se permite concatenación `string + string` o `string + integer` (no está en el enunciado ni en la gramática como caso especial). Recomendación: solo permitir `+` entre dos `string` o dos `integer`, documentando la decisión.
- Lógicos (`&& || !`): ambos operandos `BooleanType`.
- Comparación (`== != < <= > >=`): mismo tipo en ambos lados; `==` / `!=` adicionalmente permiten comparar contra `null` en tipos de clase.
- Asignación (`variable = expr`): el tipo de `expr` debe ser asignable al tipo declarado (`is_assignable(exprType, declaredType)`); `null` es asignable a cualquier `ClassType`; un `ClassType` hijo es asignable a su `ClassType` padre (covarianza simple por herencia).
- Arreglos: todos los elementos de un `arrayLiteral` deben unificar al mismo tipo (o ser `ErrorType`); el tipo declarado `T[]` exige que cada literal sea de tipo `T`.

## 5. Tabla de símbolos y manejo de ámbitos

La tabla de símbolos se modela como un árbol de `Scope` (no una tabla plana), porque el enunciado pide "creación de nuevos entornos de símbolo para cada función, clase y bloque" y "resolución adecuada según ámbito local o global". Cada `Scope` conoce a su padre (encadenamiento léxico), lo que resuelve nombres y closures de manera natural: buscar un identificador sube por la cadena de scopes hasta encontrarlo o llegar al global.

| Clase | Responsabilidad | Ejemplo |
|---|---|---|
| `Scope` | `kind` (GLOBAL/FUNCTION/CLASS/BLOCK), padre, diccionario nombre→Symbol, `define()`/`resolve()` | cada `{ }` abre un BLOCK scope |
| `VariableSymbol` | nombre, tipo declarado, es_const, inicializada (bool) | `let`/`const` |
| `ParameterSymbol` | nombre, tipo — subclase de `VariableSymbol`, siempre "inicializada" | parámetros de función |
| `FunctionSymbol` | nombre, lista de `ParameterSymbol`, tipo de retorno, scope propio, referencia a la clase si es método | `function`/método |
| `ClassSymbol` | nombre, superclase (`ClassSymbol` opcional), diccionario de campos y métodos, scope de la clase | `class` |

### Reglas de resolución

- `define(name, symbol)`: error si ya existe en ESTE mismo scope (regla de "prohibir redeclaración en el mismo ámbito"); sí se permite *shadowing* entre scopes distintos (una variable local puede tener el mismo nombre que una global, es una decisión de diseño a confirmar con el equipo).
- `resolve(name)`: busca en el scope actual y sube por la cadena de padres hasta GLOBAL; si no aparece en ningún nivel, es "variable no declarada".
- Los métodos y campos de una clase se resuelven primero en la propia `ClassSymbol` y, si no están, se sube a la superclase (herencia) antes de fallar.

Para que la tabla "interactúe con cada fase de la compilación" (como pide el punto 5 del enunciado), conviene exportarla como estructura serializable (a JSON) independiente del árbol de `Scope` en memoria — así, una fase futura (generación de código intermedio) puede consumirla sin depender de las clases Python del analizador semántico.

## 6. Analizador semántico: organización de las reglas

Un solo visitor gigante que implemente las ~25 reglas del enunciado es difícil de mantener y de probar. Se recomienda un `SemanticAnalyzer` "delgado" que hereda el visitor generado por ANTLR y delega cada categoría a un módulo de reglas (`rules_types.py`, `rules_scope.py`, etc.), pasándoles el contexto compartido (scope actual, tabla de símbolos, lista de diagnósticos, función/clase/loop actual).

| Categoría | Estado que necesita | Ejemplos de reglas (enunciado 2.x) |
|---|---|---|
| Tipos | tipos inferidos de cada nodo de expresión | operandos de `+,-,*,/` enteros; operandos de `&&,\|\|,!` booleanos; asignación coincide con tipo declarado; `const` debe inicializarse |
| Ámbito | pila de `Scope` activa | no declarada, redeclaración, acceso en bloques anidados |
| Funciones | `FunctionSymbol` actual + su tipo de retorno esperado | aridad/tipo de argumentos, tipo de retorno, recursión, closures, nombres duplicados |
| Control de flujo | contador de anidamiento de loops, bandera "dentro de función" | condición boolean en if/while/for/switch; break/continue solo en loops; return solo dentro de función |
| Clases | `ClassSymbol` actual (para `this`) y cadena de herencia | atributos/métodos existen, constructor válido, `this` bien resuelto |
| Arreglos | `ArrayType` del contexto | tipo de elementos consistente, índices de tipo integer |
| Generales | flujo de sentencias del bloque | código después de return/break/continue, expresiones sin sentido (ej. multiplicar una función), declaraciones duplicadas de parámetros |

Cada módulo de reglas expone funciones puras que reciben `(nodo, contexto)` y devuelven un `Type` o agregan un `Diagnostic` — así cada regla se puede probar de forma aislada, no solo end-to-end con archivos `.cps` completos.

## 7. Diagnósticos (errores y warnings)

En vez de lanzar excepciones al primer error (lo que cortaría el análisis y solo mostraría un problema a la vez), el analizador acumula una lista de `Diagnostic { severidad, código, mensaje, línea, columna }` y sigue recorriendo el árbol usando `ErrorType` donde corresponda para no generar una cascada de errores derivados del primero. Esto es consistente con `error_format.py` que ya existe en `yalex_parser` para la fase anterior — se puede reusar el mismo estilo de formato de mensaje.

- Severidad ERROR: detiene la validez semántica del programa (lo que pide el enunciado como "error por...").
- Severidad WARNING: útil para "código muerto" — no impide compilar pero se muestra en la IDE.
- Código estable por regla (ej. `SEM-TYPE-001`, `SEM-SCOPE-003`) para que la batería de pruebas verifique "se disparó el diagnóstico correcto", no solo "hubo algún error".

## 8. Integración con la IDE (YALex Studio)

Se sigue el mismo patrón que ya usa la app para YALex/YAPar: un tercer "workflow" en el panel Pipeline (junto a YALex y YAPar) llamado Compiscript, que llama a un bridge Python vía un nuevo comando de Tauri, replicando `run_yalex_bridge` en `src-tauri/src/lib.rs` (mismo mecanismo de invocar Python con un payload JSON y parsear la respuesta).

| Acción (bridge) | Qué calcula | Vista en la IDE |
|---|---|---|
| `compiscriptParse` | corre el lexer/parser, junta errores sintácticos | lista de errores de sintaxis |
| `compiscriptTree` | parse tree o AST serializado | vista de árbol sintáctico (reusar el renderizador SVG que ya existe para autómatas) |
| `compiscriptSymbols` | vuelca la tabla de símbolos por ámbito | tabla de símbolos navegable (árbol de scopes expandible) |
| `compiscriptCheck` | corre el análisis semántico completo | lista de diagnósticos con línea/columna clicable, que salta al editor |

Los nuevos tipos `AnyAction` (`types.ts`), los estados de resultado (`actionResults`) y el `ResultPanel` ya existentes en `App.tsx` están preparados para agregar estas acciones sin rediseñar el shell — solo se suman nuevas entradas al mismo patrón que ya usan `yaparSpec`/`yaparAutomaton`/`yaparTable`.

## 9. Estrategia de pruebas

El enunciado pide explícitamente una batería de pruebas por regla con casos exitosos y fallidos. Se recomienda:

- Un archivo `.cps` "válido" y uno o más "inválido" por regla, agrupados por categoría (carpetas de la sección 2).
- Un test parametrizado (pytest) por carpeta que: (a) para los casos válidos, exige cero diagnósticos ERROR; (b) para los inválidos, exige que aparezca el código de diagnóstico esperado (no solo "algún error").
- Tests unitarios adicionales para el sistema de tipos (`is_assignable`, `unify`) y para `Scope.resolve()`/`define()` sin pasar por el parser completo — más rápidos y más fáciles de depurar cuando fallan.
- Al menos un `.cps` de "integración" grande que ejercite muchas reglas a la vez, para detectar interacciones entre reglas (ej. una función recursiva dentro de una clase con herencia).

## 10. Riesgos y decisiones abiertas

Antes de empezar a codear, conviene que el equipo decida explícitamente estos puntos — quedan documentados aquí para no perderlos:

- La gramática (`Compiscript.g4`) no define `float` como `baseType`, pero el enunciado pide verificar tipos aritméticos para "integer o float". Hay que decidir: ¿se agrega `float` a la gramática, o se interpreta que el lenguaje solo maneja `integer` y el enunciado es genérico? Esto afecta `IntegerLiteral`/tipos y debe decidirse antes de escribir `rules_types.py`.
- `switchCase` en la gramática no tiene `break` explícito (a diferencia de TypeScript/C) — hay que decidir si el switch tiene fallthrough implícito o si cada case retorna solo su bloque; esto cambia el análisis de "código muerto" del punto 2.7.
- Closures: el enunciado pide "debe capturar variables del entorno donde se definen". Con `Scope` encadenado esto se resuelve solo para lectura de variables (la función anidada resuelve hacia arriba en tiempo de análisis semántico); si además se requiere semántica de captura en tiempo de ejecución (una fase posterior de generación de código), eso es una decisión de la fase de codegen, no de esta — dejarlo anotado para no bloquear esta fase por un requisito que pertenece a otra.
- Sobrecarga de funciones: el enunciado dice "si no se soporta sobrecarga" — hay que decidir explícitamente que NO se soporta (recomendado, por simplicidad) y por lo tanto todo nombre de función duplicado en el mismo ámbito es error, sin importar la firma.
- Arreglos multidimensionales: la gramática permite `integer[][]` sin límite de anidamiento; decidir si se soporta genéricamente (`ArrayType` recursivo) o se limita a 1-2 dimensiones para simplificar, dado que no es un punto explícito de la ponderación.
- **(Confirmado al generar el parser)** La gramática exige llaves en el cuerpo de `if`/`while`/`foreach` (`ifStatement: 'if' '(' expression ')' block ...`, y `block` es `'{' statement* '}'`). Los ejemplos de `docs/Compiscript.md` —como `if (n <= 1) return 1;` en el factorial recursivo— están escritos **sin** llaves y no parsean tal cual con `Compiscript.g4` (se verificó generando el parser y corriéndolo: falla con `missing '{'`). Hay que decidir si se ajusta la gramática para aceptar sentencia suelta además de bloque, o si se corrigen los ejemplos de la documentación del lenguaje para usar siempre `{ }`. El walking skeleton (sección 0) usa la segunda opción por ahora.

## 11. Trazabilidad: requerimiento → componente

Tabla de referencia rápida para no perder puntos de la rúbrica al revisar el avance:

| Requerimiento del enunciado | Dónde se implementa en este diseño |
|---|---|
| Analizador sintáctico (ANTLR) | `compiscript/grammar/` + `Compiscript.g4` |
| Árbol sintáctico con representación visual | `ASTBuilder` + acción `compiscriptTree` + vista de árbol en la IDE |
| Sistema de tipos | `compiscript/types/` + `rules_types.py` |
| Manejo de ámbito | `compiscript/symbols/scope.py` + `rules_scope.py` |
| Funciones y procedimientos | `rules_functions.py` + `FunctionSymbol` |
| Control de flujo | `rules_control_flow.py` (contexto: loopDepth, currentFunction) |
| Clases y objetos | `rules_classes.py` + `ClassSymbol` + herencia en `Scope` |
| Listas y estructuras | `rules_arrays.py` + `ArrayType` |
| Generales (código muerto, etc.) | `rules_general.py` |
| Listeners/Visitors de ANTLR | `SemanticAnalyzer` (Visitor) + `DeclarationsPass` (Listener o Visitor liviano) |
| Batería de tests por regla | `tests/compiscript/<categoría>/valid|invalid` + `test_semantic_rules.py` |
| Tabla de símbolos entre fases | `symbols/scope.py` + exportación serializable a JSON |
| IDE | extensión de YALex Studio: workflow Compiscript + `bridge_compiscript.py` |
| Documentación de arquitectura | este documento + comentarios de diseño en cada módulo |

## 12. Próximos pasos sugeridos

- ✅ **Hecho** — Instalar `antlr4-tools`, generar el parser y comprobar que parsea (con ajustes, ver hallazgo de la sección 10) los ejemplos del lenguaje. Ver `src/compiscript/`.
- ✅ **Hecho** — Implementar `symbols/scope.py` y `typesystem/types.py` (versión mínima: solo GLOBAL/BLOCK, solo integer/string/boolean/error) con tests unitarios. Ver `src/compiscript/README.md` para cómo correrlos.
- ✅ **Hecho** — Walking skeleton end-to-end con dos reglas (`SEM-SCOPE-001` variable no declarada, `SEM-SCOPE-002` redeclaración en el mismo ámbito) y su test de integración (`tests/compiscript/test_walking_skeleton.py`).
- Cerrar las decisiones abiertas de la sección 10 en equipo (especialmente `float`, switch fallthrough, y ahora también si/while/foreach sin llaves — las tres cambian la gramática).
- Recién ahora, implementar `rules_*.py` categoría por categoría sobre la base ya validada, siguiendo el mismo orden del enunciado (tipos, ámbito, funciones, control de flujo, clases, arreglos, generales), agregando el `.cps` de prueba de cada regla antes o junto con la regla (TDD ligero). Cada regla nueva probablemente necesita ampliar `Scope` (agregar `ScopeKind.FUNCTION`/`CLASS`) y `Type` (agregar `ArrayType`/`ClassType`/`FunctionType`) — hacerlo incrementalmente, no de una vez.
- Conectar el bridge y la IDE al final — es la parte más "visible" pero no debería bloquear el desarrollo del analizador en sí.
