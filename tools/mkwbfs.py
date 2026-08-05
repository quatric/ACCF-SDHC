#!/usr/bin/env python3
"""Build patched WBFS images for every disc dist.py has a target for.

Extracts each image under SRC_IMAGES exactly once, reads its real disc id and
version straight from the extracted sys/boot.bin header (offsets 0x0 and 0x7),
and matches that against dist.py's TARGETS -- so there is no separate
id->filename table to keep in sync by hand, and no dependence on any
particular image naming scheme. For each match: swap in the patched
sys/main.dol from DIST_DIR/<key>/sys/main.dol (run `python3 tools/dist.py`
first), optionally repoint the TMD at IOS 58 (--ios58), and rebuild the wbfs.

    python3 tools/mkwbfs.py            # every image that matches a target
    python3 tools/mkwbfs.py RUUE01v1   # only build if this target key is found
    python3 tools/mkwbfs.py --ios58    # also patch the TMD to require IOS 58
"""
import argparse
import os
import shutil
import subprocess
import sys

import dist
import paths

SRC = paths.SRC_IMAGES
DIST_DIR = paths.DIST_DIR
WORK = os.environ.get('WORK_DIR', 'work')
OUT = os.path.join(DIST_DIR, 'wbfs')


def require(tool):
    if shutil.which(tool) is None:
        sys.exit('required tool not found on PATH: %s' % tool)


def find_file(root, name):
    for r, _, files in os.walk(root):
        if name in files:
            return os.path.join(r, name)
    return None


def read_disc_id(fst):
    boot = find_file(fst, 'boot.bin')
    if not boot:
        return None
    with open(boot, 'rb') as f:
        header = f.read(8)
    disc_id = header[0:6].decode('ascii', 'replace')
    disc_ver = header[7]
    return disc_id, disc_ver


def key_for(disc_id, disc_ver):
    for key, (label, _src, _delta, tid, tver) in dist.TARGETS.items():
        if tid == disc_id and tver == disc_ver:
            return key, label
    return None, None


def build_one(fst, key, label, ios58):
    dol = os.path.join(DIST_DIR, key, 'sys', 'main.dol')
    out = os.path.join(OUT, '%s_SDHC.wbfs' % key)

    print('=== %s: %s ===' % (key, label))
    if not os.path.isfile(dol):
        print('  MISSING patched dol: %s (run tools/dist.py first)' % dol)
        return False

    os.makedirs(OUT, exist_ok=True)
    target = find_file(fst, 'main.dol')
    if not target or os.path.basename(os.path.dirname(target)) != 'sys':
        print('  could not find sys/main.dol in the FST')
        shutil.rmtree(fst, ignore_errors=True)
        return False
    shutil.copyfile(dol, target)

    if ios58:
        tmd = find_file(fst, 'tmd.bin')
        if not tmd:
            print('  no tmd.bin found, skipping --ios58')
        else:
            subprocess.run([sys.executable,
                             os.path.join(os.path.dirname(__file__), 'patch_tmd_ios.py'),
                             tmd, '58'], check=True)

    print('  rebuilding wbfs...')
    if subprocess.run(['wit', 'copy', fst, '--dest', out, '--wbfs', '-q']).returncode:
        print('  REBUILD FAILED')
        return False
    print('  built %s (%.1f MiB)' % (out, os.path.getsize(out) / 2**20))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('keys', nargs='*', help='only build these dist.py target keys, if found')
    ap.add_argument('--ios58', action='store_true', help='also repoint the TMD at IOS 58')
    args = ap.parse_args()

    require('wit')
    if not os.path.isdir(SRC):
        sys.exit('no source image directory: %s' % SRC)
    images = sorted(f for f in os.listdir(SRC) if f.lower().endswith(('.wbfs', '.iso')))
    if not images:
        sys.exit('no .wbfs/.iso images found under %s' % SRC)

    wanted = set(args.keys)
    ok = True
    matched = set()
    for name in images:
        path = os.path.join(SRC, name)
        fst = os.path.join(WORK, os.path.splitext(name)[0])
        shutil.rmtree(fst, ignore_errors=True)
        print('extracting %s...' % name)
        if subprocess.run(['wit', 'extract', path, '--dest', fst, '--psel', 'data', '-q']).returncode:
            print('  EXTRACT FAILED')
            ok = False
            shutil.rmtree(fst, ignore_errors=True)
            continue

        got = read_disc_id(fst)
        if not got:
            print('  SKIP %-60s could not read disc header' % name)
            ok = False
            shutil.rmtree(fst, ignore_errors=True)
            continue
        disc_id, disc_ver = got
        key, label = key_for(disc_id, disc_ver)
        if not key:
            print('  --   %-60s %s v%d: no matching dist.py target' % (name, disc_id, disc_ver))
            shutil.rmtree(fst, ignore_errors=True)
            continue
        if wanted and key not in wanted:
            shutil.rmtree(fst, ignore_errors=True)
            continue
        matched.add(key)
        ok = build_one(fst, key, label, args.ios58) and ok
        shutil.rmtree(fst, ignore_errors=True)

    for key in sorted(wanted - matched):
        print('  requested target %s: no source image found for it' % key)
        ok = False

    print('=== done ===')
    if os.path.isdir(OUT):
        for name in sorted(os.listdir(OUT)):
            print('  ', name)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
