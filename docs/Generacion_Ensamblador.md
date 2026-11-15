**UVG, Construcción de Compiladores, 2026 II**

# Generación de código ensamblador

Proyecto 03: del código de tres direcciones de Compiscript a MIPS32.
Cómo se eligen los registros, cómo se arma cada registro de activación y cómo se traduce cada instrucción.

**Rúbrica:** 30 puntos, 14 criterios
**Integrantes:** España 23361, Esquit 23221, Barreda 23354

---

## 1. Resumen

El backend recibe el TAC (ver [Lenguaje_Intermedio.md](Lenguaje_Intermedio.md)) y la distribución de memoria (ver [PRY2_IMPLEMENTACION.md](PRY2_IMPLEMENTACION.md)) y produce un archivo `.asm` para MARS o SPIM.

| Paso | Módulo | Resultado |
|---|---|---|
| 1. Ubicar operandos y deducir tipos | `backend/operands.py` | Cada nombre del TAC es una constante o una variable con casa en memoria |
| 2. Bloques básicos y variables vivas | `backend/blocks.py` | Grafo de flujo y siguiente uso de cada variable |
| 3. Selección de registros | `backend/registers.py` | Qué registro usa cada operando y cuándo se guarda en memoria |
| 4. Traducción | `backend/mips.py`, `floats.py`, `classes.py`, `exceptions.py` | Instrucciones MIPS |
| 5. Optimización por mirilla | `backend/peephole/` | Instrucciones MIPS reducidas |
| 6. Ejecución | `backend/simulator.py` o MARS | Salida del programa y árbol de activación |

Solo se genera ensamblador si el programa no tiene errores léxicos, sintácticos ni semánticos.

## 2. Convenciones

| Registro | Uso |
|---|---|
| `$t0` a `$t9` | Los reparte el asignador. Ninguno sobrevive a una llamada |
| `$a0` a `$a3`, `$v1` | Auxiliares dentro de una instrucción y argumentos de la biblioteca de ejecución |
| `$v0` | Valor de retorno y número de llamada al sistema |
| `$f0`, `$f2`, `$f12` | Operaciones e impresión de `float` |
| `$gp` | Inicio del área estática (variables globales) |
| `$fp` | Inicio del registro de activación actual |
| `$sp` | Tope de la pila |
| `$ra` | Dirección de retorno |

Tamaños: enteros, `float` y referencias (cadenas, arreglos, objetos) ocupan 4 bytes y se leen con `lw`; los booleanos ocupan 1 byte y se leen con `lbu`. El layout reserva 8 bytes para `float` y referencias: se usan los 4 bajos.

El TAC no nombra las variables de forma única. Cada instrucción lleva el ámbito con el que se emitió, y con él se llega al símbolo y a su offset.

## 3. Selección de registros

Es el algoritmo de descriptores (getReg) sobre bloques básicos.

**Bloques y vida.** Una función se parte en bloques en cada etiqueta y después de cada salto. Sobre el grafo de flujo se calcula, con un análisis hacia atrás, qué variables están vivas al entrar y al salir de cada bloque. Dentro del bloque se anota para cada instrucción el siguiente uso de cada variable. Una llamada cuenta como uso de todas las globales y de las variables que una función anidada captura.

**Descriptores.** Mientras se traduce un bloque se mantienen dos tablas:

- descriptor de registros: qué variables tienen su valor actual en cada registro;
- descriptor de direcciones: en qué lugares (memoria, registros) está el valor actual de cada variable.

**Elección del registro de un operando.**

1. Si el operando ya está en un registro, se usa ese.
2. Si hay un registro libre, se carga ahí.
3. Si no, se desaloja el registro más barato. Cuesta cero el que solo tiene valores muertos o valores que también están en memoria. Entre iguales se elige el que se usará más tarde. Si el valor sigue vivo y solo existe en ese registro, se guarda en su casa: eso es un derrame.

**Elección del registro del resultado.** Si la variable ya ocupa sola un registro, se reutiliza. Si un operando muere en esa instrucción, el resultado toma su registro. En otro caso se aplica la regla anterior.

**Copias.** `x = y` no emite código: `x` se agrega al registro de `y`.

**Fin de bloque y llamadas.** Al terminar un bloque se guardan solo las variables vivas cuyo valor no está en memoria, y los registros quedan vacíos. Antes de `jal` se hace lo mismo con lo que sigue vivo después de la llamada.

