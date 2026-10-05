# Lenguaje intermedio de Compiscript (TAC)

Este documento describe el lenguaje intermedio que genera el compilador: su formato, el catalogo completo de instrucciones, como se traduce cada construccion de Compiscript, el algoritmo de temporales y los supuestos de diseno. La arquitectura general y la distribucion de memoria (registros de activacion) estan en [PRY2_IMPLEMENTACION.md](PRY2_IMPLEMENTACION.md).

## 1. Diseno

El lenguaje intermedio es **codigo de tres direcciones (TAC)** representado como **cuadruplas** `(op, arg1, arg2, result)`:

- Es lineal: una lista de instrucciones y etiquetas, sin estructura de bloques. El control de flujo se hace con `goto`, `if` e `ifFalse`.
- Cada instruccion tiene a lo sumo un operador y tres direcciones.
- **No tiene tipos.** Los tipos viven en la tabla de simbolos; el generador de assembler decide, a partir de ellos, si `a + b` es suma entera, suma flotante o concatenacion de cadenas.
- Cada instruccion tiene dos formas equivalentes: texto legible (`t0 = a + b`) y un objeto JSON `{op, arg1, arg2, result}`. El IDE y las pruebas usan ambas.

El TAC solo se genera si el programa **no tiene errores lexicos, sintacticos ni semanticos**. Si los hay, la accion `compiscriptTAC` devuelve los diagnosticos y `tac: []`; nunca entrega un resultado parcial.

### Pipeline

```text
codigo .cps ──ANTLR──> arbol sintactico ──SemanticAnalyzer──> tabla de simbolos + ambitos
                                                                      │
                          registros de activacion (symbols/layout.py) ◄┤
                                                                      ▼
                                                  TACGenerator ──> TAC + conteo de temporales
```

| Modulo | Responsabilidad |
|---|---|
| `semantic/analyzer.py` | Valida tipos y ambitos; guarda el ambito de cada nodo (`scope_of`). |
| `symbols/layout.py` | Ubicacion de cada simbolo, registros de activacion, clases. |
| `intermediate/generator.py` | Visitor del arbol que emite el TAC. |
| `intermediate/ir.py` | `Instruction`, `TACProgram`, `TempAllocator`. |
| `bridge_cli.py` | Accion `compiscriptTAC` que usa el IDE. |

## 2. Direcciones

Los operandos son cadenas. Una direccion es una de estas cosas:

| Tipo | Ejemplos | Notas |
|---|---|---|
| Variable | `x`, `total` | Variable global, local o parametro de la funcion actual. |
| Temporal | `t0`, `t1` | Generados por el compilador (seccion 5). |
| Literal | `3`, `1.5`, `"hola"`, `true`, `false`, `null` | Las cadenas conservan sus comillas. |
| Pseudo-variable | `this`, `exception` | `this` es el receptor dentro de un metodo; `exception` es el mensaje (una cadena) del error capturado por un `catch`. |
| Etiqueta | `while0`, `else3` | Destino de saltos; el contador es global al programa. |
| Funcion | `suma`, `outer.inner`, `Animal.hablar` | Nombre unico de la funcion (seccion 4.9). |
| Variable capturada | `up(1).total` | Variable de una funcion que encierra a la actual (seccion 4.10). |

## 3. Catalogo de instrucciones

`a`, `b`, `v` son direcciones; `r` es la direccion donde queda el resultado; `L` es una etiqueta. La columna "JSON" indica en que campo va cada operando.

### Datos

