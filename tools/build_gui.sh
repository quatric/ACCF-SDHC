#!/bin/zsh
# Build the standalone GUI patcher app with PyInstaller.
# Output: tools/dist/ACCF-SDHC-Patcher.app (macOS) or dist/ACCF-SDHC-Patcher/ (other OSes).
set -eu
cd "${0:a:h}"
command -v pyinstaller >/dev/null || { echo "pyinstaller not found (pip install pyinstaller)"; exit 1; }
pyinstaller --noconfirm ACCF-SDHC-Patcher.spec
echo "built: tools/dist/ACCF-SDHC-Patcher"
