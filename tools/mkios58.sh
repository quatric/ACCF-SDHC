#!/bin/zsh
# Re-point a patched disc at IOS 58 instead of IOS 38, for SDHC testing.
# The TMD signature is invalidated; use Dolphin or a fakesigned loader only.
set -u

DIST=${DIST_DIR:-build}
WORK=${WORK_DIR:-work_ios58}
OUTD=$DIST/wbfs_ios58
NEWIOS=${2:-58}
ID=${1:-RUUE01}
SRC=$DIST/wbfs/${ID}_SDHC.wbfs
FST=$WORK/$ID
OUT=$OUTD/${ID}_SDHC_IOS${NEWIOS}.wbfs

mkdir -p "$WORK" "$OUTD"
[[ -f "$SRC" ]] || { echo "missing $SRC"; exit 1; }
rm -rf "$FST" "$OUT"
echo "extracting $ID..."
wit extract "$SRC" --dest "$FST" -q || { echo "extract failed"; exit 1; }
TMD=$(find "$FST" -name 'tmd.bin' | head -1)
[[ -n "$TMD" ]] || { echo "no tmd.bin found in FST"; exit 1; }
echo "tmd: $TMD"
python3 tools/patch_tmd_ios.py "$TMD" "$NEWIOS"
echo "rebuilding..."
wit copy "$FST" --dest "$OUT" --wbfs -q || { echo "rebuild failed"; exit 1; }
rm -rf "$FST"
echo "built $OUT"
wit dump "$OUT" 2>/dev/null | grep -iE "system version|ios"
