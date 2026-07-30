"""Locate a function by the error string it references.

RUUK02 ships a newer PFD revision than RUUE02, so byte- and opcode-signature
searches both fail. The error strings survive though, and each pfd_sddrv_*
function names itself in its own ERR string, so a lis/addi (or lis/ori) pair
materialising that string's address lands us inside the right function.
"""
import struct, sys
from dol import Dol


def find_string_vas(dol, needle):
    out = []
    data = dol.data
    start = 0
    nb = needle.encode()
    while True:
        i = data.find(nb, start)
        if i < 0:
            break
        start = i + 1
        va = dol.f2v(i)
        if va is not None:
            out.append(va)
    return out


def find_refs(dol, target_va):
    """Addresses of lis rX,hi ; addi/ori rY,rX,lo pairs that build target_va."""
    n = len(dol.data) // 4
    W = struct.unpack('>%dI' % n, dol.data[:n * 4])
    hi = (target_va >> 16) & 0xFFFF
    lo = target_va & 0xFFFF
    # addi sign-extends its immediate, so the hi word may be pre-compensated
    hi_adj = (hi + 1) & 0xFFFF if lo & 0x8000 else hi
    refs = []
    for i in range(n - 1):
        w = W[i]
        if (w >> 26) != 15:                       # lis rD, imm
            continue
        rD = (w >> 21) & 0x1F
        if (w & 0xFFFF) not in (hi, hi_adj):
            continue
        for j in range(i + 1, min(i + 9, n)):     # allow a short gap
            v = W[j]
            op = v >> 26
            if op == 14 and ((v >> 16) & 0x1F) == rD:      # addi rX, rD, lo
                if (v & 0xFFFF) == lo and (w & 0xFFFF) == hi_adj:
                    refs.append(dol.f2v(i * 4))
                    break
            if op == 24 and ((v >> 21) & 0x1F) == rD:      # ori rX, rD, lo
                if (v & 0xFFFF) == lo and (w & 0xFFFF) == hi:
                    refs.append(dol.f2v(i * 4))
                    break
            if (v >> 26) == 15 and ((v >> 21) & 0x1F) == rD:
                break                                       # rD reloaded
    return refs


def func_start(dol, va, max_back=0x800):
    """Scan back for the prologue (stwu r1,-N(r1)) that opens this function."""
    a = va
    for _ in range(max_back // 4):
        b = dol.read(a, 4)
        if not b:
            return None
        w = struct.unpack('>I', b)[0]
        if (w >> 26) == 37 and ((w >> 21) & 0x1F) == 1 and ((w >> 16) & 0x1F) == 1:
            return a          # stwu r1, -N(r1)
        a -= 4
    return None


if __name__ == '__main__':
    d = Dol(sys.argv[1])
    for s in sys.argv[2:]:
        vas = find_string_vas(d, s)
        print(f'"{s[:52]}" -> ' + (', '.join('%08X' % v for v in vas) or 'not found'))
        for v in vas:
            for r in find_refs(d, v):
                fs = func_start(d, r)
                print(f'    ref @ {r:08X}   func start {fs and "%08X" % fs}')
