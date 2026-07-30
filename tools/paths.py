"""Where the reference DOLs live.

Nothing here is committed with real paths -- set these to wherever your own
dumps are. Every tool reads them from here (or from the matching environment
variable), so no script carries a hardcoded path.

  ACCF_DOL   USA Rev 1 (RUUE01) sys/main.dol -- the reference the site map is built against
  RANCH_DOL  My Pokemon Ranch 00000001.app  -- the upstream SDHC patch donor
  DIST_DIR   where build output is written
  SRC_IMAGES directory holding the source .wbfs images
"""
import os

ACCF_DOL   = os.environ.get('ACCF_DOL',   'dumps/RUUE01/sys/main.dol')
RANCH_DOL  = os.environ.get('RANCH_DOL',  'dumps/ranch/00000001.app')
DIST_DIR   = os.environ.get('DIST_DIR',   'build')
SRC_IMAGES = os.environ.get('SRC_IMAGES', 'images')