| Texto | `op` | JSON | Semantica |
|---|---|---|---|
| `r = a` | `copy` | `arg1=a, result=r` | Copia el valor. |
| `r = a op b` | el operador: `+ - * / % < <= > >= == !=` | `arg1=a, arg2=b, result=r` | Operacion binaria. `&&` y `||` no son instrucciones: se traducen con saltos (seccion 4.8). |
| `r = -a` | `neg` | `arg1=a, result=r` | Negacion aritmetica. |
| `r = !a` | `not` | `arg1=a, result=r` | Negacion logica. |
| `r = array e1, e2, ...` | `array` | `arg1="e1, e2, ...", result=r` | Crea un arreglo con esos elementos (`r = array` crea uno vacio). |
| `r = length a` | `length` | `arg1=a, result=r` | Cantidad de elementos del arreglo `a`. |
| `r = a[i]` | `index_load` | `arg1=a, arg2=i, result=r` | Lee un elemento. |
| `a[i] = v` | `index_store` | `arg1=i, arg2=v, result=a` | Escribe un elemento. |
| `r = o.f` | `member_load` | `arg1=o, arg2=f, result=r` | Lee un campo. |
| `o.f = v` | `member_store` | `arg1=f, arg2=v, result=o` | Escribe un campo. |
| `r = new C, n` | `new` | `arg1=C, arg2=n, result=r` | Crea un objeto de la clase `C` y ejecuta su constructor con los `n` `param` anteriores. El constructor es el de `C` o, si `C` no declara uno, el de su ancestro mas cercano. |
| `r = up(n).x` | `env_load` | `arg1=n, arg2=x, result=r` | Lee la variable `x` de un registro externo. |
| `up(n).x = v` | `env_store` | `arg1=v, arg2=n, result=x` | Escribe la variable `x` de un registro externo. |

### Control de flujo

| Texto | `op` | JSON | Semantica |
|---|---|---|---|
| `L:` | `label` | `result=L` | Define la etiqueta. |
| `goto L` | `goto` | `result=L` | Salto incondicional. |
| `if a goto L` | `if` | `arg1=a, result=L` | Salta si `a` es verdadero. |
| `ifFalse a goto L` | `ifFalse` | `arg1=a, result=L` | Salta si `a` es falso. |
| `try goto L` | `try` | `result=L` | Instala un manejador de errores de ejecucion (seccion 4.7): si una operacion falla mientras esta activo, la ejecucion sigue en `L` con el mensaje en `exception`. |
| `endtry` | `endtry` | | Desinstala el manejador mas reciente. Se emite al terminar el bloque `try` y tambien antes de cada `return`, `break` o `continue` que salga de el. |
| `halt` | `halt` | | Termina el programa. |

### Funciones

| Texto | `op` | JSON | Semantica |
|---|---|---|---|
| `function f` | `function` | `result=f` | Inicio del cuerpo de `f`. |
| `end function f` | `end_function` | `result=f` | Fin del cuerpo de `f`. |
| `param_decl x` | `param_decl` | `arg1=x` | Declara un parametro formal (en metodos, `this` va primero). |
| `param a` | `param` | `arg1=a` | Empuja un argumento real; se emiten todos antes del `call`. |
| `link n` | `link` | `arg1=n` | Fija de donde sale el `access_link` de la funcion anidada que se va a llamar (seccion 4.10). |
| `r = call f, n` | `call_result` | `arg1=f, arg2=n, result=r` | Llama a `f` con los `n` `param` anteriores. |
| `r = invoke o.m, n` | `invoke` | `arg1="o.m", arg2=n, result=r` | Llama al metodo `m` del objeto `o`, resuelto en ejecucion segun su clase. `n` cuenta el receptor, que es el primer `param`. |
| `return` / `return a` | `return` | `arg1=a` (opcional) | Retorna al llamador. |
| `print a` | `print` | `arg1=a` | Imprime el valor. |

Una llamada usada como sentencia (`hola();`) tambien emite `call_result`; el temporal se descarta.

## 4. Traduccion de cada construccion

Todos los ejemplos son la salida real del compilador.

### 4.1 Programa

El codigo de nivel superior se emite primero y termina en `halt`. Los cuerpos de funciones y metodos se emiten **despues**, de modo que la ejecucion secuencial nunca entra en ellos.

```text
function hola() { print(1); }        t0 = call hola, 0
hola();                              halt
                                     function hola
                                     print 1
                                     end function hola
```

### 4.2 Expresiones y temporales

Cada operacion produce un temporal; los operandos se evaluan de izquierda a derecha respetando la precedencia.

