# Compiscript Studio: IDE de escritorio

Interfaz tipo VS Code (Tauri, React y Monaco) para el compilador de Compiscript.

## Arquitectura

- Frontend: React, TypeScript y Vite (`src/`).
- Shell de escritorio: Tauri (`src-tauri/`).
- Motor: Python (`../compiscript`).
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

- Explorador de archivos y editor en pestañas con resaltado de sintaxis.
- Panel Pipeline con las acciones de Compiscript: `compiscriptCheck`, `compiscriptSymbols`, `compiscriptTree` y `compiscriptTAC`.
- Vistas del resultado: diagnósticos, tabla de símbolos, árbol sintáctico, código intermedio, registros de activación y temporales. El botón JSON muestra la respuesta cruda del bridge.
- Paneles redimensionables con persistencia de tamaños.

`App.tsx` conserva código de los flujos de YALex y YAPar de un proyecto anterior. Ya no se muestran y el bridge no atiende esas acciones.

## Solución de problemas

| Síntoma | Causa y arreglo |
|---|---|
| `npm run tauri dev` falla desde la raíz | Ejecutarlo dentro de `src/desktop-app` |
| `Cannot read properties of undefined (reading 'invoke')` | La UI se abrió fuera de Tauri, por ejemplo con `npm run dev`. Iniciar con `npm run tauri -- dev` |
| Error de `gdk-3.0`, `pkg-config` o `webkit` en Ubuntu | Instalar las dependencias nativas de Tauri listadas en el README raíz |
| `symbol lookup error: libpthread.so.0` | Snap provee una libc vieja. Usar `bash scripts/launch-clean.sh` |
| `cargo` o `rustc` no encontrado | Instalar Rust y reiniciar la terminal |
| Error de linker en Windows | Instalar MSVC Build Tools |
| `No se pudo iniciar py/python` | Verificar `python --version` |
| Puerto de Vite ocupado | Cerrar la instancia anterior |
