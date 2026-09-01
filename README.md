# Compilador: YALex Studio + Compiscript

Repositorio de Diseño de Lenguajes de Programación (UVG). Contiene dos fases:

| Fase | Qué hace | Dónde |
|---|---|---|
| **YALex / YAPar** (entregada) | Genera lexers desde `.yal` y parsers SLR desde `.yalp`, sin librerías de regex ni de autómatas | [src/yalex_parser/](src/yalex_parser/), [src/yapar_generator/](src/yapar_generator/) |
| **Compiscript** (en curso) | Análisis semántico de Compiscript sobre ANTLR: sistema de tipos, tabla de símbolos y diagnósticos | [src/compiscript/](src/compiscript/) |

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

## Ejecución

```bash
# Analizador semantico de Compiscript sobre un archivo .cps
python src/compiscript/run_demo.py tests/compiscript/samples/animals.cps

# CLI de YALex/YAPar (menu interactivo)
python src/main.py

# Generar lexer y parser autonomos
python src/bridge_yapar.py gen-lexer  examples/medium/lang_medium.yal  -o output/lexer.py
python src/bridge_yapar.py gen-parser examples/medium/lang_medium.yalp -o output/parser.py

# IDE de escritorio
cd src/desktop-app && npm install && npm run tauri:nowatch
```

## Pruebas

```bash
python -m pytest                      # todo (YALex/YAPar + Compiscript)
python -m pytest tests/compiscript/   # solo la suite semantica
./run_tests.sh                        # todo
```


## Estructura

```text
src/compiscript/     Analisis semantico: gramatica ANTLR, tipos, simbolos, reglas
src/yalex_parser/    Generador de lexers (metodo directo, minimizacion Hopcroft)
src/yapar_generator/ Generador de parsers SLR (items LR(0), FIRST/FOLLOW)
src/desktop-app/     IDE de escritorio (Tauri + React + Monaco)
src/bridge_cli.py    Bridge JSON entre el IDE y el motor Python
docs/                Enunciado y documento de diseño de la fase semántica
examples/            Casos de prueba low / medium / high
tests/               Suites de ambas fases
```
