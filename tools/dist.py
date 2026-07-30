"""Build the ACCF SDHC distribution for every supported disc.

Emits, per target:
  <id>/sys/main.dol          patched DOL (static form, no codehandler)
  riivolution/<id>.xml       Riivolution <memory> patch
  gecko/<id>.txt             Gecko code text

Targets are the USA Rev 1 base game plus the three City Folk Deluxe regions
that are uniform rebases of it. RUUK02 (Korea) is deliberately excluded: it
ships a newer PFD revision with native SDHC support, so patching it would be
redundant and would risk double-converting block addresses.
"""
import os, struct, sys, shutil
from dol import Dol
import paths
import build

OUT = paths.DIST_DIR

# id -> (label, source main.dol, delta from the RUUE01 Rev1 map)
TARGETS = {
    'RUUE01': ('Animal Crossing: City Folk (USA/Asia, Rev 1)',
               paths.ACCF_DOL, 0),
    'RUUE02': ('Animal Crossing: City Folk Deluxe (USA)',
               os.path.join(paths.SRC_IMAGES, 'RUUE02/sys/main.dol'), -292),
    'RUUJ02': ('Animal Crossing: City Folk Deluxe (Japan)',
               os.path.join(paths.SRC_IMAGES, 'RUUJ02/sys/main.dol'), 124),
    'RUUP02': ('Animal Crossing: City Folk Deluxe (PAL)',
               os.path.join(paths.SRC_IMAGES, 'RUUP02/sys/main.dol'), -724),
}


def rebase_payload(words, delta):
    """Shift absolute game-code addresses built by a lis/ori pair inside a hook
    payload. hook2 and hook4 materialise a return address (site+0x40, site+0xC)
    and reach it with bctr, so those must follow the site. Addresses in the
    codecave (0x8000xxxx -- e.g. hook1's FLAG pointer) are fixed and must not
    move, hence the 0x80100000 floor."""
    if not delta:
        return list(words)
    w = list(words)
    for i in range(len(w) - 1):
        a, b_ = w[i], w[i + 1]
        if (a >> 26) != 15:                                  # lis rD, hi
            continue
        rD = (a >> 21) & 0x1F
        if (b_ >> 26) != 24 or ((b_ >> 21) & 0x1F) != rD or ((b_ >> 16) & 0x1F) != rD:
            continue                                          # ori rD, rD, lo
        va = ((a & 0xFFFF) << 16) | (b_ & 0xFFFF)
        if va < 0x80100000:                                   # cave / FLAG: fixed
            continue
        nva = va + delta
        w[i] = (a & 0xFFFF0000) | ((nva >> 16) & 0xFFFF)
        w[i + 1] = (b_ & 0xFFFF0000) | (nva & 0xFFFF)
    return w


def rebased_patches(delta):
    """Rebuild the static patch for a shifted site map.

    Relative branches encode (target - from), so they must be recomputed against
    the *rebased* site address -- shifting a prebuilt blob silently corrupts every
    branch by exactly the delta. Helper and trampoline bodies live at fixed cave
    addresses and do not move."""
    patches = []
    for name, addr, words in build.HELPERS:
        patches.append((addr, b''.join(struct.pack('>I', x) for x in words)))
    for name, addr, tgt, orig in build.BLS:
        a = addr + delta
        patches.append((a, struct.pack('>I', build.bl(tgt, a))))
    cur = build.TRAMP
    for name, addr, orig, payload in build.HOOKS:
        a = addr + delta
        p = rebase_payload(payload, delta)
        body = list(p[:-1]) + [build.b(a + 4, cur + 4 * (len(p) - 1))]
        patches.append((a, struct.pack('>I', build.b(cur, a))))
        patches.append((cur, b''.join(struct.pack('>I', x) for x in body)))
        cur += 4 * len(body)
    assert cur < 0x800060C0, 'trampolines overflow the codecave'
    return patches, cur


