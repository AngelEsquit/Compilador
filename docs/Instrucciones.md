Fecha de entrega: lunes 07 de septiembre de 2026
Modalidad: en grupos (máximo: tres personas)
Ponderación: 24 puntos

Instrucciones

Lenguaje de programación a utilizar: Definición de Compiscript
Gramática propuesta del lenguaje, en ANTLR: Gramática de Compiscript
Requerimientos para el proyecto: Análisis semántico de Compiscript
Observaciones y restricciones

La actividad deberá realizarse en los grupos que se conformaron al principio del semestre.
El lenguaje que se debe analizar léxica, sintácticamente y semánticamente es Compiscript.
Las herramientas para generar analizadores léxicos y sintácticos, el lenguaje de programación y las librerías a utilizar quedan a elección del grupo.
Es obligatorio utilizar una herramienta generadora de analizadores; no se aceptará una implementación completamente manual del analizador léxico o del analizador sintáctico. El incumplimiento de esta restricción se penalizará colocando cero puntos de nota.
El software deberá contar con una interfaz gráfica amigable y estética. El incumplimiento de esta restricción se penalizará restando cinco puntos a la nota obtenida.
El archivo de entrada deberá seleccionarse desde la interfaz gráfica. El incumplimiento de esta restricción se penalizará restando cinco puntos a la nota obtenida.
Los resultados del análisis deberán mostrarse dentro de la interfaz gráfica; no será suficiente mostrarlos únicamente en la consola. El incumplimiento de esta restricción se penalizará restando cinco puntos a la nota obtenida.
Cada grupo deberá escribir los archivos de prueba que se utilizarán en la calificación.
El analizador léxico deberá continuar procesando la entrada después de encontrar caracteres o lexemas no reconocidos.
El analizador sintáctico deberá implementar una estrategia de recuperación que le permita continuar el parseo después de encontrar un error.
El analizador semántico deberá continuar después de encontrar un error semántico.
No se aceptará que el proceso de análisis termine inmediatamente después de encontrar el primer error. El software deberá intentar reportar la mayor cantidad posible de errores en una misma ejecución. Esto no implica que deba identificar literalmente todos los errores existentes, debido a que un error puede modificar la interpretación de los símbolos posteriores; sin embargo, deberá evidenciarse que existe un mecanismo efectivo de recuperación. El incumplimiento de esta restricción se penalizará restando cinco puntos a la nota obtenida.
Deberá evitarse la generación repetitiva del mismo error, los ciclos infinitos durante la recuperación y los mensajes derivados que no aporten información útil. El incumplimiento de esta restricción se penalizará restando cinco puntos a la nota obtenida.
El alcance de la actividad se limita al análisis léxico, sintáctico y semántico. No se requiere ejecutar el programa, generar código intermedio ni producir código objeto. El incumplimiento de esta restricción se penalizará colocando cero puntos de nota.