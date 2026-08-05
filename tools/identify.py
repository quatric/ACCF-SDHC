#!/usr/bin/env python3
"""Identify a City Folk disc and say which patch belongs to it.

The GUI patcher reads the disc's own id and revision and can only ever apply
the matching site map. Anyone installing by hand -- a Gecko code, a Riivolution
XML, a prebuilt main.dol -- has no such guard, and RUUE01/RUUJ01/RUUP01 each
cover two revisions whose addresses differ. Applying the wrong one overwrites
unrelated live code: the SD card is reported as an unknown device at best, and
the title dies at worst.

So: run this first.

    python3 tools/identify.py "Animal Crossing - City Folk (USA).wbfs"
    python3 tools/identify.py sys/main.dol

Accepts a .wbfs, a .iso, or a bare sys/main.dol. Given an image it reads the
disc header directly and needs no tooling; if `wit` is on PATH it also extracts
main.dol and checks the ten patch sites, which is the only way to tell an
unpatched disc from an already-patched one.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build
import dist
from dol import Dol

WII_MAGIC = 0x5D1C9EA3


def read_disc_header(path):
    """Return (disc_id, version) from a .wbfs or .iso, or None.

    A .wbfs keeps a copy of the disc header at 0x200; a plain .iso has it at 0.
    Both are confirmed by the Wii magic word at header+0x18 rather than by the
    file extension, so a misnamed file is caught instead of misread.
    """
    with open(path, 'rb') as f:
        for base in (0x200, 0x000):
            f.seek(base)
            head = f.read(0x20)
            if len(head) < 0x20:
                continue
            if struct.unpack_from('>I', head, 0x18)[0] == WII_MAGIC:
                return head[0:6].decode('ascii', 'replace'), head[7]
    return None


def classify(d, delta):
    """unpatched / patched / mismatch, by looking at the ten sites."""
    if dist.verify_target(d, delta) == []:
        return 'unpatched'
    # Patched discs branch into the codecave at every site and carry live
    # helper code where the source DOL had zeroed padding.
    hooks_branch = all(
        (w := d.read(addr + delta, 4)) is not None
        and (struct.unpack('>I', w)[0] >> 26) == 18
        for _n, addr, _o, _p in build.HOOKS)
    helper = d.read(build.HELPERS[0][1], 4)
    if hooks_branch and helper == struct.pack('>I', build.HELPERS[0][2][0]):
        return 'patched'
    return 'mismatch'


def extract_dol(image, into):
    wit = shutil.which('wit')
    if wit is None:
        return None, 'wit not on PATH -- skipping the main.dol check'
    r = subprocess.run([wit, 'extract', image, '--dest', into,
                        '--files', '+/sys/main.dol', '--psel', 'data',
                        '--overwrite', '-q'], capture_output=True, text=True)
    if r.returncode:
        return None, 'wit extract failed: %s' % (r.stderr or r.stdout).strip()
    for root, _dirs, files in os.walk(into):
        if 'main.dol' in files and os.path.basename(root) == 'sys':
            return os.path.join(root, 'main.dol'), None
    return None, 'no sys/main.dol in the extracted disc'


def report(disc_id, ver, dol_path):
    print('disc id:   %s' % disc_id)
    print('revision:  %s' % ('%d' % ver if ver is not None else 'unknown'))

    if disc_id in ('RUUK01', 'RUUK02'):
        print('\nKorean discs already support SDHC natively. Do NOT patch them.')
        return 0

    key = label = None
    for k, (lbl, _src, delta, tid, tver) in dist.TARGETS.items():
        if tid == disc_id and tver == ver:
            key, label, dl = k, lbl, delta
            break
    if key is None:
        print('\nNot a supported target.')
        print('Supported: %s' % ', '.join(
            sorted('%s v%d' % (t[3], t[4]) for t in dist.TARGETS.values())))
        return 1

    print('title:     %s' % label)
    print('rebase:    %+d' % dl)
    print('')
    print('use exactly these files:')
    print('  gecko/%s.txt' % key)
    print('  riivolution/%s.xml' % key)
    if any(t[3] == disc_id and t[4] != ver for t in dist.TARGETS.values()):
        other = [k for k, t in dist.TARGETS.items() if t[3] == disc_id and t[4] != ver]
        print('')
        print('  NOTE: %s also covers another revision (%s). Those addresses are'
              % (disc_id, ', '.join(sorted(other))))
        print('        different and must not be used on this disc.')

    if dol_path:
        state = classify(Dol(dol_path), dl)
        print('')
        if state == 'unpatched':
            print('main.dol:  unpatched, matches the %s site map -- ready to patch' % key)
        elif state == 'patched':
            print('main.dol:  ALREADY PATCHED with the %s site map' % key)
        else:
            print('main.dol:  does NOT match the %s site map, and is not this' % key)
            print('           patch applied either -- an unexpected build, or patched')
            print('           with something else. Do not patch it.')
            return 1
    return 0


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    path = argv[1]
    if not os.path.isfile(path):
        print('no such file: %s' % path)
        return 2

    if path.lower().endswith('.dol'):
        d = Dol(path)
        for key, (label, _src, delta, tid, tver) in sorted(dist.TARGETS.items()):
            if classify(d, delta) in ('unpatched', 'patched'):
                print('main.dol matches %s (%s v%d)' % (key, tid, tver))
                return report(tid, tver, path)
        print('main.dol matches no supported build.')
        return 1

    got = read_disc_header(path)
    if not got:
        print('%s: no Wii disc header found (not a .wbfs/.iso?)' % path)
        return 2
    disc_id, ver = got
    with tempfile.TemporaryDirectory(prefix='accf_identify_') as tmp:
        dol_path, why = extract_dol(path, tmp)
        if why:
            print('(%s)\n' % why)
        return report(disc_id, ver, dol_path)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
