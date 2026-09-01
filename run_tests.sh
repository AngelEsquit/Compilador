#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

LOOPS="${1:-1}"
if ! [[ "$LOOPS" =~ ^[0-9]+$ ]] || [[ "$LOOPS" -lt 1 ]]; then
  echo "Uso: ./run_tests.sh [loops>=1]"
  exit 1
fi

# Elige el primer interprete que tenga pytest instalado.
PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -m pytest --version >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

if [[ -z "$PY" ]]; then
  echo "No se encontro un Python con pytest instalado. Instalar con: pip install pytest"
  exit 1
fi

echo "[1/2] Suite completa (YALex/YAPar + Compiscript) con ${PY}..."
"$PY" -m pytest -q

echo "[2/2] Repeticion de escenarios extremos (${LOOPS} veces)..."
for ((i=1; i<=LOOPS; i++)); do
  echo "  - Iteracion ${i}/${LOOPS}"
  "$PY" -m pytest tests/test_extreme_scenarios.py -q
done

echo "Pruebas completadas correctamente."
