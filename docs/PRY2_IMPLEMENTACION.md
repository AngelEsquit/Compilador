# Proyecto 2: representacion intermedia

## Arquitectura

El pipeline de Compiscript conserva tres pasos separados:

1. ANTLR tokeniza y construye el arbol sintactico.
2. `SemanticAnalyzer` valida tipos, nombres, ambitos y control de flujo.
3. `TACGenerator` visita el mismo arbol y produce codigo de tres direcciones.

El bridge expone la accion `compiscriptTAC`. Esta accion siempre ejecuta el analisis semantico antes de traducir. Si hay errores lexicos, sintacticos o semanticos, devuelve los diagnosticos y `tac: []`; nunca entrega una representacion parcial.

## Formato TAC

La unidad basica es `Instruction(op, arg1, arg2, result)`. La salida de texto usa las formas clasicas:

```text
t0 = b * c
t1 = a + t0
ifFalse t1 goto else0
goto while0
param x
t2 = call suma, 1
return t2
```

Las operaciones soportadas incluyen copias, operaciones unarias y binarias, etiquetas, saltos condicionales e incondicionales, llamadas, retornos, impresion, arreglos, acceso indexado, acceso a miembros, `new` y bloques de funciones. Las instrucciones tambien se serializan como JSON para el IDE.

### Convenciones de traduccion

- **Programa principal y funciones.** El codigo de nivel superior termina en `halt`; los cuerpos de funciones y metodos se emiten despues, de modo que la ejecucion secuencial nunca entra en ellos. Las funciones anidadas se elevan a nivel superior (conservan su nombre simple).
- **Metodos.** Se emiten como `function Clase.metodo` con `param_decl this` como primer parametro. El constructor es `Clase.constructor`; los inicializadores de campos (`let n: integer = 5;`) se emiten al inicio de ese constructor (se sintetiza uno si la clase no lo declara).
- **Llamadas.** `f(a, b)` emite `param a`, `param b` y `t = call f, 2`. `new C(a)` emite `param a` y `t = new C, 1`. `o.m(a)` emite `param o`, `param a` y `t = invoke o.m, 2`: el receptor viaja como `this` y el metodo se resuelve en ejecucion segun la clase del objeto.
- **Asignaciones.** `x = v` es `copy`; `xs[i] = v` es `xs[i] = v` (`index_store`); `o.c = v` es `o.c = v` (`member_store`).
- **`switch`.** Sigue la semantica de caida al siguiente caso descrita en `Compiscript.md`.

## Temporales

`TempAllocator` entrega nombres `t0`, `t1`, etc. Cuando una expresion deja de necesitar un temporal, el visitor lo devuelve al allocator. La siguiente expresion puede reutilizarlo, manteniendo acotado el numero de temporales vivos sin cambiar el orden de evaluacion.

El allocator solo recicla nombres que el mismo entrego y nunca usa un nombre que aparezca como identificador en el programa fuente, asi que una variable de usuario llamada `t1` no se corrompe. Cada funcion usa un allocator propio: sus temporales empiezan otra vez en `t0`.

## Tabla de simbolos y registros de activacion

`symbols/layout.py` recorre el arbol de ambitos que deja el analisis semantico (`compute_layout`) y fija la ubicacion de cada simbolo: `storage` (`global`, `local`, `param` o `field`), `offset` y `size` en bytes, y `frame` (nombre del registro que lo contiene). Despues de generar el TAC, `Layout.apply_temps` agrega cuantos temporales uso cada funcion.

### Tamanos

`integer` 4 bytes, `boolean` 1, `float` 8; `string`, arreglos y objetos son referencias de 8. Cada variable se alinea a su propio tamano.

### Registro de activacion

Offsets en bytes respecto a `fp`, creciendo hacia arriba:

```text
fp+0    saved_fp         enlace dinamico (fp del llamador)
fp+8    return_address   direccion de retorno
fp+16   access_link      enlace estatico (fp de la funcion que encierra lexicamente)
fp+24   parametros       (`this` primero en los metodos)
        variables locales
        temporales       (8 bytes cada uno)
```

- Los bloques hermanos (`then`/`else`, cuerpos de bucles) **reutilizan el mismo espacio**; el frame solo cubre la ruta mas profunda.
- `level` es la profundidad lexica (`main` = 0, funcion de nivel superior = 1, anidada = nivel de la que la encierra + 1) y `parent` el registro que la encierra: sirven para seguir `access_link` y alcanzar variables capturadas por una funcion anidada.
- `main` es el registro del codigo de nivel superior. Guarda sus temporales y las variables declaradas en bloques o bucles de nivel superior.
- Las variables globales viven en un **area estatica** (`dataArea`), no en `main`.
- `frameSize` = control + parametros + locales + temporales, redondeado a 8.

### Clases

Un objeto tiene 8 bytes de cabecera (puntero a la clase) y despues sus campos. Una subclase conserva los offsets de los campos heredados y agrega los suyos a continuacion. La tabla de metodos asigna a cada metodo un indice estable; una sobrescritura reemplaza la etiqueta (`B.m`) en el mismo indice, por lo que `invoke o.m` se resuelve en ejecucion con `vtable[indice]`. Los constructores no entran en la tabla.

### Ejemplo

```text
function outer(a: integer, b: float): integer {
  let x: integer = a + 1;
  if (x > 0) { let y: integer = 2; let z: float = 1.5; } else { let w: boolean = true; }
  ...
}

registro de activacion outer (function, nivel 1, dentro de main)
  fp+0    saved_fp (8 bytes)
  fp+8    return_address (8 bytes)
  fp+16   access_link (8 bytes)
  fp+24   a: integer [param] (4 bytes)
  fp+32   b: float [param] (8 bytes)
  fp+40   x: integer [local] (4 bytes)
  fp+44   y: integer [local] (4 bytes)     <- y y w comparten el offset 44
  fp+48   z: float [local] (8 bytes)
  fp+44   w: boolean [local] (1 bytes)
  fp+56   temporales: 2 x 8 bytes
  tamano del frame: 72 bytes
```

### Salida

La accion `compiscriptTAC` devuelve `layout` (JSON) y `layoutText` (el resumen de arriba); `compiscriptSymbols` devuelve `layout` sin conteo de temporales. Los simbolos de `symbols` / `scope` ya llevan `storage`, `offset`, `size` y `frame`.

## Uso desde el IDE

Abra un archivo `.cps`, seleccione el workflow **Compiscript** y ejecute **Codigo Intermedio**. El resultado JSON contiene `syntaxErrors`, `diagnostics`, `tac`, `text`, la tabla `symbols` y la distribucion de memoria (`layout` y `layoutText`). El panel de resultados conserva tambien el texto TAC legible para inspeccion y presentacion.

## Pruebas

```bash
python -m pytest tests/compiscript/test_tac_generation.py -q
python -m pytest -q
```