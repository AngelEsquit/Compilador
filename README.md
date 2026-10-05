# Compilador: YALex Studio + Compiscript

Repositorio de Diseño de Lenguajes de Programación (UVG). Contiene dos fases:

| Fase | Qué hace | Dónde |
|---|---|---|
| **YALex / YAPar** (entregada) | Genera lexers desde `.yal` y parsers SLR desde `.yalp`, sin librerías de regex ni de autómatas | [src/yalex_parser/](src/yalex_parser/), [src/yapar_generator/](src/yapar_generator/) |
| **Compiscript** | Compilador de Compiscript sobre ANTLR: análisis semántico (tipos, ámbitos, clases) y **generación de código intermedio** de tres direcciones, con tabla de símbolos y registros de activación | [src/compiscript/](src/compiscript/) |

Ambas comparten el IDE de escritorio en [src/desktop-app/](src/desktop-app/) (Tauri + React).

## Integrantes

- Javier España #23361
- Ángel Esquit #23221
- Roberto Barreda #23354

## Requisitos

- Python 3.10 o superior.
- Para Compiscript: `pip install -r src/compiscript/requirements.txt`.
- Para el IDE: Node.js 18+, toolchain de Rust, y Python en el PATH.
  - Windows: Visual Studio Build Tools (MSVC) y WebView2 Runtime.
  - Linux: `build-essential pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev patchelf libssl-dev`.

## Compiscript: de código fuente a código intermedio

```text
archivo .cps ─ANTLR→ árbol ─análisis semántico→ tabla de símbolos ─→ registros de activación
                                                                              │
                                              generador de TAC ◄──────────────┘
                                                    │
                                          código de tres direcciones
```

El código intermedio solo se genera si el programa no tiene errores léxicos, sintácticos ni semánticos.

### Desde la línea de comandos

```bash
python src/compiscript/run_demo.py programa.cps            # diagnósticos
python src/compiscript/run_demo.py programa.cps --tac      # + código intermedio
python src/compiscript/run_demo.py programa.cps --layout   # + registros de activación
python src/compiscript/run_demo.py programa.cps --tac --layout
```

Ejemplo:

```text
function sumar(a: integer, b: integer): integer {
  return a + b;
}
let r: integer = sumar(1, 2) * 3;
print(r);
```

```text
param 1
param 2
t0 = call sumar, 2
t1 = t0 * 3
r = t1
print r
halt
function sumar
param_decl a
param_decl b
t0 = a + b
return t0
end function sumar
```

Hay programas listos en [tests/compiscript/samples/](tests/compiscript/samples/) y en [tests/compiscript/intermediate/valid/](tests/compiscript/intermediate/valid/).

### Desde el IDE

1. Abrir la carpeta del proyecto y un archivo `.cps`.
2. Elegir el workflow **Compiscript**.
3. Ejecutar **Diagnósticos**, **Tabla de Símbolos**, **Árbol Sintáctico** o **Código Intermedio**. El resultado de **Código Intermedio** incluye las instrucciones (`tac`, `text`), la tabla de símbolos con sus ubicaciones de memoria (`symbols`) y los registros de activación (`layout`, `layoutText`), y se muestra en tres pestañas (el botón **JSON** de la barra de resultados conserva la salida cruda):
   - **Código**: el TAC numerado y coloreado, agrupado por función; los saltos y las llamadas son enlaces a su destino.
   - **Registros de activación**: un diagrama por función con las zonas del frame (control, parámetros, locales, temporales y relleno de alineación), el área estática de las globales y la distribución de cada clase con su tabla de métodos.
   - **Temporales**: una barra por cada valor intermedio, desde que se calcula hasta su último uso; varias barras en la misma fila muestran que el temporal se reutilizó.

```bash
cd src/desktop-app && npm install && npm run tauri:nowatch
```

### Otras herramientas

```bash
# CLI de YALex/YAPar (menú interactivo)
python src/main.py

# Generar lexer y parser autónomos
python src/bridge_yapar.py gen-lexer  examples/medium/lang_medium.yal  -o output/lexer.py
python src/bridge_yapar.py gen-parser examples/medium/lang_medium.yalp -o output/parser.py
```

