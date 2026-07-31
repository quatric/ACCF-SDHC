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

| File       | Disc ID  | Rev | Version                                       | Rebase   |
|------------|----------|-----|-----------------------------------------------|----------|
| `RUUE01v0` | `RUUE01` | 0   | City Folk (USA)                               | −292     |
| `RUUE01v1` | `RUUE01` | 1   | City Folk (USA/Asia)                          | —        |
| `RUUJ01v1` | `RUUJ01` | 1   | Machi e Ikou yo: Doubutsu no Mori (Japan)     | +124     |
| `RUUJ01v2` | `RUUJ01` | 2   | Machi e Ikou yo: Doubutsu no Mori (Japan)     | +416     |
| `RUUE02`   | `RUUE02` | 0   | City Folk **Deluxe** (USA)                    | −292     |
| `RUUJ02`   | `RUUJ02` | 1   | City Folk **Deluxe** (Japan)                  | +124     |
| `RUUP02`   | `RUUP02` | 0   | City Folk **Deluxe** (PAL)                    | −724     |

Rebase is relative to the `RUUE01` Rev 1 site map. Helper and trampoline
addresses are absolute and do **not** move between builds; only the ten patch
sites shift, along with the two `bctr` return addresses embedded in the hook2 and
hook4 payloads.

### ⚠️ Revision matters — check yours first

`RUUE01` covers **both** USA revisions and `RUUJ01` covers **both** Japanese
ones, and each revision needs a *different* set of addresses. Applying the wrong
revision's patch overwrites unrelated live code — all four hook sites land on
different instructions — and **will crash**.

The Riivolution XMLs match on the disc version byte as well as the game ID
(`<id game="RUUE01" version="0" />`), so they cannot misapply. **Gecko codes
cannot do this** — cheat managers match on the 6-character ID only and have no
way to test the revision, so picking the right file is on you. Each Gecko file
states its revision in the header.

You can read the disc version byte at offset 7 of the disc header (offset
`0x207` in a `.wbfs`).

### Not supported: Europe / PAL vanilla (`RUUP01`)

Not done — the PAL vanilla disc (*Animal Crossing: Let's Go to the City*) was not
available to derive a site map from. Deluxe PAL (`RUUP02`) **is** covered.

Its rebase of −724 is unique among the builds tested, which is a hint but not
evidence: `RUUE02` shares Rev 0's −292 and `RUUJ02` shares JP Rev 1's +124, so
each Deluxe build appears to be built on its region's vanilla base. That would
suggest `RUUP01` also sits at −724, but **do not assume it** — it has not been
checked against a real disc, and an unverified guess here crashes.

### Not supported: Korea (`RUUK01`, `RUUK02`) — and it does not need to be

Both the Korean vanilla disc and Korean Deluxe ship a **newer PFD library
revision** that already supports SDHC natively.

`pfd_sddrv_get_total_sectors` (`0x80220400`) tests `CSD_STRUCTURE`
(`rlwinm. r0,r0,0,9,9` at `0x80220484`) and branches to its own CSD v2 path at
`0x80220504` computing `(C_SIZE + 1) << 10` sectors — the same result this patch
adds — and the mount code already checks the OCR CCS bit (`0x802222F0`,
`0x80222324`), which the other regions do not. Both carry
`pfd_sddrv_calc_fat32_mbr_bpb()`, absent from every non-Korean build, and both
have the CSD v2 test at the identical address, so Korean Deluxe is built directly
on Korean vanilla.

**Do not patch either Korean disc.** It would be redundant and risks
double-converting block addresses. They should already work with SDHC cards as
shipped.

Note the Korean vanilla disc also requires **IOS 48**, not IOS 38 like every
other build here.

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
