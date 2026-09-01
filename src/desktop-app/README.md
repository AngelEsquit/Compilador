# YALex Studio: IDE de escritorio

Interfaz tipo VS Code (Tauri + React + Monaco) para los pipelines de YALex, YAPar
y, más adelante, Compiscript.

## Arquitectura

- Frontend: React + TypeScript + Vite (`src/`).
- Shell de escritorio: Tauri (`src-tauri/`).
- Motor: Python (`../yalex_parser`, `../yapar_generator`).
- Bridge: `../bridge_cli.py`, protocolo JSON por stdin y stdout.

## Ejecución

```bash
npm install
npm run tauri:nowatch     # recomendado en Windows y Linux, evita reinicios al guardar
npm run tauri -- dev      # Tauri dev estandar
bash scripts/launch-clean.sh   # Linux con conflictos de snap/glibc
```

Builds:

```bash
npm run build             # solo frontend, sale en dist/
npm run tauri -- build    # instaladores, salen en src-tauri/target/release/bundle/
```

## Funcionalidad

- Explorer recursivo con expand y collapse, badges por tipo de archivo.
- Editor en pestañas con resaltado de sintaxis y guardado manual.
- Panel Pipeline con una acción activa por vez:
  - YALex: `spec`, `ast`, `combinedNfa` (construcción directa), `dfa`, `tokenize`, `generate`.
  - YAPar: `yaparSpec`, `yaparAutomaton`, `yaparTable`, `yaparParse`, `yaparGenerate`.
- Campos de input y output contextuales, solo cuando la acción los necesita.
- Panel `Resultado JSON` y panel `Output` para trazas y errores.
- Paneles redimensionables con persistencia de tamaños.

Flujo típico: abrir un `.yal` o `.yalp`, elegir la acción, completar los campos
que pida, ejecutar y revisar `Resultado JSON` y `Output`.

## Solución de problemas

| Síntoma | Causa y arreglo |
|---|---|
| `npm run tauri dev` falla desde la raíz | Ejecutarlo dentro de `src/desktop-app`. Si el shell se queja de los flags, usar `npm run tauri -- dev` |
| La app se reinicia al guardar `.txt` o `.yal` | Usar `npm run tauri:nowatch` |
| `Cannot read properties of undefined (reading 'invoke')` | La UI se abrió fuera de Tauri, por ejemplo con `npm run dev`. Iniciar con `npm run tauri -- dev` |
| Error de `gdk-3.0`, `pkg-config` o `webkit` en Ubuntu | Instalar las dependencias nativas de Tauri listadas en el README raíz |
| `symbol lookup error: libpthread.so.0: undefined symbol __libc_pthread_init` | Snap provee una libc vieja. Usar `bash scripts/launch-clean.sh` |
| `cargo` o `rustc` no encontrado | Instalar Rust y reiniciar la terminal |
| Error de linker en Windows | Instalar MSVC Build Tools |
| `No se pudo iniciar py/python` | Verificar `python3 --version` en Linux, o `py -3 --version` en Windows |
| Puerto de Vite ocupado | Cerrar la instancia anterior o reiniciar la app |

## Notas

- En Windows el backend intenta `python` y luego `py -3` como fallback.
- La raíz del workspace se detecta asumiendo que la app vive en `src/desktop-app/`.