## Pruebas

```bash
python -m pytest                      # todo (YALex/YAPar + Compiscript)
python -m pytest tests/compiscript/   # solo Compiscript (semántica + código intermedio)
./run_tests.sh                        # todo
```

La suite de Compiscript incluye, además de las pruebas semánticas:

- **Programas completos** en `tests/compiscript/intermediate/valid/*.cps`: se traducen a TAC, se ejecutan con un intérprete de referencia (`tests/compiscript/tac_interpreter.py`) y se compara lo que imprimen con las líneas `// expect:` del propio archivo.
- **Casos inválidos** en `tests/compiscript/intermediate/invalid/*.cps` (`// error: <código>`): no deben generar código.
- **Snapshots** exactos del TAC de cada construcción, pruebas unitarias del allocator de temporales, de los registros de activación y del subtipado de clases.
- **End-to-end del bridge** (`test_bridge_e2e.py`): ejecuta `bridge_cli.py` como lo hace el IDE (JSON por stdin, JSON UTF-8 por stdout) y valida el pipeline completo y el contrato con `types.ts`.

Para agregar un caso basta con crear un `.cps` en esas carpetas; las pruebas lo recogen solas.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/Lenguaje_Intermedio.md](docs/Lenguaje_Intermedio.md) | El lenguaje intermedio: catálogo de instrucciones, traducción de cada construcción con ejemplos, algoritmo de temporales, supuestos y limitaciones |
| [docs/PRY2_IMPLEMENTACION.md](docs/PRY2_IMPLEMENTACION.md) | Arquitectura de la fase intermedia, tabla de símbolos, registros de activación y clases |
| [docs/Compiscript_Diseno_Semantico.md](docs/Compiscript_Diseno_Semantico.md) | Diseño del análisis semántico, sistema de tipos y subtipado de clases |
| [docs/Compiscript.md](docs/Compiscript.md) | Descripción del lenguaje Compiscript |
| [src/compiscript/README.md](src/compiscript/README.md) | Mapa de módulos de Compiscript |

## Estructura

```text
src/compiscript/             Compilador de Compiscript
  grammar/                   Gramática ANTLR y parser generado
  typesystem/                Tipos, asignabilidad y jerarquía de clases
  symbols/                   Tabla de símbolos, ámbitos y registros de activación (layout.py)
  semantic/                  Análisis semántico (reglas de tipos, ámbitos, clases, funciones, arreglos)
  intermediate/              Código de tres direcciones: instrucciones, temporales y generador
src/yalex_parser/            Generador de lexers (método directo, minimización Hopcroft)
src/yapar_generator/         Generador de parsers SLR (items LR(0), FIRST/FOLLOW)
src/desktop-app/             IDE de escritorio (Tauri + React + Monaco)
src/bridge_cli.py            Bridge JSON entre el IDE y el motor Python
docs/                        Documentación (enunciado, diseño semántico, lenguaje intermedio)
examples/                    Casos de prueba de YALex/YAPar (low / medium / high)
tests/                       Suites de ambas fases
```

## Problemas comunes

- **Windows: "Una directiva de Control de aplicaciones bloqueó este archivo" (error 4551) al ejecutar el IDE.** *Smart App Control* bloquea los ejecutables sin firmar que compila Rust. Hay que desactivarlo en Seguridad de Windows → Control de aplicaciones y del navegador → Configuración de Smart App Control. Es irreversible sin reinstalar Windows. La CLI de Python (`run_demo.py`) y las pruebas no lo necesitan.
- **Windows: "Python was not found; run without arguments to install from the Microsoft Store" (código 9009) al ejecutar una acción del IDE.** Windows trae alias falsos `python.exe` y `python3.exe` (en `WindowsApps`) que solo abren la Tienda. El IDE ya los descarta probando `python --version` en cada candidato, pero necesita un Python real en el PATH: instalar Python 3.10 o superior desde python.org y `pip install -r src/compiscript/requirements.txt`. Si se usa una versión anterior del IDE, desactivar esos alias en Configuración → Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución de aplicaciones.
- **`cargo` o `rustc` no se reconocen.** Cerrar y volver a abrir la terminal después de instalar Rust para que el PATH se actualice.