```text
let r: integer = (a + b) * (a - c) + b * c;

t0 = a + b
t1 = a - c
t2 = t0 * t1
t1 = b * c          <- t1 se recicla: (a - c) ya fue consumido
t0 = t2 + t1        <- t0 tambien
r = t0
```

Operadores unarios: `-a` es `neg` y `!b` es `not`. Los literales y las variables no necesitan temporal: se usan directamente como operandos.

### 4.3 Asignaciones

| Compiscript | TAC |
|---|---|
| `x = e;` | `x = <e>` |
| `xs[i] = v;` | `xs[i] = v` (`index_store`) |
| `o.campo = v;` | `o.campo = v` (`member_store`) |
| `let x = e;` / `const x = e;` | `x = <e>` (sin inicializador no emite nada) |
| `m[1][0] = 9;` | `t2 = m[1]` y despues `t2[0] = 9` |

### 4.4 Condicional `if`

```text
if (x > 1) { print(1); } else { print(2); }

t0 = x > 1
ifFalse t0 goto else0
print 1
goto endif1
else0:
print 2
endif1:
```

Sin `else` no hay `goto endif` ni segunda etiqueta: `ifFalse` salta directamente a `else0`.

### 4.5 Bucles

**`while`.** `continue` salta al inicio (reevalua la condicion); `break` salta a `endwhile`.

```text
while (i < 5) { i = i + 1; if (i == 2) { continue; } if (i == 4) { break; } print(i); }

while0:
t0 = i < 5
ifFalse t0 goto endwhile1
t0 = i + 1
i = t0
t0 = i == 2
ifFalse t0 goto else2
goto while0            <- continue
else2:
t0 = i == 4
ifFalse t0 goto else4
goto endwhile1         <- break
else4:
print i
goto while0
endwhile1:
```

**`do-while`.** `continue` salta a `docond`, de modo que **si evalua la condicion**.

```text
do { i = i + 1; if (i == 1) { continue; } } while (i < 3);

do0:
t0 = i + 1
i = t0
t0 = i == 1
ifFalse t0 goto else3
goto docond2           <- continue
else3:
docond2:
t0 = i < 3
if t0 goto do0
enddo1:
```

**`for`.** El inicializador va antes del bucle y `continue` salta a `increment`.

```text
for (let i: integer = 0; i < 3; i = i + 1) { print(i); }

i = 0
for0:
t0 = i < 3
ifFalse t0 goto endfor1
print i
increment2:
t0 = i + 1
i = t0
goto for0
endfor1:
```

**`foreach`.** Recorre por indice con dos temporales ocultos (el indice y la longitud, que se calcula una sola vez); termina cuando el indice llega a la longitud. `continue` salta a `foreachnext`, que avanza el indice.

```text
foreach (v in xs) { if (v == 2) { continue; } print(v); }

t0 = 0                 <- indice oculto
t1 = length xs         <- longitud, calculada una vez
foreach0:
t2 = t0 < t1
ifFalse t2 goto endforeach1
t2 = xs[t0]
v = t2
t2 = v == 2
ifFalse t2 goto else3
goto foreachnext2      <- continue
else3:
print v
foreachnext2:
t2 = t0 + 1
t0 = t2
goto foreach0
endforeach1:
```

### 4.6 `switch`

Cada `case` compara y salta; si ninguno coincide se salta a `default` (o al final). Los cuerpos se emiten en orden y **caen al siguiente caso** si no hay salida, como muestra `docs/Compiscript.md`.

```text
switch (x) { case 1: print(1); case 2: print(2); default: print(0); }

t0 = x == 1
if t0 goto case1
t0 = x == 2
if t0 goto case2
goto default3
case1:
print 1
case2:
print 2
default3:
print 0
endswitch0:
```

### 4.7 `try / catch` y errores de ejecucion

Compiscript no tiene `throw`: lo que activa un `catch` son los **errores de ejecucion**. Estas operaciones los producen, y no necesitan instrucciones de comprobacion aparte, porque el error es parte de su semantica:

