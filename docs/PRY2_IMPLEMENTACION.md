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

## Temporales

`TempAllocator` entrega nombres `t0`, `t1`, etc. Cuando una expresion deja de necesitar un temporal, el visitor lo devuelve al allocator. La siguiente expresion puede reutilizarlo, manteniendo acotado el numero de temporales vivos sin cambiar el orden de evaluacion.

## Tabla de simbolos y registros de activacion

Cada simbolo conserva su tipo, ambito y posicion fuente. Al insertarse en un `Scope`, recibe un `offset`, el nombre del `frame` y una ubicacion serializada como `scope[offset]`. Esto prepara la tabla para asociar variables, parametros y temporales con registros de activacion durante la futura generacion de assembler.

## Uso desde el IDE

Abra un archivo `.cps`, seleccione el workflow **Compiscript** y ejecute **Codigo Intermedio**. El resultado JSON contiene `syntaxErrors`, `diagnostics`, `tac`, `text` y la tabla `symbols`. El panel de resultados conserva tambien el texto TAC legible para inspeccion y presentacion.

## Pruebas

```bash
python -m pytest tests/compiscript/test_tac_generation.py -q
python -m pytest -q
```