#!/usr/bin/env python3
"""make.fun entry news-image-20261122 -- Sunday 22 November 2026 in one image.

The poster is rendered ahead of time by tools/render.py (Pillow, local only)
and committed as entry.png. This program is what the grader runs: it copies
those exact bytes to $MAKEFUN_OUTPUT_DIR/entry.png (or /output/entry.png),
using the standard library alone, with no network and no randomness, so both
runs write byte-identical output.
"""

import os
import sys

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def output_dir():
    return os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "entry.png")
    with open(src, "rb") as fh:
        data = fh.read()

    if not data.startswith(PNG_MAGIC):
        sys.stderr.write("entry.png is not a PNG\n")
        return 1

    dest_dir = output_dir()
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "entry.png")
    with open(dest, "wb") as fh:
        fh.write(data)

    # read it back: every run must land the same bytes on disk
    with open(dest, "rb") as fh:
        written = fh.read()
    if written != data:
        sys.stderr.write("short write: %d of %d bytes\n"
                         % (len(written), len(data)))
        return 1

    sys.stdout.write("wrote %s (%d bytes)\n" % (dest, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