| Operacion | Condicion de error | Mensaje en `exception` |
|---|---|---|
| `r = a / b`, `r = a % b` | `b` es cero | `division por cero` |
| `r = a[i]`, `a[i] = v` | `i < 0` o `i >= length a` | `indice fuera de rango` |
| `r = o.f`, `o.f = v`, `invoke o.m`, `r = a[i]`, `r = length a` | `o` / `a` es `null` | `acceso a null` |

El `try` se traduce con un manejador instalado:

```text
try { print(1 / cero); } catch (e) { print(e); }

try goto catch0        <- instala el manejador
t0 = 1 / cero          <- si cero es 0: salta a catch0 con exception = "division por cero"
print t0
endtry                 <- fin normal del bloque: desinstala el manejador
goto endtry1
catch0:
e = exception          <- el catch siempre empieza leyendo el mensaje
print e
endtry1:
```

**Semantica del manejador.**

1. `try goto L` apila `L` en la pila de manejadores **del registro de activacion actual**.
2. Cuando una operacion falla, se busca un manejador: si el registro actual tiene uno, se desapila, se asigna el mensaje a `exception` y se salta a su etiqueta. Si no, se **desenrolla**: se descarta el registro (como si hiciera `return`) y se busca en el del llamador, y asi hasta `main`. Sin ningun manejador el programa termina con el error.
3. El manejador se desapila al activarse, asi que un error dentro del propio `catch` no lo captura el mismo `try`; lo atiende el `try` de afuera, si lo hay.
4. `endtry` desapila el manejador cuando el bloque termina sin error. Para que un `try` nunca deje un manejador instalado, el generador tambien lo emite **antes de cada `return`, `break` o `continue` que salga del bloque** (una vez por cada `try` que se abandona); en el `return` el valor se calcula antes, dentro del `try`.

```text
function seguro(d: integer): integer { try { return 10 / d; } catch (e) { return -1; } }

function seguro
param_decl d
try goto catch0
t0 = 10 / d            <- el valor se calcula con el manejador activo
endtry                 <- se desinstala antes de salir
return t0
endtry
goto endtry1
catch0:
e = exception
t0 = -1
return t0
endtry1:
end function seguro
```

Con `try` anidados, un `return` interior emite un `endtry` por cada `try` que abandona; dentro de un `catch` ya no cuenta el `try` que lo origino (su manejador se consumio).

### 4.8 Ternario y logicos

```text
let m: integer = a < b ? a : b;

t0 = a < b
ifFalse t0 goto false0
t1 = a
goto endternary1
false0:
t1 = b
endternary1:
m = t1
```

**`&&` y `||` hacen cortocircuito.** El resultado vive en un temporal y el segundo operando solo se evalua si el primero no decide el valor: `a || b` salta al final (`if t0 goto orend0`) cuando `a` es verdadero, y `a && b` cuando `a` es falso (`ifFalse t0 goto andend0`). Asi `d != 0 && 10 / d > 1` no divide por cero y `false && tocar()` no ejecuta `tocar()`.

```text
let r: boolean = a || b;

t0 = a
if t0 goto orend0      <- a es verdadero: el resultado ya esta decidido
t0 = b
orend0:
r = t0
```

Una cadena como `a && b || c` se traduce por niveles, con la precedencia normal (`&&` primero):

```text
t1 = a
ifFalse t1 goto andend1
t1 = b
andend1:
t0 = t1
if t0 goto orend0
t0 = c
orend0:
r = t0
```

### 4.9 Funciones y llamadas

```text
function suma(a: integer, b: integer): integer { return a + b; }
let r: integer = suma(1, 2);

param 1                    <- los argumentos primero, de izquierda a derecha
param 2
t0 = call suma, 2
r = t0
halt
function suma
param_decl a
param_decl b
t0 = a + b
return t0
end function suma
```

Un argumento que es otra llamada se evalua completo antes de empezar a emitir los `param` de la externa, asi que los `param` nunca quedan intercalados.

