"""Masked byte-signature search: locate a Ranch/Brawl function inside ACCF's main.dol.

Masks out fields that legitimately differ between two links of the same object:
  - relative branches (b/bl/bc)            -> whole word
  - lis/addis, ori, and any D-form using r13/r2 (SDA) -> low 16 bits
"""
import struct, sys
from dol import Dol

def word_mask(w):
    op = w >> 26
    ra = (w >> 16) & 0x1F
    if op in (16, 18):                 # bc, b  (relative)
        return 0x00000000
    if op == 15:                       # addis/lis
        return 0xFFFF0000
    if op in (24, 25, 26, 27, 28, 29): # ori/oris/xori/xoris/andi/andis
        return 0xFFFF0000
    if op == 14:                       # addi/subi -- low half of an absolute
        return 0xFFFF0000
    if 32 <= op <= 55 and ra in (2, 13):  # lwz/stw/lbz/... off(r13|r2)
        return 0xFFFF0000
    return 0xFFFFFFFF

def make_sig(data):
    n = len(data) // 4
    words = struct.unpack('>%dI' % n, data[:n*4])
    return words, [word_mask(w) for w in words]

def find(hay, words, masks, limit=8):
    n = len(words)
    hits = []
    hw = len(hay) // 4
    H = struct.unpack('>%dI' % hw, hay[:hw*4])
    # anchor on the first fully-unmasked word to keep this fast
    anchor = next((i for i, m in enumerate(masks) if m == 0xFFFFFFFF), 0)
    a = words[anchor]
    start = 0
    while True:
        try:
            idx = H.index(a, start)
        except ValueError:
            break
        start = idx + 1
        base = idx - anchor
        if base < 0 or base + n > hw:
            continue
        if all((H[base+i] & masks[i]) == (words[i] & masks[i]) for i in range(n)):
            hits.append(base * 4)
            if len(hits) >= limit:
                break
    return hits

if __name__ == '__main__':
    src = Dol(sys.argv[1])   # reference (Ranch)
    dst = Dol(sys.argv[2])   # target (ACCF)
    for spec in sys.argv[3:]:
        name, va, ln = spec.split(':')
        va = int(va, 16); ln = int(ln, 16)
        ref = src.read(va, ln)
        words, masks = make_sig(ref)
        hits = find(dst.data, words, masks)
        vas = [dst.f2v(h) for h in hits]
        print(f'{name:32s} ref 0x{va:08X} len 0x{ln:X} -> ' +
              (', '.join('0x%08X' % v for v in vas) if vas else 'NO MATCH'))
