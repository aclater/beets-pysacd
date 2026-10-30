#!/usr/bin/env python3
"""Atheris (libFuzzer) harness for the DVD/Blu-ray identifier, beetsplug/_sacd_discimage.py (#22).

Each input is a whole disc image. It's written to a temporary file and passed to identify(),
which must return a DiscImage of a known kind or raise OSError, never anything else: images
are hostile input (CLAUDE.md). Anything else is a crash, which libFuzzer saves as crash-<sha1>.

    python fuzz/fuzz_discimage.py --seeds fuzz/seeds        # write the seed images
    python fuzz/fuzz_discimage.py -max_total_time=150 -max_len=1048576 -timeout=10 \\
        fuzz/corpus fuzz/seeds                               # fuzz (needs atheris)
    python fuzz/fuzz_discimage.py crash-...                  # replay one input

The seeds are tests/discgen.py's images: DVD-Audio, DVD-Video and Blu-ray trees in every UDF
layout it writes (1.02, 2.50 with a metadata partition, long allocation descriptors), with and
without ISO 9660, plus ISO 9660 alone. A crash's input, minimised, goes into
fuzz/regressions/ with its fix; tests/test_discimage.py replays that folder.
"""

from __future__ import annotations

import atexit
import os
import sys
import tempfile
from pathlib import Path

import atheris

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with atheris.instrument_imports():
    from beetsplug._sacd_discimage import KINDS, DiscImage, identify

# one file, rewritten for every input
_fd, IMAGE = tempfile.mkstemp(prefix="fuzz-discimage-", suffix=".iso")
os.close(_fd)
atexit.register(os.unlink, IMAGE)       # libFuzzer exits through exit()


def TestOneInput(data: bytes) -> None:
    with open(IMAGE, "wb") as f:
        f.write(data)
    try:
        found = identify(IMAGE)
    except OSError:
        return
    assert isinstance(found, DiscImage), f"identify returned {type(found).__name__}"
    assert found.kind in KINDS, f"unknown kind {found.kind!r}"
    assert isinstance(found.label, str) and isinstance(found.titles, int)


def write_seeds(out: Path) -> None:
    sys.path.insert(0, str(ROOT / "tests"))
    import discgen

    out.mkdir(parents=True, exist_ok=True)
    trees = {"dvd-audio": discgen.DVD_AUDIO, "dvd-video": discgen.DVD_VIDEO, "bluray": discgen.BLURAY}
    layouts = [("1.02", True), ("1.02", False), ("2.50", False), ("long", False), (None, True)]
    for kind, tree in trees.items():
        for udf, iso9660 in layouts:
            name = f"{kind}-udf{udf or 'none'}{'-iso9660' if iso9660 else ''}.iso"
            discgen.build(out / name, tree, "FUZZ_SEED", udf, iso9660)
    print(f"wrote {len(trees) * len(layouts)} seeds to {out}")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--seeds":
        write_seeds(Path(sys.argv[2]))
        return
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
