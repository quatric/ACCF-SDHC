"""Verify the emitted distribution DOLs, independently of the code that wrote them.

Re-reads each patched main.dol from disk and asserts, at the rebased addresses:
  * every patch site now branches into the codecave
  * each trampoline replays the original instruction and returns to site+4
  * each bl redirect lands exactly on a helper entry
  * helpers are intact and end in blr
  * nothing outside the intended writes changed vs the source DOL
"""
import struct, sys, os
from dol import Dol
import build, dist

md = None
try:
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
except ImportError:
    pass

fail = []


def check(cond, msg):
    if not cond:
        fail.append(msg)
        print('    FAIL ' + msg)
    return cond


def rel(w, at):
    off = w & 0x03FFFFFC
    if off >= 0x02000000:
        off -= 0x04000000
    return at + off


for gid, (label, src, delta, disc_id, disc_ver) in sorted(dist.TARGETS.items()):
    out = os.path.join(dist.OUT, gid, 'sys', 'main.dol')
    if not os.path.exists(out):
        check(False, '%s: no output DOL' % gid)
        continue
    s = Dol(src)
    p = Dol(out)
    print('== %s (delta %+d) %s' % (gid, delta, label))

    check(len(s.data) == len(p.data), '%s: size changed' % gid)

    # 1. only the intended bytes differ
    patches, cave_end = dist.rebased_patches(delta)
    touched = set()
    for va, blob in patches:
        fo = s.v2f(va)
        touched.update(range(fo, fo + len(blob)))
    diff = {i for i in range(min(len(s.data), len(p.data))) if s.data[i] != p.data[i]}
    stray = diff - touched
    check(not stray, '%s: %d bytes changed outside the patch set' % (gid, len(stray)))

    # 2. helpers intact at their absolute addresses
    for name, addr, words in build.HELPERS:
        got = struct.unpack('>%dI' % len(words), p.read(addr, len(words) * 4))
        check(list(got) == list(words), '%s: %s body mismatch' % (gid, name))
        check(got[-1] == 0x4E800020, '%s: %s does not end in blr' % (gid, name))

    # 3. bl redirects
    for name, addr, tgt, orig in build.BLS:
        a = addr + delta
        w = struct.unpack('>I', p.read(a, 4))[0]
        check((w >> 26) == 18 and (w & 1) == 1 and rel(w, a) == tgt,
              '%s: %s -> 0x%08X (want 0x%08X)' % (gid, name, rel(w, a), tgt))

    # 4. hooks branch to trampolines that replay the original and return
    cur = build.TRAMP
    for name, addr, orig, payload in build.HOOKS:
        a = addr + delta
        n = len(payload)
        site = struct.unpack('>I', p.read(a, 4))[0]
        check((site >> 26) == 18 and (site & 3) == 0 and rel(site, a) == cur,
              '%s: %s site does not branch to 0x%08X' % (gid, name.split(':')[0], cur))
        body = struct.unpack('>%dI' % n, p.read(cur, 4 * n))
        check(orig in body, '%s: %s trampoline lost the original %08X'
              % (gid, name.split(':')[0], orig))
        last = body[-1]
        check((last >> 26) == 18 and rel(last, cur + 4 * (n - 1)) == a + 4,
              '%s: %s trampoline does not return to 0x%08X'
              % (gid, name.split(':')[0], a + 4))

        # Absolute addresses materialised by lis/ori inside the payload (the
        # bctr targets in hook2/hook4) must keep their offset from the site.
        for i in range(n - 1):
            x, y = payload[i], payload[i + 1]
            if (x >> 26) != 15:
                continue
            rD = (x >> 21) & 0x1F
            if (y >> 26) != 24 or ((y >> 21) & 0x1F) != rD or ((y >> 16) & 0x1F) != rD:
                continue
            want_src = ((x & 0xFFFF) << 16) | (y & 0xFFFF)
            gx, gy = body[i], body[i + 1]
            got = ((gx & 0xFFFF) << 16) | (gy & 0xFFFF)
            if want_src < 0x80100000:
                check(got == want_src,
                      '%s: %s cave pointer moved: %08X -> %08X'
                      % (gid, name.split(':')[0], want_src, got))
            else:
                check(got == want_src + delta and got - a == want_src - addr,
                      '%s: %s bctr target %08X should be %08X (site+0x%X)'
                      % (gid, name.split(':')[0], got, want_src + delta,
                         want_src - addr))
                check(p.v2f(got) is not None,
                      '%s: %s bctr target %08X is unmapped'
                      % (gid, name.split(':')[0], got))
        cur += 4 * n
    check(cur <= 0x800060C0, '%s: trampolines overflow the cave' % gid)

    # 5. the source really did hold the declared originals
    for name, addr, orig, payload in build.HOOKS:
        w = struct.unpack('>I', s.read(addr + delta, 4))[0]
        check(w == orig, '%s: source %s had %08X, expected %08X'
              % (gid, name.split(':')[0], w, orig))

print()
print('ALL DISTRIBUTION DOLS VERIFIED' if not fail else '%d FAILURES' % len(fail))
sys.exit(1 if fail else 0)
