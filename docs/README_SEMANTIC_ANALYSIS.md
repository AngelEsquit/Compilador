# Fase de Compilacion: Analisis Semantico

## Descripcion General

En esta fase de compilacion, deberan de implementar el analisis semantico para un lenguaje denominado: Compiscript.

* Lea atentamente el README.md en este directorio, en donde encontrara las generalidades del lenguaje.
* En el directorio `program` encontrara la gramatica de este lenguaje en ANTLR y en BNF. Se le otorga un playground similar a los laboratorios para que usted pueda experimentar inicialmente.
* **Modalidad: Grupos de 3 integrantes.**

## Requerimientos

1. **Crear un analizador sintactico utilizando ANTLR** o cualquier otra herramienta similar de su eleccion.
   * Se recomienda usar ANTLR dado que es la herramienta que se utiliza en las lecciones del curso, pero puede utilizar otro Generador de Parsers.
2. Añadir **acciones/reglas semanticas** en este analizador sintactico y **construir un arbol sintactico, con una representacion visual.**
   1. **Sistema de Tipos**
      * Verificacion de tipos en operaciones aritmeticas (`+`, `-`, `*`, `/`) - los operandos deben ser de tipo `integer` o `float`.
      * Verificacion de tipos en operaciones logicas (`&&`, `||`, `!`) - los operandos deben ser de tipo `boolean`.
      * Compatibilidad de tipos en comparaciones (`==`, `!=`, `<`, `<=`, `>`, `>=`) - los operandos deben ser del mismo tipo compatible.
      * Verificacion de tipos en asignaciones - el tipo del valor debe coincidir con el tipo declarado de la variable.
      * Inicializacion obligatoria de constantes (`const`) en su declaracion.
      * Verificacion de tipos en listas y estructuras (si se soportan mas adelante).
   2. **Manejo de Ambito**
      * Resolucion adecuada de nombres de variables y funciones segun el ambito local o global.
      * Error por uso de variables no declaradas.
      * Prohibir redeclaracion de identificadores en el mismo ambito.
      * Control de acceso correcto a variables en bloques anidados.
      * Creacion de nuevos entornos de simbolo para cada funcion, clase y bloque.
   3. **Funciones y Procedimientos**
      * Validacion del numero y tipo de argumentos en llamadas a funciones (coincidencia posicional).
      * Validacion del tipo de retorno de la funcion - el valor devuelto debe coincidir con el tipo declarado.
      * Soporte para funciones recursivas - verificacion de que pueden llamarse a si mismas.
      * Soporte para funciones anidadas y closures - debe capturar variables del entorno donde se definen.
      * Deteccion de multiples declaraciones de funciones con el mismo nombre (si no se soporta sobrecarga).
   4. **Control de Flujo**
      * Las condiciones en `if`, `while`, `do-while`, `for`, `switch` deben evaluar expresiones de tipo `boolean`.
      * Validacion de que se puede usar `break` y `continue` solo dentro de bucles.
      * Validacion de que el `return` este dentro de una funcion (no fuera del cuerpo de una funcion).
   5. **Clases y Objetos**
      * Validacion de existencia de atributos y metodos accedidos mediante `.` (dot notation).
      * Verificacion de que el constructor (si existe) se llama correctamente.
      * Manejo de `this` para referenciar el objeto actual (verificar ambito).
   6. **Listas y Estructuras de Datos**
      * Verificacion del tipo de elementos en listas.
      * Validacion de indices (acceso valido a listas).
   7. **Generales**
      * Deteccion de codigo muerto (instrucciones despues de un `return`, `break`, etc.).
      * Verificacion de que las expresiones tienen sentido semantico (por ejemplo, no multiplicar funciones).
      * Validacion de declaraciones duplicadas (variables, parametros).
3. Implementar la recorrida de este arbol utilizando ANTLR Listeners o Visitors para evaluar las reglas semanticas que se ajusten al lenguaje.
4. **Para los puntos anteriores, referentes a las reglas semanticas, debera de escribir una bateria de tests para validar casos exitosos y casos fallidos en cada una de las reglas mencionadas.**
   * Al momento de presentar su trabajo, esta bateria de tests debe estar presente y sera tomada en cuenta para validar el funcionamiento de su compilador.
5. Construir una **tabla de simbolos** que interactue con cada fase de la compilacion, incluyendo las fases mencionadas anteriormente. Esta tabla debe considerar el **manejo de entornos** y almacenar toda la informacion necesaria para esta y futuras fases de compilacion.
6. Debera **desarrollar un IDE** que permita a los usuarios escribir su propio codigo y compilarlo.
7. Debera crear **documentacion asociada a la arquitectura de su implementacion** y **documentacion de las generalidades de como ejecutar su compilador**.
8. Entregar su repositorio de GitHub.
   * Se validan los commits y contribuciones de cada integrante, no se permite "compartir" commits en conjunto, debe notarse claramente que porcion de codigo implemento cada integrante.

## Ponderacion

| Componente | Puntos |
| --- | --- |
| IDE | 15 puntos |
| Analizador Sintactico y Semantico con validacion de reglas semanticas y sistema de tipos | 60 puntos |
| Tabla de simbolos | 25 puntos |
| **Total** | **100 puntos** |
