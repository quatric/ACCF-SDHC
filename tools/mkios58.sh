#!/bin/zsh
# Re-point a patched disc at IOS 58 instead of IOS 38, for SDHC testing.
#
# The required IOS lives in the TMD's sys_version field (8 bytes at 0x184 of the
# TMD: 00000001-000000XX). wit has no option for it, so the TMD is patched in the
# extracted FST and the image rebuilt. This invalidates the TMD signature, which
# is fine for Dolphin and for cIOS/loader use, but it is a TEST image -- it is not
# something to hand out.
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
[[ -n "$TMD" ]] || { echo "no tmd.bin found in FST"; find "$FST" -maxdepth 2 | head -20; exit 1; }
echo "tmd: $TMD"

python3 - "$TMD" "$NEWIOS" <<'PY'
import sys, struct
p, newios = sys.argv[1], int(sys.argv[2])
d = bytearray(open(p, 'rb').read())
off = 0x184                      # sys_version, for an RSA-2048 signed TMD
old = struct.unpack('>Q', d[off:off+8])[0]
print('  sys_version before: %016X (IOS %d)' % (old, old & 0xFF))
assert old >> 32 == 1, 'unexpected sys_version high word %08X' % (old >> 32)
new = (1 << 32) | newios
d[off:off+8] = struct.pack('>Q', new)
open(p, 'wb').write(bytes(d))
print('  sys_version after:  %016X (IOS %d)' % (new, newios))
PY

echo "rebuilding..."
wit copy "$FST" --dest "$OUT" --wbfs -q || { echo "rebuild failed"; exit 1; }
rm -rf "$FST"
echo "built $OUT"
wit dump "$OUT" 2>/dev/null | grep -iE "system version|ios"
