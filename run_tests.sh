#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Elige el primer interprete que tenga pytest instalado.
PY=""
for candidate in "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/venv/bin/python" python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -m pytest --version >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

if [[ -z "$PY" ]]; then
  echo "No se encontro un Python con pytest instalado. Instalar con: pip install pytest"
  exit 1
fi

echo "Suite de Compiscript con ${PY}..."
"$PY" -m pytest -q

echo "Pruebas completadas correctamente."
