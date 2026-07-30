import sys
from dol import Dol
import paths
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)

RANCH = paths.RANCH_DOL
ACCF  = paths.ACCF_DOL

# ranch_va -> accf_va  (derived by masked signature search)
SITES = [
    ('hook1  SD_GetDeviceStatus', 0x804A3D3C, 0x80224250),
    ('hook2  sddrv_total_sectors',0x804A1B00, 0x8021FAC8),
    ('hook3  duCommandv',         0x804A3E10, 0x80224324),
    ('hook4  duCommandv 4-word',  0x804A3F38, 0x8022444C),
    ('bl1    ReadMultiBlock',     0x804A4388, 0x8022487C),
    ('bl2    WriteMultiBlock',    0x804A46C4, 0x80224BB8),
    ('bl3    phys_read mullw',    0x804A1708, 0x8021F6D0),
    ('bl4    phys_write mullw',   0x804A1904, 0x8021F8CC),
    ('bl5    phys_read add',      0x804A1854, 0x8021F81C),
    ('bl6    total_sectors',      0x804A1A50, 0x8021FA18),
]

r = Dol(RANCH); a = Dol(ACCF)

def dis(d, va):
    b = d.read(va, 4)
    ins = list(md.disasm(b, va))
    return b.hex(), (f'{ins[0].mnemonic} {ins[0].op_str}' if ins else '??')

ok = True
for name, rva, ava in SITES:
    rh, rd = dis(r, rva)
    ah, ad = dis(a, ava)
    same = (rh == ah)
    ok &= same
    print(f'{name:28s} ranch {rva:08X} {rh} {rd:28s} | accf {ava:08X} {ah} {ad:28s} {"OK" if same else "**DIFF**"}')
print('\nall identical:', ok)