Ejemplo, `return (a + b) * (c + d) + (a - b) * (c - d);` con tres registros:

```text
    # t0 = a + b
    lw $t0, 24($fp)                 # carga a
    lw $t1, 28($fp)                 # carga b
    addu $t2, $t0, $t1
    # t1 = c + d
    lw $t0, 32($fp)                 # carga c
    lw $t1, 36($fp)                 # carga d
    sw $t2, 40($fp)                 # derrame t0
    addu $t2, $t0, $t1
```

`a` y `b` pierden su registro sin guardarse porque su valor sigue en memoria. `t0` sí se guarda: está vivo y solo existía en `$t2`. Con diez registros el mismo código no tiene derrames.

La opción `--registers=N` de la línea de comandos y el control del IDE limitan los registros disponibles para observar este comportamiento.

## 4. Registros de activación

El ensamblador usa el registro que calcula `symbols/layout.py`, sin cambios:

```text
fp+0    saved_fp
fp+8    return_address
fp+16   access_link
fp+24   parámetros (this primero en los métodos)
        variables locales
        temporales
```

**Llamada.**

1. Cada `param x` apila 4 bytes. El primer argumento queda más abajo.
2. Si la función es anidada, `link n` deja su access_link en `$v1`.
3. Se guardan los valores vivos y se ejecuta `jal`.
4. Al volver, el llamador desapila los argumentos y toma el resultado de `$v0`.

**Prólogo y epílogo.**

```text
f_fact:
    addiu $sp, $sp, -48             # registro de fact: 48 bytes
    sw $fp, 0($sp)                  # saved_fp
    sw $ra, 8($sp)                  # return_address
    move $fp, $sp
    lw $a0, 48($fp)
    sw $a0, 24($fp)                 # parametro n
    ...
f_fact_fin:
    lw $ra, 8($fp)
    lw $fp, 0($fp)
    addiu $sp, $sp, 48
    jr $ra
```

El prólogo copia cada argumento desde la pila del llamador a su casilla de parámetro. Como cada activación reserva su propio registro, la recursividad no necesita nada adicional.

**Variables globales.** Viven en `_static`, en `.data`, y se acceden como `offset($gp)`.

**Funciones anidadas.** `up(n).x` sigue `n` veces el access_link (`16($fp)`) y lee `x` en ese registro. El registro del programa principal se guarda al inicio para alcanzarlo directamente.

**Árbol de activación.** El simulador registra cada `jal` a una función del programa y cada retorno, con los argumentos y el resultado:

```text
main()
  fib(3) = 2
    fib(2) = 1
      fib(1) = 1
      fib(0) = 0
    fib(1) = 1
```

Se ve con `--tree` y en la pestaña Árbol de activación del IDE.

## 5. Traducción por construcción

| TAC | MIPS |
|---|---|
| `x = 5` | `li $t0, 5` |
| `x = y` | sin código (comparten registro) |
| `t = a + b`, `a - b`, `a * b` | `addu`, `subu`, `mul` |
| `t = a + 1` | `addiu $t0, $t1, 1` |
| `t = a / b`, `a % b` | `beqz $t1, _div_zero`, `div $t0, $t1`, `mflo` o `mfhi` |
| `t = a < b`, `<=`, `>`, `>=`, `==`, `!=` | `slt`, `sle`, `sgt`, `sge`, `seq`, `sne` |
| `t = -a`, `t = !a` | `subu $t0, $zero, $t1`, `xori $t0, $t1, 1` |
| `goto L` | `j L` |
| `if t goto L`, `ifFalse t goto L` | `bnez $t0, L`, `beqz $t0, L` |
| `print x` | `move $a0, ...` y `jal _print_int`, `_print_str`, `_print_bool` o `_print_float` según el tipo |
| `param x` | `addiu $sp, $sp, -4` y `sw $t0, 0($sp)` |
| `t = call f, n` | `jal f_f`, `addiu $sp, $sp, 4*n`, `move $t0, $v0` |
| `return x` | `move $v0, $t0` y `j f_f_fin` |
| `halt` | `li $v0, 10` y `syscall` |

**Sentencias de control.** `if`, `while`, `do-while`, `for`, `foreach`, `switch`, el operador ternario y el cortocircuito de `&&` y `||` llegan al backend como etiquetas y saltos, así que se traducen con las tres filas de saltos de la tabla.

