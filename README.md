# ACCF-SDHC

SDHC (>2 GB) SD card support for *Animal Crossing: City Folk* on Wii.

Ported from **SDHC Extension 1.1 [Bero]** by way of *My Pokémon Ranch*.

> ## ⚠️ Work in progress — not ready for use
>
> This patch is **not finished and not confirmed working on hardware.** It has
> been verified statically and confirmed resident in emulator memory, but the SD
> path itself has **never actually been exercised** — no SDHC card has been read
> or written with it, on console or in emulation.
>
> There is also a known unresolved problem, described under
> [Open problems](#open-problems), that may mean the patch cannot work as-is.
> Do not rely on this for real saves yet.

## What it does

City Folk's bundled PFD SD driver only understands standard-capacity cards: it
assumes byte addressing and reads capacity from a CSD v1 record. SDHC cards use
block addressing and a CSD v2 record, so the stock game either misreads the card
size or writes to the wrong offsets.

The patch adds three things:

- reads the OCR **CCS** bit at mount time and latches an "is SDHC" flag
- parses **CSD v2** capacity (`(C_SIZE + 1) × 1024` sectors of 512 bytes)
- switches the read/write paths to **block addressing** when that flag is set

It touches only the SD driver.

## Supported discs

| Disc ID  | Version                        | Rebase from `RUUE01` |
|----------|--------------------------------|----------------------|
| `RUUE01` | City Folk (USA/Asia, Rev 1)    | —                    |
| `RUUE02` | City Folk **Deluxe** (USA)     | −292 (−0x124)        |
| `RUUJ02` | City Folk **Deluxe** (Japan)   | +124 (+0x7C)         |
| `RUUP02` | City Folk **Deluxe** (PAL)     | −724 (−0x2D4)        |

The three Deluxe builds are uniform rebases of the USA Rev 1 map. Helper and
trampoline addresses are absolute and do **not** move between regions; only the
ten patch sites shift, along with the two `bctr` return addresses embedded in the
hook2 and hook4 payloads.

### Not supported: `RUUK02` (Deluxe, Korea) — and it does not need to be

The Korean Deluxe build ships a **newer PFD library revision** that already
supports SDHC natively. Its `pfd_sddrv_get_total_sectors` (`0x80220400`) tests
`CSD_STRUCTURE` and branches to its own CSD v2 path at `0x80220504` computing
`(C_SIZE + 1) << 10` sectors — the same result this patch adds — and its mount
code already checks the OCR CCS bit (`0x802222F0`, `0x80222324`), which the other
regions do not. It also carries `pfd_sddrv_calc_fat32_mbr_bpb()`, absent from
`RUUE02`.

**Do not patch RUUK02.** Applying this would be redundant and risks
double-converting block addresses.

## Contents

- `gecko/` — Gecko codes, one per disc ID (needs a code handler)
- `riivolution/` — Riivolution `<memory>` patches, one per disc ID
- `tools/` — the porting, build and verification scripts

No game binaries are included, and none should ever be committed here. The tools
operate on your own dumps; see `tools/paths.py`.

## How it works

Three helper routines and four trampolines are written into dead padding in the
exception-vector image at `0x80005C00`, and ten sites in the SD driver are
redirected into them. The cave runs `0x80005C00`–`0x80005D38`, inside padding
that ends at `0x800060C0`. The static (DOL) form needs no code handler; the Gecko
form does.

Nine of the ten sites are byte-identical to the *My Pokémon Ranch* originals, so
Bero's register assumptions carry over unchanged. The tenth (hook4) differs only
in its r13 SDA offset.

## Open problems

**The card may never initialise.** The game issues its own ACMD41
(`li r4,0x29` at `0x8021F120` in `RUUE01`), and that call passes **argument 0** —
no HCS bit (`0x40000000`). Per the SD spec, an SDHC card will not complete
initialisation if the host never requests high capacity. That is the standard
first *inquiry* ACMD41, so a second one may supply the real voltage window and
HCS — the command builder at `0x802202B0` takes its argument from a struct field
rather than a literal — but this has not been confirmed. If no HCS is ever set,
the port needs an additional hook there and will not work until it has one.

**IOS.** The disc TMD requires **IOS 38**. Whether IOS 38's SDIO module supports
SDHC at all is unconfirmed. This cannot be answered in Dolphin, which HLEs
`/dev/sdio` and supports SDHC regardless of IOS version. `tools/mkios58.sh`
retargets a disc at IOS 58 for testing by rewriting the TMD `sys_version` field;
that invalidates the TMD signature, so its output is for testing only.

**Untested end to end.** The flag at `0x80005C70` has never been observed set,
because City Folk only mounts the card when an SD feature is used, not at the
title screen.

## Verification

`tools/verify.py` and `tools/distverify.py` check the invariants that matter:
each C2 hook still executes the instruction it overwrote, every `bl` redirect
lands exactly on a helper entry, helpers end in `blr`, trampolines return to
site+4, the cave was zero beforehand and does not overflow, and nothing outside
the intended writes changed.

`tools/boottest.py` confirms the patch is resident in live MEM1 through Dolphin's
GDB stub (`GDBPort` in `Dolphin.ini`, launch with `-d`). The stub accepts one
client per run, so it does halt → resume → interrupt → verify in a single
connection.

## Credits

- **Bero** — original *SDHC Extension 1.1*, which this is a port of
- Wiimm — [wit / Wiimms ISO Tools](https://wit.wiimm.de/)

## Contact

quatricsoftware@gmail.com

No support will be provided for this tool.

## License

Copyright (c) 2026 quatric