**Nombres de funcion.** Cada funcion tiene un nombre unico: `f` si es de nivel superior, `outer.inner` si esta anidada, `Clase.metodo` si es un metodo. Dos funciones anidadas homonimas en funciones distintas (`a.inner` y `b.inner`) no chocan. Si una misma funcion declara dos con el mismo nombre en bloques distintos (por ejemplo, en el `if` y en el `else`), la segunda recibe el sufijo `#2` (`f.h` y `f.h#2`); cada llamada usa el nombre de la que le corresponde.

### 4.10 Closures (funciones anidadas)

Una funcion anidada puede leer y escribir variables de las que la encierran. Cada variable vive en un registro de activacion con un nivel lexico; si la variable pertenece a un registro externo se accede con `up(n)`, donde `n` es cuantos registros hay que subir por `access_link`.

```text
function acumular(inicio: integer, paso: integer): integer {
  let actual: integer = inicio;
  function siguiente(incremento: integer): integer { return actual + incremento; }
  return siguiente(paso);
}

function acumular
param_decl inicio
param_decl paso
actual = inicio
param paso
link 0                           <- el access_link de siguiente es el registro de acumular
t0 = call acumular.siguiente, 1
return t0
end function acumular
function acumular.siguiente
param_decl incremento
t0 = up(1).actual                <- 'actual' vive un registro mas arriba
t1 = t0 + incremento
return t1
end function acumular.siguiente
```

`link n` se emite justo antes de llamar a una funcion anidada. Con `L(f)` el nivel lexico de `f`: `n = L(llamador) - (L(callee) - 1)`. Las variables propias, los parametros y las globales se nombran directamente, sin `up`.

### 4.11 Arreglos

```text
let m: integer[][] = [[1, 2], [3, 4]]; m[1][0] = 9; print(m[0][1]);

t0 = array 1, 2
t1 = array 3, 4
t2 = array t0, t1
m = t2
t2 = m[1]
t2[0] = 9
t2 = m[0]
t1 = t2[1]
print t1
```

### 4.12 Clases y objetos

```text
class A {
  let n: integer = 1;
  function constructor(k: integer) { this.n = k; }
  function get(): integer { return this.n; }
}
let o: A = new A(5);
o.n = 7;
print(o.get());

param 5
t0 = new A, 1
o = t0
o.n = 7
param o                       <- el receptor viaja como primer param
t0 = invoke o.get, 1
print t0
halt
function A.constructor
param_decl this
param_decl k
this.n = 1                    <- inicializador del campo, antes del cuerpo
this.n = k
end function A.constructor
function A.get
param_decl this
t0 = this.n
return t0
end function A.get
```

- Los metodos se llaman `Clase.metodo` y reciben `this` como primer parametro.
- Los inicializadores de campos (`let n: integer = 1;`) se emiten al inicio del constructor; si la clase no declara constructor se sintetiza uno. El constructor de una subclase empieza por los inicializadores de sus superclases (de la raiz hacia abajo) y despues los propios.
- `o.metodo(args)` emite `param o`, los `param` de los argumentos e `invoke o.metodo, n+1`. El metodo concreto se elige en ejecucion con la tabla de metodos de la clase del objeto (ver `PRY2_IMPLEMENTACION.md`).
- **Polimorfismo.** Una variable de tipo `Animal` puede guardar un `Perro` (ver `Compiscript_Diseno_Semantico.md`). Como `invoke` decide por la clase del objeto y no por el tipo de la variable, `a.hablar()` ejecuta `Perro.hablar` aunque `a` este declarada como `Animal`; el TAC es el mismo que para cualquier otra llamada a metodo.

## 5. Temporales: asignacion y reciclaje

`TempAllocator` (en `intermediate/ir.py`) lleva una lista de temporales libres y un contador.

- **`acquire()`**: devuelve un temporal libre; si no hay, crea el siguiente (`t0`, `t1`, ...). Se salta cualquier nombre que ya sea un identificador del programa fuente, de modo que una variable de usuario llamada `t1` nunca choca con un temporal.
- **`release(t)`**: devuelve `t` a la lista de libres, **solo si el mismo allocator lo entrego** (una variable de usuario `t1` nunca se recicla).

