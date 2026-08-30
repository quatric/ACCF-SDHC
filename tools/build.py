"""Build the ACCF (RUUE01 Rev1) SDHC Extension patch in three forms:
     1. Gecko code text (Dolphin .ini / .gct source)
     2. a static main.dol patch (trampolines in the codecave -- no codehandler)
     3. Riivolution <memory> patch elements

Ported from "SDHC Extension 1.1 [Bero]" via My Pokemon Ranch (see memory
ranch-sdhc-port).  Every site was located by masked byte-signature search and
the surrounding code verified instruction-identical, so Bero's register
assumptions (r22/r25/r19...) carry over unchanged.
"""
import struct

# ---------------------------------------------------------------- addresses
CAVE = 0x80005C00           # dead padding in .init's exception-vector image
H1   = 0x80005C00           # 0x20 : block-vs-byte address for Read/WriteMultiBlockAsync
H2   = 0x80005C20           # 0x28 : block-vs-byte for pfd_sddrv_physical_read/write
H3   = 0x80005C48           # 0x24 : sector-advance step
FLAG = 0x80005C70           # 1 = card reported SDHC (block addressing)
TRAMP = 0x80005C80          # static-patch trampolines start here

def b(target, frm, lk=0):
    off = (target - frm) & 0xFFFFFFFF
    if off & 0x02000000:
        off |= 0xFC000000
    off = (target - frm)
    assert -0x2000000 <= off < 0x2000000, hex(off)
    return 0x48000000 | (off & 0x03FFFFFC) | lk

def bl(target, frm):
    return b(target, frm, lk=1)

# ------------------------------------------------------------------- C2 hooks
# each: (name, address, original instruction word, payload words)
# payload's LAST word is the slot the codehandler overwrites with the branch-back.
HOOKS = [
    ('hook1 SD_GetDeviceStatus: latch SDHC bit', 0x80224250, 0x2C1D0000, [
        0x546302D7,   # rlwinm. r3,r3,0,11,11      ; OCR bit30 (CCS) -> high capacity
        0x41820014,   # beq     +0x14
        0x38600001,   # li      r3,1
        0x3C808000,   # lis     r4,0x8000
        0x60845C70,   # ori     r4,r4,0x5C70
        0x90640000,   # stw     r3,0(r4)           ; FLAG = 1
        0x2C1D0000,   # cmpwi   r29,0              ; <- original
        0x00000000,   # <- branch-back
    ]),
    ('hook2 pfd_sddrv_get_total_sectors: CSD v2 size', 0x8021FAC8, 0x80A1000C, [
        0x80610014,   # lwz     r3,0x14(r1)
        0x54630253,   # rlwinm. r3,r3,0,9,9        ; CSD_STRUCTURE == 1 ?
        0x41820028,   # beq     +0x28              ; no -> original CSD v1 path
        0x38000009,   # li      r0,9
        0x8061000C,   # lwz     r3,0xc(r1)
        0x5463C2BE,   # rlwinm  r3,r3,24,10,31     ; C_SIZE (v2, 22-bit)
        0x38630001,   # addi    r3,r3,1
        0x1CC30400,   # mulli   r6,r3,0x400        ; sectors = (C_SIZE+1) * 1024
        0x3C608021,   # lis     r3,0x8021
        0x6063FB08,   # ori     r3,r3,0xFB08       ; -> site+0x40
        0x7C6903A6,   # mtctr   r3
        0x4E800420,   # bctr
        0x80A1000C,   # lwz     r5,0xc(r1)         ; <- original
        0x00000000,   # <- branch-back
    ]),
    ('hook3 duCommandv: block-count arg', 0x80224324, 0x38C00001, [
        0x38C00000,   # li      r6,0
        0x2C160000,   # cmpwi   r22,0              ; r22 = FLAG, set by helper1
        0x41820008,   # beq     +8
        0x38C00001,   # li      r6,1               ; <- original
        0x60000000,   # nop
        0x00000000,   # <- branch-back
    ]),
    ('hook4 duCommandv: 4-word response copy', 0x8022444C, 0x806DD6CC, [
        0x807C001C,   # lwz     r3,0x1c(r28)
        0x2C030001,   # cmpwi   r3,1
        0x806DD6CC,   # lwz     r3,-0x2934(r13)    ; <- original (ACCF SDA offset)
        0x41820034,   # beq     +0x34
        0x80030000, 0x90190000,
        0x80030004, 0x90190004,
        0x80030008, 0x90190008,
        0x8003000C, 0x9019000C,
        0x3C608022,   # lis     r3,0x8022
        0x60634458,   # ori     r3,r3,0x4458       ; -> site+0xC
        0x7C6903A6,   # mtctr   r3
        0x4E800420,   # bctr
        0x60000000,   # nop
        0x00000000,   # <- branch-back
    ]),
]

