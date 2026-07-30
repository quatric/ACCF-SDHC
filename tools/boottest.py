"""Boot-test the patched disc and confirm the SDHC patch is live in MEM1.

Dolphin's GDB stub only accepts one client per run, so the whole flow -- halt at
boot, resume, let the apploader load the DOL, interrupt, verify -- happens in a
single connection.
"""
import sys, time, struct
from gdbmem import Gdb
import build, dist

DELTA = 0            # RUUE01
fail = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        fail.append(msg)
    return cond


g = Gdb(timeout=25)
print('stop reply:', g.cmd('?'))

disc = g.read_mem(0x80000000, 6).decode('ascii', 'replace')
check(disc == 'RUUE01', 'disc id in MEM1 is %r' % disc)

# Let the apploader run and hand off to the game.
print('\nresuming; letting the game boot...')
g.cont()
time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 40)

print('interrupting...')
r = g.interrupt()
print('  stop reply:', r)
if r is None:
    print('  could not interrupt -- stub may still be running')

patches, cave_end = dist.rebased_patches(DELTA)

print('\n== codecave resident in MEM1 ==')
for va, blob in sorted(patches):
    if not (build.CAVE <= va < 0x800060C0):
        continue
    got = g.read_mem(va, len(blob))
    check(got == blob, 'cave 0x%08X+0x%02X matches the built patch' % (va, len(blob)))

print('\n== patch sites redirected in MEM1 ==')
for va, blob in sorted(patches):
    if build.CAVE <= va < 0x800060C0:
        continue
    got = g.read_mem(va, len(blob))
    w = struct.unpack('>I', got)[0]
    exp = struct.unpack('>I', blob)[0]
    check(w == exp, 'site 0x%08X holds %08X (branch into cave)' % (va, w))

print('\n== SDHC flag ==')
flag = struct.unpack('>I', g.read_mem(build.FLAG, 4))[0]
print('  FLAG @0x%08X = %d  (%s)' % (build.FLAG, flag,
      'card reported SDHC' if flag else 'no SDHC card seen yet -- expected without an SDHC image mounted'))

print('\nresuming game.')
g.cont()
time.sleep(1)
g.close()

print()
print('PATCH VERIFIED LIVE IN MEMORY' if not fail else '%d FAILURES' % len(fail))
sys.exit(1 if fail else 0)