**Cadenas.** Los literales van a `.data` con `.asciiz`. La concatenación llama a `_concat`, que reserva memoria con la llamada al sistema 9, y la comparación llama a `_streq`.

**Arreglos.** Un arreglo es un bloque del montículo: la longitud en la primera palabra y después los elementos de 4 bytes.

```text
    # t2 = v[t0]
    beqz $t0, _null_error
    lw $a0, 0($t0)                  # longitud
    bgeu $t1, $a0, _index_error
    sll $a1, $t1, 2
    addu $a1, $a1, $t0
    lw $t2, 4($a1)
```

La comparación sin signo rechaza también los índices negativos.

**Clases, objetos y herencia.** Un objeto es un bloque del montículo (`_alloc`). Su primera palabra apunta a la tabla de métodos de su clase y los campos siguen en el offset que calcula `symbols/layout.py`. Un campo heredado conserva su offset, así que un método de la superclase lo lee igual en una instancia de cualquier subclase.

```text
.data
_vt_Animal: .word f_Animal_hablar, f_Animal_presentar
_vt_Perro:  .word f_Perro_hablar,  f_Animal_presentar    # sobrescribe el slot 0
```

La tabla tiene una palabra por método, en el orden de su `slot`. Una subclase copia la tabla de su superclase y cambia las entradas sobrescritas, por eso un método tiene el mismo `slot` en toda la jerarquía.

| TAC | MIPS |
|---|---|
| `t = new C, n` | `_alloc` con el tamaño de `C`, `la $a1, _vt_C` y `sw $a1, 0($v0)`; si hay constructor (propio o heredado), baja `$sp`, corre los `n` argumentos para dejar `this` primero, `jal` al constructor y recupera el objeto |
| `t = o.f` | `beqz` a `_null_error` y `lw` o `lbu` en `offset(o)` |
| `o.f = v` | `beqz` a `_null_error` y `sw` o `sb` en `offset(o)` |
| `t = invoke o.m, n` | el receptor es el primer argumento apilado: `lw $a0, 4*(n-1)($sp)`, comprobación de null, `lw $a1, 0($a0)` (tabla), `lw $a1, 4*slot($a1)`, `jalr $a1`, `addiu $sp, $sp, 4*n` |

El despacho es dinámico: el `slot` sale de la clase estática del receptor, pero la tabla es la del objeto real, así que `a.hablar()` con `a: Animal` que guarda un `Perro` ejecuta `Perro.hablar`. Dentro de un método `this` nunca es null y no lleva comprobación.

**Punto flotante.** Un `float` es de precisión simple y sus 32 bits viajan por los registros generales. Para operar se pasan a `$f0` y `$f2` con `mtc1`, se calcula (`add.s`, `sub.s`, `mul.s`, `div.s`, `c.lt.s`...) y el resultado vuelve con `mfc1`. Un entero que llega a un lugar de tipo `float` (operando, variable, argumento o retorno) se convierte con `cvt.s.w`.

**Errores de ejecución.** División por cero, índice fuera de rango y acceso a null saltan a una rutina que deja el mensaje en `$a0` y continúa en `_throw`.

## 6. Biblioteca de ejecución

`backend/runtime.py` contiene rutinas MIPS que el código generado llama con `jal`: `_print_int`, `_print_str`, `_print_bool`, `_print_float`, `_alloc`, `_concat`, `_streq` y `_throw`. Reciben en `$a0` y `$a1`, devuelven en `$v0` y no modifican los registros `$t`. Solo se incluyen en el programa las que se usan.

## 7. Simulador

Hay dos formas de ejecutar el ensamblador:

- **Simulador incluido** (`backend/simulator.py`). Implementa las instrucciones, pseudoinstrucciones, directivas y llamadas al sistema (1, 2, 4, 9, 10, 11 y 17) que usa el backend. Lo usan `--run`, el IDE y las pruebas.
- **MARS 4.5.** `python src/compiscript/run_demo.py programa.cps --out=programa.asm` y después abrir el archivo en MARS, o `java -jar Mars4_5.jar nc programa.asm`.

Los programas de prueba dan la misma salida en ambos. Si existe `tools/mars/Mars4_5.jar`, la suite ejecuta además una comparación directa contra MARS.

## 8. Optimización por mirilla