def verify_target(d, delta):
    """Every declared original must still be present at its rebased address."""
    bad = []
    for name, addr, orig, payload in build.HOOKS:
        w = d.read(addr + delta, 4)
        if not w or struct.unpack('>I', w)[0] != orig:
            bad.append(name.split(':')[0])
    for name, addr, tgt, orig in build.BLS:
        w = d.read(addr + delta, 4)
        if not w or struct.unpack('>I', w)[0] != orig:
            bad.append(name)
    cave = d.read(build.CAVE, 0x4C0)
    if cave != b'\x00' * 0x4C0:
        bad.append('codecave not zero')
    return bad


def riivolution_xml(gid, label, patches):
    L = ['<!-- %s -- SDHC Support [Bero, ported by quatric] -->' % label,
         '<wiidisc version="1" root="/">',
         '  <id game="%s" />' % gid,
         '  <options>',
         '    <section name="Animal Crossing: City Folk">',
         '      <option name="SDHC Card Support" default="1">',
         '        <choice name="Enabled"><patch id="sdhc" /></choice>',
         '      </option>',
         '    </section>',
         '  </options>',
         '  <patch id="sdhc">']
    for va, blob in sorted(patches):
        L.append('    <memory offset="0x%08X" value="%s" />' % (va, blob.hex().upper()))
    L += ['  </patch>', '</wiidisc>', '']
    return '\n'.join(L)


def gecko_text(gid, label, delta):
    """Gecko form, rebased. C2/04/06 codes address memory directly."""
    out = ['$SDHC Support [Bero, ported by quatric]',
           '*%s' % label,
           '*Adds SDHC (>2GB) SD card support.']
    for name, addr, orig, payload in build.HOOKS:
        p = rebase_payload(payload, delta)
        if len(p) % 2:
            p.append(0)
        out.append('* %s' % name)
        out.append('C2%06X %08X' % ((addr + delta) & 0x01FFFFFF, len(p) // 2))
        for i in range(0, len(p), 2):
            out.append('%08X %08X' % (p[i], p[i + 1]))
    out.append('* bl redirects into the helpers')
    for name, addr, tgt, orig in build.BLS:
        a = addr + delta
        out.append('04%06X %08X' % (a & 0x01FFFFFF, build.bl(tgt, a)))
    for name, addr, words in build.HELPERS:
        out.append('* %s' % name)
        out.append('06%06X %08X' % (addr & 0x01FFFFFF, len(words) * 4))
        w = list(words)
        if len(w) % 2:
            w.append(0)
        for i in range(0, len(w), 2):
            out.append('%08X %08X' % (w[i], w[i + 1]))
    return '\n'.join(out) + '\n'


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'riivolution'))
    os.makedirs(os.path.join(OUT, 'gecko'))
    rc = 0
    for gid, (label, src, delta) in TARGETS.items():
        if not os.path.exists(src):
            print('  SKIP %s: no source DOL at %s' % (gid, src))
            rc = 1
            continue
        d = Dol(src)
        bad = verify_target(d, delta)
        if bad:
            print('  FAIL %s: %s' % (gid, ', '.join(bad)))
            rc = 1
            continue
        patches, cave_end = rebased_patches(delta)
        data = bytearray(d.data)
        for va, blob in patches:
            fo = d.v2f(va)
            assert fo is not None, '%s: unmapped 0x%08X' % (gid, va)
            data[fo:fo + len(blob)] = blob
        ddir = os.path.join(OUT, gid, 'sys')
        os.makedirs(ddir)
        open(os.path.join(ddir, 'main.dol'), 'wb').write(bytes(data))
        open(os.path.join(OUT, 'riivolution', '%s.xml' % gid), 'w').write(
            riivolution_xml(gid, label, patches))
        open(os.path.join(OUT, 'gecko', '%s.txt' % gid), 'w').write(
            gecko_text(gid, label, delta))
        print('  ok   %-7s delta %+5d  %d writes  cave..0x%08X  %s'
              % (gid, delta, len(patches), cave_end, label))
    return rc


if __name__ == '__main__':
    sys.exit(main())
