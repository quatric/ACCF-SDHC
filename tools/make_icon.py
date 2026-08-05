#!/usr/bin/env python3
"""Rasterize assets/leaf-source.svg into the app icon.

Source: the Animal Crossing leaf, from
https://commons.wikimedia.org/wiki/File:Animal_Crossing_Leaf.svg -- Commons
tags it public domain (below the threshold of originality for copyright) but
notes it may still be a protected trademark in some jurisdictions; this is a
fan patch for the same game, not a competing product, but that's a judgment
call for whoever redistributes builds, not a settled legal fact.

Requires ImageMagick (`magick`/`convert`) to rasterize the SVG, and
`iconutil` (macOS only) for the .icns. Emits:
  assets/icon.png   (1024x1024 source, transparent, padded to square)
  assets/icon.ico   (Windows, multi-size)
  assets/icon.icns  (macOS, via iconutil -- macOS only)
"""
import os
import shutil
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'assets')
SVG = os.path.join(OUT, 'leaf-source.svg')
SIZE = 1024
PAD_FRACTION = 0.84  # leaf content fills this fraction of the square canvas


def magick_bin():
    for name in ('magick', 'convert'):
        if shutil.which(name):
            return name
    sys.exit('ImageMagick (magick/convert) not found on PATH')


def make_png(png_path):
    content = int(SIZE * PAD_FRACTION)
    subprocess.run([
        magick_bin(), '-background', 'none', '-density', '1200', SVG,
        '-resize', f'{content}x{content}',
        '-gravity', 'center', '-background', 'none', '-extent', f'{SIZE}x{SIZE}',
        png_path,
    ], check=True)


def make_ico(png_path, ico_path):
    img = Image.open(png_path)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, sizes=sizes)


def make_icns(png_path, icns_path):
    if shutil.which('iconutil') is None:
        print('  iconutil not found (macOS only) -- skipping .icns')
        return
    iconset = icns_path + '.iconset'
    if os.path.isdir(iconset):
        shutil.rmtree(iconset)
    os.makedirs(iconset)
    img = Image.open(png_path)
    for s in (16, 32, 128, 256, 512):
        img.resize((s, s), Image.LANCZOS).save(os.path.join(iconset, f'icon_{s}x{s}.png'))
        img.resize((s * 2, s * 2), Image.LANCZOS).save(os.path.join(iconset, f'icon_{s}x{s}@2x.png'))
    subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', icns_path], check=True)
    shutil.rmtree(iconset)


def main():
    if not os.path.isfile(SVG):
        sys.exit('missing %s' % SVG)
    os.makedirs(OUT, exist_ok=True)
    png_path = os.path.join(OUT, 'icon.png')
    ico_path = os.path.join(OUT, 'icon.ico')
    icns_path = os.path.join(OUT, 'icon.icns')

    print('rasterizing', SVG)
    make_png(png_path)
    print('  wrote', png_path)

    make_ico(png_path, ico_path)
    print('  wrote', ico_path)

    make_icns(png_path, icns_path)
    if os.path.exists(icns_path):
        print('  wrote', icns_path)


if __name__ == '__main__':
    sys.exit(main())
