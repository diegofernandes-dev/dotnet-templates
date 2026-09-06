#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="${ROOT_DIR}/tests"
VENV_DIR="${TESTS_DIR}/.venv"

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required on PATH for platform contract tests" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required on PATH for platform contract tests" >&2
  exit 1
fi

python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install --quiet -r "${TESTS_DIR}/requirements.txt"

cd "${ROOT_DIR}"
python -m unittest discover -s tests -p 'test_*.py' -v
