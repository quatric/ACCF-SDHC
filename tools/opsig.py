"""Register-insensitive signature search.

RUUK02 (ACCF Deluxe Korea) recompiled the SD driver with a different register
allocation, so the masked *byte* search in sigsearch.py finds nothing. This
masks the register operand fields as well, keeping only the opcode / extended
opcode and the structural shape, which still pins a function down when the
instruction sequence is unchanged.
"""
import struct
from dol import Dol


def op_key(w):
    """Opcode-only fingerprint of one instruction word."""
    op = w >> 26
    if op in (16, 18):                      # bc, b -- relative, fully volatile
        return (op,)
    if op == 31:                            # X/XO form: keep extended opcode
        return (op, (w >> 1) & 0x3FF)
    if op == 19:                            # bclr/bcctr etc
        return (op, (w >> 1) & 0x3FF)
    if op in (7, 8, 12, 13, 14, 15):        # mulli/subfic/addic/addi/addis
        return (op,)
    if 24 <= op <= 29:                      # ori/oris/xori/.../andis
        return (op,)
    if op in (20, 21, 23):                  # rlwimi/rlwinm/rlwnm: keep shift+mask
        return (op, (w >> 11) & 0x1F, (w >> 6) & 0x1F, (w >> 1) & 0x1F)
    if 32 <= op <= 55:                      # D-form loads/stores
        return (op,)
    if op in (10, 11):                      # cmpli/cmpi
        return (op,)
    return (op,)


def make_opsig(data):
    n = len(data) // 4
    words = struct.unpack('>%dI' % n, data[:n * 4])
    return [op_key(w) for w in words]


def find_ops(hay_words, keys, limit=16):
    n = len(keys)
    H = hay_words
    hits = []
    # anchor on the rarest distinctive key to keep the scan cheap
    for i in range(len(H) - n + 1):
        if H[i] != keys[0]:
            continue
        if all(H[i + j] == keys[j] for j in range(n)):
            hits.append(i * 4)
            if len(hits) >= limit:
                break
    return hits


def word_keys(dol):
    n = len(dol.data) // 4
    W = struct.unpack('>%dI' % n, dol.data[:n * 4])
    return [op_key(w) for w in W], W
