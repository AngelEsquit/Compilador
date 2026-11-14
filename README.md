# Compilador de Compiscript

Construcción de Compiladores, UVG, 2026 II. Compilador de Compiscript (subconjunto de TypeScript) sobre un parser generado con ANTLR: análisis semántico, código intermedio de tres direcciones y generación de ensamblador MIPS32.

## Integrantes

- Javier España #23361
- Ángel Esquit #23221
- Roberto Barreda #23354

## Etapas

| Etapa | Módulo | Resultado |
|---|---|---|
| Análisis léxico y sintáctico | [src/compiscript/grammar/](src/compiscript/grammar/) | Árbol sintáctico (ANTLR) |
| Análisis semántico | [src/compiscript/semantic/](src/compiscript/semantic/) | Diagnósticos y tabla de símbolos |
| Distribución de memoria | [src/compiscript/symbols/layout.py](src/compiscript/symbols/layout.py) | Registros de activación, área estática y clases |
| Código intermedio | [src/compiscript/intermediate/](src/compiscript/intermediate/) | Código de tres direcciones (TAC) |
| Generación de código | [src/compiscript/backend/](src/compiscript/backend/) | Ensamblador MIPS32 para MARS o SPIM |

Cada etapa solo se ejecuta si la anterior no reportó errores.

## Requisitos

- Python 3.10 o superior y `pip install -r src/compiscript/requirements.txt`.
- Para el IDE: Node.js 18 o superior y el toolchain de Rust.
  - Windows: Visual Studio Build Tools (MSVC) y WebView2 Runtime.
  - Linux: `build-essential pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev patchelf libssl-dev`.
- Opcional: Java y MARS 4.5 para ejecutar el ensamblador fuera del simulador incluido.

## Uso desde la línea de comandos

```bash
python src/compiscript/run_demo.py programa.cps                 # diagnósticos
python src/compiscript/run_demo.py programa.cps --tac --layout  # código intermedio y registros de activación
python src/compiscript/run_demo.py programa.cps --asm           # ensamblador MIPS
python src/compiscript/run_demo.py programa.cps --run --tree    # ejecuta y muestra el árbol de activación
python src/compiscript/run_demo.py programa.cps --asm --registers=3   # fuerza derrames con tres registros
python src/compiscript/run_demo.py programa.cps --out=programa.asm    # archivo para MARS o SPIM
```

Ejemplo:

```text
function factorial(n: integer): integer {
  if (n <= 1) { return 1; }
  return n * factorial(n - 1);
}
print(factorial(4));
```

```text
Salida del programa:
24

Arbol de activacion:
main()
  factorial(4) = 24
    factorial(3) = 6
      factorial(2) = 2
        factorial(1) = 1
```

## Ensamblador y simulador

El backend genera MIPS32 con la sintaxis, las pseudoinstrucciones y las llamadas al sistema de MARS y SPIM. Hay dos formas de ejecutarlo:

- **Simulador incluido** ([src/compiscript/backend/simulator.py](src/compiscript/backend/simulator.py)): lo usan `--run`, las pruebas y el IDE. No necesita Java y registra las llamadas para construir el árbol de activación.
- **MARS**: generar el archivo con `--out=programa.asm` y abrirlo en MARS, o ejecutarlo sin interfaz con `java -jar Mars4_5.jar nc programa.asm`.

## IDE

```bash
cd src/desktop-app
npm install
npm run tauri:nowatch
```

Abrir la carpeta del proyecto y un archivo `.cps`, y ejecutar **Diagnósticos**, **Tabla de Símbolos**, **Árbol Sintáctico** o **Código Intermedio** desde el panel Pipeline.

## Pruebas

```bash
python -m pytest            # toda la suite
./run_tests.sh              # lo mismo, eligiendo el Python que tenga pytest
```

Los programas de `tests/compiscript/intermediate/valid/*.cps` declaran su salida con líneas `// expect:`. Cada uno se ejecuta dos veces: con el intérprete de referencia del código intermedio y, compilado a MIPS, con el simulador (con diez y con tres registros). Para agregar un caso basta con crear un `.cps` en esa carpeta.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/Compiscript.md](docs/Compiscript.md) | El lenguaje Compiscript |
| [docs/Compiscript_Diseno_Semantico.md](docs/Compiscript_Diseno_Semantico.md) | Análisis semántico y sistema de tipos |
| [docs/Lenguaje_Intermedio.md](docs/Lenguaje_Intermedio.md) | Instrucciones del código intermedio y su traducción |
| [docs/PRY2_IMPLEMENTACION.md](docs/PRY2_IMPLEMENTACION.md) | Tabla de símbolos y registros de activación |
| [src/compiscript/README.md](src/compiscript/README.md) | Mapa de módulos |

## Problemas comunes

- **Windows, error 4551 al ejecutar el IDE.** Smart App Control bloquea los ejecutables sin firmar que compila Rust. Se desactiva en Seguridad de Windows, Control de aplicaciones y del navegador. La línea de comandos y las pruebas no lo necesitan.
- **Windows, "Python was not found" (código 9009) desde el IDE.** Los alias `python.exe` de `WindowsApps` solo abren la Tienda. Instalar Python desde python.org y las dependencias de `requirements.txt`.
- **`cargo` o `rustc` no se reconocen.** Cerrar y volver a abrir la terminal después de instalar Rust.
