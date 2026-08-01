#!/usr/bin/env python3
"""Change a Wii TMD's required IOS for SDHC testing.

ACCF's stock TMD requests IOS 38. IOS 38 does not expose the SDv2 path
needed to initialize SDHC cards; IOS 58 does. Changing this field invalidates
the TMD signature, so the result is for Dolphin or a fakesigned loader only.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

SIG_HEADERS = {
    0x00010000: 0x240,  # RSA-4096
    0x00010001: 0x140,  # RSA-2048
    0x00010002: 0x80,   # ECC
}


def locate(data: bytes) -> int:
    sig = struct.unpack_from(">I", data)[0]
    if sig not in SIG_HEADERS:
        raise ValueError(f"unsupported TMD signature type 0x{sig:08X}")
    return SIG_HEADERS[sig] + 0x44


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tmd", type=Path)
    ap.add_argument("ios", type=int, nargs="?", default=58)
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    data = bytearray(args.tmd.read_bytes())
    off = locate(data)
    old = struct.unpack_from(">Q", data, off)[0]
    if old >> 32 != 1:
        raise ValueError(f"unexpected sys_version 0x{old:016X}")
    if args.show:
        print(f"sys_version: 0x{old:016X} (IOS {old & 0xFF})")
        return 0
    if not 0 <= args.ios <= 0xFF:
        raise ValueError("IOS must be in the range 0..255")
    new = (1 << 32) | args.ios
    if not args.no_backup:
        backup = args.tmd.with_suffix(args.tmd.suffix + ".bak")
        if backup.exists():
            raise FileExistsError(f"backup already exists: {backup}")
        backup.write_bytes(data)
    struct.pack_into(">Q", data, off, new)
    args.tmd.write_bytes(data)
    print(f"sys_version: IOS {old & 0xFF} -> IOS {args.ios}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
