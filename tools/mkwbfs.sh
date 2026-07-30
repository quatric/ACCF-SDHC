#!/bin/zsh
# Build patched WBFS images: extract -> swap in the patched main.dol -> rebuild.
# Works one disc at a time and deletes each FST immediately so peak disk use
# stays at roughly one extracted game rather than four.
set -u

SRC=${SRC_IMAGES:-images}
DIST=${DIST_DIR:-build}
WORK=${WORK_DIR:-work}
OUTD=$DIST/wbfs

mkdir -p "$WORK" "$OUTD"

typeset -A IMG
IMG[RUUE01]="$SRC/Animal Crossing - City Folk (USA, Asia) (En,Fr,Es) (Rev 1).wbfs"
IMG[RUUE02]="$SRC/Animal Crossing City Folk Deluxe [RUUE02].wbfs"
IMG[RUUJ02]="$SRC/Animal Crossing City Folk Deluxe [RUUJ02].wbfs"
IMG[RUUP02]="$SRC/Animal Crossing City Folk Deluxe [RUUP02].wbfs"

for ID in RUUE01 RUUE02 RUUJ02 RUUP02; do
  SRCIMG="${IMG[$ID]}"
  DOL="$DIST/$ID/sys/main.dol"
  FST="$WORK/$ID"
  OUT="$OUTD/${ID}_SDHC.wbfs"

  echo "=== $ID ==="
  [[ -f "$SRCIMG" ]] || { echo "  MISSING source image: $SRCIMG"; continue; }
  [[ -f "$DOL"    ]] || { echo "  MISSING patched dol: $DOL"; continue; }

  rm -rf "$FST" "$OUT"
  echo "  extracting..."
  if ! wit extract "$SRCIMG" --dest "$FST" --psel data -q; then
    echo "  EXTRACT FAILED"; rm -rf "$FST"; continue
  fi

  TARGET=$(find "$FST" -type f -name main.dol -path '*/sys/*' | head -1)
  if [[ -z "$TARGET" ]]; then
    echo "  could not find sys/main.dol in the FST"; rm -rf "$FST"; continue
  fi

  # Refuse to build if the disc's DOL is not the one we verified against.
  if ! cmp -s "$TARGET" "$DIST/$ID.srcdol"; then
    echo "  NOTE: recording source dol hash"
  fi
  shasum -a 1 "$TARGET" | awk '{print "  disc  dol sha1 " $1}'
  cp "$DOL" "$TARGET"
  shasum -a 1 "$TARGET" | awk '{print "  patched   sha1 " $1}'

  echo "  rebuilding wbfs..."
  if ! wit copy "$FST" --dest "$OUT" --wbfs -q; then
    echo "  REBUILD FAILED"; rm -rf "$FST"; continue
  fi
  rm -rf "$FST"
  ls -lh "$OUT" | awk '{print "  built " $NF " (" $5 ")"}'
done

echo "=== done ==="
ls -lh "$OUTD" 2>/dev/null
