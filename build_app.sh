#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# AudioBoost needs a Python with working tkinter. Homebrew's python@3.12/3.13
# do not ship tkinter by default — install `brew install python-tk@3.12` (or
# @3.13) to enable them. macOS system Python 3.9 always has tkinter.

pick_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if "${PYTHON_BIN}" -c "import tkinter" 2>/dev/null; then
      echo "${PYTHON_BIN}"
      return 0
    fi
    echo "PYTHON_BIN=${PYTHON_BIN} is missing tkinter" >&2
    return 1
  fi
  for candidate in python3.13 python3.12 python3.11 /usr/bin/python3 python3; do
    if command -v "${candidate}" >/dev/null 2>&1 \
        && "${candidate}" -c "import tkinter" 2>/dev/null; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

if ! PYTHON_BIN="$(pick_python)"; then
  cat >&2 <<'MSG'
No Python with tkinter was found. Install one of:
  brew install python-tk@3.12    # adds tkinter to Homebrew python@3.12
  brew install python-tk@3.13    # adds tkinter to Homebrew python@3.13
Or use /usr/bin/python3 (macOS system Python) which already bundles tkinter.
MSG
  exit 1
fi

echo "Using ${PYTHON_BIN} ($(${PYTHON_BIN} --version))"

rm -rf build dist

if [[ ! -d .venv ]]; then
  "${PYTHON_BIN}" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip >/dev/null
pip install -r requirements.txt

python setup.py py2app

APP="dist/AudioBoost.app"

# macOS 26 enforces code-signature validity on Launch Services launches.
# py2app's default signatures can be missing or stale on nested Mach-O files,
# which causes the app to quit with SIGKILL (Code Signature Invalid) when
# double-clicked — but run fine from Terminal. Re-sign everything inside-out
# with an ad-hoc signature so Gatekeeper accepts it.
echo "Signing bundle…"
find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 \
  | xargs -0 codesign --force --sign - --timestamp=none >/dev/null 2>&1 || true
for py in "$APP"/Contents/Frameworks/Python.framework/Versions/*/Python; do
  [[ -f "$py" ]] && codesign --force --sign - --timestamp=none "$py" >/dev/null 2>&1 || true
done
[[ -f "$APP/Contents/MacOS/python" ]] && \
  codesign --force --sign - --timestamp=none "$APP/Contents/MacOS/python" >/dev/null 2>&1
codesign --force --sign - --timestamp=none "$APP/Contents/MacOS/AudioBoost" >/dev/null 2>&1
codesign --force --sign - --timestamp=none "$APP"

echo ""
echo "✓ Built $APP"
open dist/ || true