# --------------------------------------------------------------- bl redirects
BLS = [
    ('bl1 SD_ReadMultiBlockAsync  -> helper1', 0x8022487C, H1, 0x7C040040),
    ('bl2 SD_WriteMultiBlockAsync -> helper1', 0x80224BB8, H1, 0x7C040040),
    ('bl3 pfd_sddrv_physical_read  -> helper2', 0x8021F6D0, H2, 0x7F2531D6),
    ('bl4 pfd_sddrv_physical_write -> helper2', 0x8021F8CC, H2, 0x7F2531D6),
    ('bl5 pfd_sddrv_physical_read  -> helper3', 0x8021F81C, H3, 0x7F39BA14),
    ('bl6 pfd_sddrv_get_total_sectors -> helper3', 0x8021FA18, H3, 0x7F39BA14),
]

# -------------------------------------------------------------------- helpers
HELPERS = [
    ('helper1 @0x80005C00', H1, [
        0x3EC08000,   # lis    r22,0x8000
        0x62D65C70,   # ori    r22,r22,0x5C70
        0x82D60000,   # lwz    r22,0(r22)          ; r22 = FLAG (also read by hook3)
        0x2C160000,   # cmpwi  r22,0
        0x41820008,   # beq    +8
        0x7C802378,   # mr     r0,r4               ; SDHC: address already in blocks
        0x7C040040,   # cmplw  r4,r0               ; <- original
        0x4E800020,   # blr
    ]),
    ('helper2 @0x80005C20', H2, [
        0x3F008000,   # lis    r24,0x8000
        0x63185C70,   # ori    r24,r24,0x5C70
        0x83180000,   # lwz    r24,0(r24)
        0x2C180000,   # cmpwi  r24,0
        0x4182000C,   # beq    +0xC
        0x7CB92B78,   # mr     r25,r5              ; SDHC: sector index as-is
        0x48000008,   # b      +8
        0x7F2531D6,   # mullw  r25,r5,r6           ; <- original (byte offset)
        0x548006FF,   # clrlwi. r0,r4,0x1b         ; restore CR0 for caller
        0x4E800020,   # blr
    ]),
    ('helper3 @0x80005C48', H3, [
        0x3C608000,   # lis    r3,0x8000
        0x60635C70,   # ori    r3,r3,0x5C70
        0x80630000,   # lwz    r3,0(r3)
        0x2C030000,   # cmpwi  r3,0
        0x4182000C,   # beq    +0xC
        0x3B390001,   # addi   r25,r25,1           ; SDHC: advance one block
        0x48000008,   # b      +8
        0x7F39BA14,   # add    r25,r25,r23         ; <- original (advance bytes)
        0x4E800020,   # blr
    ]),
]


def gecko_lines():
    out = []
    out.append('$SDHC Support [Bero, ported by quatric]')
    out.append('*Adds SDHC (>2GB) card support to Animal Crossing: City Folk.')
    out.append('*USA/Asia Rev 1 (RUUE01) -- also covers City Folk Deluxe [RUUE02].')
    for name, addr, orig, payload in HOOKS:
        p = list(payload)
        if len(p) % 2:
            p.append(0x00000000)
        out.append(f'* {name}')
        out.append(f'C2{addr & 0x01FFFFFF:06X} {len(p)//2:08X}')
        for i in range(0, len(p), 2):
            out.append(f'{p[i]:08X} {p[i+1]:08X}')
    out.append('* bl redirects into the helpers')
    for name, addr, tgt, orig in BLS:
        out.append(f'04{addr & 0x01FFFFFF:06X} {bl(tgt, addr):08X}')
    for name, addr, words in HELPERS:
        out.append(f'* {name}')
        out.append(f'06{addr & 0x01FFFFFF:06X} {len(words)*4:08X}')
        w = list(words)
        if len(w) % 2:
            w.append(0x00000000)
        for i in range(0, len(w), 2):
            out.append(f'{w[i]:08X} {w[i+1]:08X}')
    return out


def static_patches():
    """(vaddr, bytes) list for a permanent main.dol patch -- no codehandler."""
    patches = []
    for name, addr, words in HELPERS:
        patches.append((addr, b''.join(struct.pack('>I', x) for x in words)))
    for name, addr, tgt, orig in BLS:
        patches.append((addr, struct.pack('>I', bl(tgt, addr))))
    cur = TRAMP
    for name, addr, orig, payload in HOOKS:
        body = list(payload[:-1]) + [b(addr + 4, cur + 4 * (len(payload) - 1))]
        patches.append((addr, struct.pack('>I', b(cur, addr))))
        patches.append((cur, b''.join(struct.pack('>I', x) for x in body)))
        cur += 4 * len(body)
    assert cur < 0x800060C0, 'trampolines overflow the codecave'
    return patches, cur


if __name__ == '__main__':
    for l in gecko_lines():
        print(l)
    p, end = static_patches()
    print(f'\n* static patch: {len(p)} writes, cave used 0x{CAVE:08X}..0x{end:08X}')
