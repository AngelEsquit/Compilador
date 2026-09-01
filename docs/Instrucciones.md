# Instrucciones del Proyecto: Analisis Semantico de Compiscript

Fecha de entrega: lunes 07 de septiembre de 2026  
Modalidad: en grupos (maximo: tres personas)  
Ponderacion: 24 puntos  

---

## 1. Documentos y Recursos del Proyecto

- **Lenguaje de programacion a utilizar:** Definicion de Compiscript (`docs/Compiscript.md` y `docs/README.md`).
- **Gramatica propuesta del lenguaje (ANTLR):** `docs/Compiscript.g4` y `src/compiscript/grammar/`.
- **Requerimientos semanticos:** `docs/README_SEMANTIC_ANALYSIS.md`.
- **Diseno de arquitectura:** `docs/Compiscript_Diseno_Semantico.md`.
- **Distribucion de tareas y asignaciones:** `docs/DISTRIBUCION_TAREAS.md`.
- **Material teorico de clase:** Presentaciones en `docs/presentaciones/`.

---

## 2. Pautas y Fundamentos Teoricos de Clase (Presentaciones 01 a 05)

Todo el desarrollo del compilador debe seguir de manera estricta los conceptos, estructuras de datos y formalismos explicados en las presentaciones de clase:

### A. Tabla de Simbolos (Presentacion 02: `docs/presentaciones/02 - Tabla de simbolos v 1.11.pptx`)
1. **Atributos minimos por simbolo:**
   - Lexema / Nombre del identificador.
   - Tipo de dato / Tipo semantico (Integer, String, Boolean, Array, Class, Function).
   - Alcance (Scope) al que pertenece.
   - Posicion en el codigo fuente: linea y columna.
   - Estado de inicializacion y constancia (`is_const`).
   - Para funciones: lista de parametros (tipos y nombres), numero de parametros (aridad) y tipo de retorno.
   - Para clases: superclase, diccionario de campos y metodos.
2. **Tres Operaciones Basicas:**
   - **Insertar (`define`):** Agrega un simbolo al ambito actual. Si ya existe un simbolo con el mismo nombre en este mismo ambito, debe reportar error por redeclaracion (`SEM-SCOPE-002`).
   - **Recuperar (`resolve`):** Busca el simbolo en el ambito actual y sube recursivamente por la cadena de ambitos padres (Alcance N -> Alcance N-1 -> ... -> Alcance 0 Global). Si no existe en ningun nivel, reporta variable no declarada (`SEM-SCOPE-001`).
   - **Actualizar (`update`):** Permite actualizar atributos de un simbolo existente (por ejemplo, marcar `initialized = True` tras una asignacion).
3. **Manejo de Alcances en Arbol:**
   - Estructura jerarquica de arbol de `Scope` (no una tabla plana).
   - Cada bloque `{ ... }`, cuerpo de funcion, clase o bucle crea un ambito hijo.
   - Se permite el sombreado (*shadowing*): un ambito interno puede declarar una variable con el mismo nombre que una variable de un ambito superior sin generar error.

### B. Sistema de Tipos y Reglas Semanticas (Presentacion 03: `docs/presentaciones/03 - Analisis semantico v 1.1.pptx`)
1. **Formalismo de Deduccion de Tipos:**
   - Las reglas deben seguir el esquema formal de juicio de tipos: `Gamma |- expresion : Tipo`, donde `Gamma` representa el entorno (la tabla de simbolos activa).
   - Axiomas: `Gamma |- 123 : integer`, `Gamma |- "abc" : string`, `Gamma |- true : boolean`.
   - Operaciones aritmeticas: Si `Gamma |- a : integer` y `Gamma |- b : integer`, entonces `Gamma |- a + b : integer`. Si los tipos no coinciden, `Gamma |- a + b : error`.
   - Control de flujo: `Gamma |- condicion : boolean` para `if`, `while`, `do-while`, `for`.
2. **Estrategia de Recuperacion con Tipo Comodin (`ErrorType`):**
   - Cuando se detecta un error de tipos, se emite el diagnostico correspondiente y se retorna `ErrorType`.
   - `ErrorType` es compatible con cualquier tipo en evaluaciones posteriores, evitando que un solo error genere una cascada interminable de mensajes derivados.

### C. Traduccion Orientada por la Sintaxis (Presentaciones 04 y 05)
1. **Atributos Sintetizados (Bottom-Up):**
   - El tipo de las expresiones compuestas se sintetiza a partir del tipo resuelto de sus hijos (recorrido Visitor post-order).
2. **Atributos Heredados (Top-Down):**
   - La informacion de contexto (el scope activo `current_scope`, el flag de estar dentro de un bucle para `break`/`continue`, y el scope de funcion para `return`) se propaga hacia abajo a medida que se desciende en el arbol sintactico.
3. **Estructuras de Tipos Compuestos (Presentacion 05):**
   - Los arreglos se modelan estructuralmente como `ArrayType(elem_type, dimensions)` (equivalente a `array(dims, elem_type)`).

---

## 3. Observaciones y Restricciones Oficiales

1. La actividad debera realizarse en los grupos que se conformaron al principio del semestre.
2. El lenguaje que se debe analizar lexica, sintacticamente y semanticamente es Compiscript.
3. Las herramientas para generar analizadores lexicos y sintacticos, el lenguaje de programacion y las librerias a utilizar quedan a eleccion del grupo (se utiliza ANTLR con runtime de Python).
4. Es obligatorio utilizar una herramienta generadora de analizadores; no se aceptara una implementacion completamente manual del analizador lexico o del analizador sintactico. El incumplimiento de esta restriccion se penalizara colocando cero puntos de nota.
5. El software debera contar con una interfaz grafica amigable y estetica. El incumplimiento de esta restriccion se penalizara restando cinco puntos a la nota obtenida.
6. El archivo de entrada debera seleccionarse desde la interfaz grafica. El incumplimiento de esta restriccion se penalizara restando cinco puntos a la nota obtenida.
7. Los resultados del analisis deberan mostrarse dentro de la interfaz grafica; no sera suficiente mostrarlos unicamente en la consola. El incumplimiento de esta restriccion se penalizara restando cinco puntos a la nota obtenida.
8. Cada grupo debera escribir los archivos de prueba que se utilizaran en la calificacion.
9. El analizador lexico debera continuar procesando la entrada despues de encontrar caracteres o lexemas no reconocidos.
10. El analizador sintactico debera implementar una estrategia de recuperacion que le permita continuar el parseo despues de encontrar un error.
11. El analizador semantico debera continuar despues de encontrar un error semantico.
12. No se aceptara que el proceso de analisis termine inmediatamente despues de encontrar el primer error. El software debera intentar reportar la mayor cantidad posible de errores en una misma ejecucion.
13. Debera evitarse la generacion repetitiva del mismo error, los ciclos infinitos durante la recuperacion y los mensajes derivados que no aporten informacion util.
14. El alcance de la actividad se limita al analisis lexico, sintactico y semantico. No se requiere ejecutar el programa, generar codigo intermedio ni producir codigo objeto.