"""Static verification of the ACCF SDHC patch.

Applies the static form to a copy of main.dol, disassembles every touched
region, and asserts the invariants that matter:
  * each C2 hook still executes the instruction it overwrote
  * every bl redirect lands exactly on a helper entry
  * every helper ends in blr and contains no stray 0x00000000
  * trampolines branch back to site+4
  * the codecave was zero beforehand and does not overflow
"""
import struct, sys, os
from dol import Dol
import paths
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
import build

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
ACCF = paths.ACCF_DOL
OUT_DOL = os.environ.get('OUT_DOL', 'accf_sdhc.dol')

d = Dol(ACCF)
data = bytearray(d.data)
fail = []

def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        fail.append(msg)

print('== preconditions ==')
patches, cave_end = build.static_patches()
for va, blob in patches:
    if build.CAVE <= va < 0x800060C0:
        orig = d.read(va, len(blob))
        check(orig == b'\x00' * len(blob), f'cave 0x{va:08X}+0x{len(blob):X} was zero')
check(cave_end <= 0x800060C0, f'cave end 0x{cave_end:08X} within padding (0x800060C0)')
check(not any(va <= build.FLAG < va + len(blob) for va, blob in patches),
      f'FLAG 0x{build.FLAG:08X} lands in a gap, not inside any written blob')
check(d.read(build.FLAG, 4) == b'\x00\x00\x00\x00', 'FLAG word is zero in the DOL')

print('\n== C2 hooks reproduce the overwritten instruction ==')
for name, addr, orig, payload in build.HOOKS:
    have = struct.unpack('>I', d.read(addr, 4))[0]
    check(have == orig, f'{name.split(":")[0]}: DOL has {have:08X}, code declares {orig:08X}')
    check(orig in payload, f'{name.split(":")[0]}: payload contains the original {orig:08X}')
    check(payload[-1] == 0, f'{name.split(":")[0]}: last payload word is the branch-back slot')
    check(0 not in payload[:-1], f'{name.split(":")[0]}: no stray 00000000 before the last word')

print('\n== bl redirects ==')
for name, addr, tgt, orig in build.BLS:
    have = struct.unpack('>I', d.read(addr, 4))[0]
    check(have == orig, f'{name}: site holds {have:08X} (expected {orig:08X})')
    w = build.bl(tgt, addr)
    off = w & 0x03FFFFFC
    if off >= 0x02000000:
        off -= 0x04000000
    check(addr + off == tgt and (w & 1) == 1, f'{name}: bl {w:08X} -> 0x{addr+off:08X}')

print('\n== helpers ==')
for name, addr, words in build.HELPERS:
    check(words[-1] == 0x4E800020, f'{name}: ends in blr')
    check(0 not in words, f'{name}: no zero word')
    orig = [o for _, a, t, o in build.BLS if t == addr]
    check(all(o in words for o in orig), f'{name}: reproduces caller original {set(orig)}')

# ---- apply static patch and disassemble ----
for va, blob in patches:
    fo = d.v2f(va)
    assert fo is not None, hex(va)
    data[fo:fo + len(blob)] = blob
open(OUT_DOL, 'wb').write(bytes(data))
p = Dol(OUT_DOL)

print('\n== static patch: trampolines ==')
cur = build.TRAMP
for name, addr, orig, payload in build.HOOKS:
    n = len(payload)          # payload minus its branch-back slot, plus our branch-back
    site = struct.unpack('>I', p.read(addr, 4))[0]
    off = site & 0x03FFFFFC
    if off >= 0x02000000:
        off -= 0x04000000
    check((site >> 26) == 18 and (site & 3) == 0 and addr + off == cur,
          f'{name.split(":")[0]}: site branches to trampoline 0x{cur:08X}')
    last = struct.unpack('>I', p.read(cur + 4 * (n - 1), 4))[0]
    off2 = last & 0x03FFFFFC
    if off2 >= 0x02000000:
        off2 -= 0x04000000
    check((last >> 26) == 18 and (cur + 4 * (n - 1)) + off2 == addr + 4,
          f'{name.split(":")[0]}: trampoline returns to 0x{addr+4:08X}')
    cur += 4 * n

if '-v' in sys.argv:
    print('\n== disassembly of the patched cave ==')
    regions = [(a, len(bl2)) for a, bl2 in patches if build.CAVE <= a < 0x800060C0]
    for a, n in sorted(regions):
        print(f'  --- 0x{a:08X} ---')
        for ins in md.disasm(p.read(a, n), a):
            print(f'  {ins.address:08x}: {ins.mnemonic} {ins.op_str}')

print('\n' + ('ALL CHECKS PASSED' if not fail else f'{len(fail)} FAILURES'))
sys.exit(1 if fail else 0)