El generador libera un temporal en cuanto la instruccion que lo consume ya fue emitida: los dos operandos de una operacion se liberan despues de emitir la operacion, y el resultado queda vivo hasta que su consumidor lo libera.

Cada funcion usa **su propio allocator**, asi que sus temporales empiezan otra vez en `t0`. Al terminar, el generador reporta cuantos temporales distintos uso cada una (`temp_counts`) y ese numero entra en el tamano de su registro de activacion.

Ejemplo de la seccion 4.2: la expresion `(a + b) * (a - c) + b * c` produce 5 resultados intermedios pero solo usa 3 temporales (`t0`, `t1`, `t2`).

## 6. Tabla de simbolos y memoria

Despues del analisis semantico, `symbols/layout.py` anota cada simbolo con `storage` (`global`, `local`, `param` o `field`), `offset` y `size` en bytes y `frame` (registro que lo contiene), y calcula el registro de activacion de cada funcion, el area estatica y el layout de cada clase. El detalle, con el formato del frame, esta en [PRY2_IMPLEMENTACION.md](PRY2_IMPLEMENTACION.md). La accion `compiscriptTAC` devuelve esa informacion como `layout` (JSON) y `layoutText` (texto).

## 7. Supuestos y decisiones de diseno

1. **TAC sin tipos.** Las operaciones no distinguen entero de flotante; el assembler lo decide con la tabla de simbolos. El estrechamiento `integer -> float` no genera una instruccion de conversion.
2. **Cortocircuito.** `&&` y `||` no evaluan el segundo operando si el primero ya decide el resultado, como en TypeScript. Los operandos son siempre booleanos (lo garantiza el analisis semantico), asi que el resultado es el del ultimo operando evaluado.
3. **Orden de evaluacion de izquierda a derecha**, con los argumentos de una llamada evaluados por completo antes de emitir los `param`.
4. **Caida entre casos en `switch`.** No hay `break` dentro de un `switch` en el lenguaje (el analizador semantico solo acepta `break` en bucles).
5. **Metodos resueltos en ejecucion** con `invoke` (despacho dinamico, base del polimorfismo); las llamadas a funciones usan `call` con el nombre ya resuelto.
6. **Funciones elevadas.** Ningun cuerpo de funcion aparece dentro de otro; el anidamiento se conserva en el nombre (`outer.inner`) y en los niveles lexicos.
7. **Las funciones no son valores.** No hay closures que sobrevivan a la funcion que las crea, asi que basta con `access_link`; no se captura ningun entorno.
8. **Nombres de variable sin calificar.** Dos variables con el mismo nombre en bloques anidados aparecen igual en el TAC; la distincion esta en la tabla de simbolos.
9. **Los errores detienen la generacion.** Con cualquier error no se emite TAC ni `layout`.
10. **Errores de ejecucion como parte de la semantica.** La division, el indexado y el acceso a miembros fallan por si mismos (seccion 4.7); el TAC no lleva comprobaciones explicitas y el assembler debe implementarlas en esas operaciones. El mensaje de `exception` es una cadena, que es el tipo que el analizador semantico da a la variable del `catch`.
11. **Pila de manejadores por registro.** Cada registro de activacion lleva la pila de sus `try` activos; el desenrollado descarta registros hasta encontrar un manejador.

## 8. Limitaciones conocidas

- No se emite `link` para llamar a metodos de una clase declarada dentro de una funcion, porque `invoke` resuelve el metodo en ejecucion.
- Un constructor de una subclase no invoca al de la superclase (la gramatica no tiene `super`): el cuerpo del constructor de la superclase solo se ejecuta si la subclase no declara el suyo. Los inicializadores de campos de las superclases (`let x: integer = 5;`) si se ejecutan siempre: se emiten, de la raiz hacia abajo, al inicio del constructor de la subclase.

## 9. Como ejecutarlo y probarlo

**Desde el IDE.** Abrir un `.cps`, elegir el workflow **Compiscript** y ejecutar **Codigo Intermedio**. El resultado incluye `tac`, `text`, `symbols`, `layout` y `layoutText`.