`backend/peephole/` revisa el texto generado con ventanas de una o dos instrucciones y repite las reglas hasta que ninguna cambia nada. Se desactiva con `--no-peephole` (o desde el IDE). Una ventana nunca cruza una etiqueta y los comentarios no cuentan como instrucciones. Las rutinas de `runtime.py` también pasan por el optimizador.

| Transformación | Antes | Después | Módulo |
|---|---|---|---|
| Salto a la siguiente instrucción | `j L` y luego `L:` | solo `L:` | `flow.py` |
| Salto sobre salto | `beqz $t0, L1` / `j L2` / `L1:` | `bnez $t0, L2` / `L1:` | `flow.py` |
| Código inalcanzable | instrucciones entre `j` o `jr` y la siguiente etiqueta | se eliminan | `flow.py` |
| Saltos encadenados | `j L1` con `L1: j L2` | `j L2` | `flow.py` |
| Identidad algebraica | `addiu $t0, $t0, 0`, `move $t0, $t0` | se eliminan (con otro destino, `move`) | `local.py` |
| Carga redundante | `sw $t0, 24($fp)` y `lw $t0, 24($fp)` | se quita el `lw` (con otro registro, `move`) | `local.py` |
| Movimiento redundante | `move $t0, $v0` y `move $a0, $t0` con `$t0` muerto | `move $a0, $v0` | `local.py` |
| Ajustes de pila contiguos | `addiu $sp, $sp, -4` y `addiu $sp, $sp, 4` | se combinan o desaparecen | `local.py` |
| Reducción de fuerza | `li $t1, 8` y `mul $t0, $t0, $t1` | `sll $t0, $t0, 3` | `constants.py` |
| Comparación con inmediato | `li $t1, 3` y `slt $t0, $t0, $t1` | `slti $t0, $t0, 3` (`sle` usa `c + 1`) | `constants.py` |
| Aritmética con inmediato | `li $t1, 5` y `addu $t0, $t0, $t1` | `addiu $t0, $t0, 5` | `constants.py` |

**Cuándo un registro está muerto.** `analysis.is_dead` recorre el código hacia adelante: el registro está vivo si se lee antes de escribirse. Solo se contesta para `$t0` a `$t9`. El asignador vacía sus descriptores en cada etiqueta, salto y llamada a una función del programa (guarda antes lo que sigue vivo), así que un `$t` nunca lleva un valor a través de ellos. Las rutinas de biblioteca (`_nombre`) conservan los `$t`, por lo que la búsqueda continúa después de un `jal _print_int`. Cualquier otro registro se considera vivo.

Sobre los programas de `intermediate/valid` la mirilla quita cerca del 8 % de las instrucciones. `--asm` imprime al final cuántas veces se aplicó cada regla. Cada regla recibe la lista de `Line` y devuelve la lista nueva con su conteo; para agregar una, se define `RULES` en un módulo del paquete.

## 9. Supuestos y límites

1. La división y el módulo de enteros truncan hacia cero, como la instrucción `div` de MIPS.
2. Los enteros son de 32 bits con desborde silencioso.
3. `float` es de precisión simple. No hay módulo de `float` ni comprobación de división por cero en `float`.
4. No se convierte de entero a `float` al guardar en un elemento de arreglo o en un campo.
5. La memoria del montículo no se libera.
6. Si dos variables del mismo nombre conviven en ámbitos anidados y la interna se usa antes de su declaración, se toma la interna.

## 10. Pruebas

| Archivo | Qué cubre |
|---|---|
| `tests/compiscript/test_mips_programs.py` | Cada programa de `intermediate/valid` compilado a MIPS y ejecutado, con diez y con tres registros |
| `tests/compiscript/test_mips_backend.py` | Bloques, vida, cada regla del asignador, prólogo, llamadas, árbol de activación y simulador |
| `tests/compiscript/test_mips_classes.py` | Objetos, campos, constructores heredados, tablas de métodos, polimorfismo y acceso a null |
| `tests/compiscript/test_mips_features.py` | Arreglos, `float`, acción `compiscriptASM` del bridge y comparación contra MARS |
| `tests/compiscript/test_mips_peephole*.py` | Cada regla de mirilla con entrada y salida exactas, y la mirilla completa contra todos los programas |
| `tests/compiscript/test_run_demo.py` | Opciones de la línea de comandos |