**Desde Python.**

```bash
python -m pytest tests/compiscript/ -q          # todas las pruebas de Compiscript
python -m pytest tests/compiscript/test_tac_generation.py -q
```

```python
from bridge_cli import _run_action
r = _run_action({"action": "compiscriptTAC", "cpsSource": "let x: integer = 1 + 2 * 3;"})
print(r["text"])
```

### Mapa de pruebas

| Archivo | Que cubre |
|---|---|
| `tests/compiscript/test_try_catch.py` | Errores de ejecucion sin capturar (terminan el programa), manejadores que deben quedar desinstalados tras un error, un `return`, un `break` o un `continue`, `endtry` antes del `return` con el valor ya calculado, y que cada `try` tenga su `catch` que lee `exception`. |
| `tests/compiscript/test_intermediate_programs.py` | **84 programas validos** (`intermediate/valid/*.cps`; los `rubrica_*.cps` agrupan casos por criterio de evaluacion: declaraciones, aritmetica, logicas con cortocircuito, arreglos, control, funciones, recursividad, clases, herencia y try/catch) que se traducen a TAC, se ejecutan con el interprete de referencia y se comparan con las lineas `// expect:` del propio archivo; **10 programas invalidos** (`intermediate/invalid/*.cps`, `// error: <codigo>`) que no deben generar TAC ni `layout`. Tambien verifica que el layout sea consistente con el TAC (funciones con registro, temporales dentro de lo reservado, `halt` antes de los cuerpos). |
| `tests/compiscript/tac_interpreter.py` | Interprete de referencia del TAC (solo para pruebas): ejecuta `call`, `invoke`, `new`, `up(n)`, `link`, arreglos y saltos, y falla si un programa no termina. Comprueba el *comportamiento* del TAC, no solo su texto. |
| `tests/compiscript/test_bridge_e2e.py` | **End-to-end del bridge**, como lo usa el IDE: lanza `bridge_cli.py` como subproceso, escribe el payload por stdin y decodifica stdout como UTF-8. Recorre el pipeline en el orden del IDE (diagnosticos, simbolos, arbol, TAC) con `cpsPath` y `cpsSource`, rutas con espacios y acentos, independencia del directorio de trabajo, errores del programa y del bridge, texto Unicode, y que las respuestas cumplan el contrato de `desktop-app/src/types.ts`. |
| `tests/compiscript/test_tac_snapshots.py` | Salida exacta del TAC de cada construccion (expresiones con reciclaje, `if`, `while`, `do-while`, `for`, `foreach`, `switch`, `try/catch`, ternario, funciones, closures, matrices, clases). |
| `tests/compiscript/test_tac_ir_unit.py` | `TempAllocator` (consecutivos, reciclaje LIFO, doble liberacion, nombres reservados, conteo) y formato de texto/JSON de cada instruccion. |
| `tests/compiscript/test_tac_generation.py` | Regresiones puntuales: `new` con argumentos, metodos e `invoke`, asignacion a elementos, funciones elevadas, closures (`up`, `link`), nombres de funciones, `continue` en `foreach` y `do-while`, condicion de salida de `foreach`, cuadruplas. |
| `tests/compiscript/test_class_hierarchy.py` | Subtipado de clases: relacion de herencia, ancestro comun, asignacion, argumentos, retorno, campos, arreglos, ternario e igualdad, casos invalidos y aislamiento entre analisis. |
| `tests/compiscript/test_activation_records.py` | Area estatica, tamanos y alineacion, registros de funcion y de metodo, bloques hermanos, niveles lexicos, layout de clases y herencia, constructor sintetizado, ciclos de herencia. |
| `tests/compiscript/test_semantic_rules.py` y `test_*_unit.py` | Fase semantica que precede al TAC (casos validos e invalidos en `tests/compiscript/*/valid` y `*/invalid`). |

Para agregar un caso basta con crear un `.cps` en `intermediate/valid/` con sus lineas `// expect:` (o en `intermediate/invalid/` con `// error: <codigo>`, `syntax` o `any`); las pruebas lo recogen solas.
