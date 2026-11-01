"""Pure helpers for `beet sacd-migrate`: where sacdfs shows a track, and whether library items
are the extracts of an ISO's area. No beets, no pysacd imports: callers pass plain values."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

DURATION_TOLERANCE = 2.0        # seconds; extracts cut with or without pauses differ by less
AREA_DIRS = {"stereo": "Stereo", "multichannel": "Multichannel"}


def _holds_only(directory: Path, child: str) -> bool:
    try:
        return os.listdir(directory) == [child]
    except OSError:
        return False


def image_folder(iso: Path, source: Path | None, flatten: bool) -> Path:
    """The folder sacdfs shows an image as, relative to the mount point: the image's directory
    relative to SOURCE plus the file name without `.iso`, or with `flatten` (sacdfs --flatten)
    the outermost folder of the chain of folders that hold only this image. SOURCE's own
    top-level folders are never collapsed."""
    rel = iso.relative_to(source) if source is not None else Path(iso.name)
    parts = rel.parts[:-1]                  # the folders between SOURCE and the image
    stem = iso.name[:-4] if iso.name.lower().endswith(".iso") else iso.name
    if not flatten or len(parts) < 2 or source is None:
        return Path(*parts, stem)
    names = [*parts, iso.name]
    dirs = [source.joinpath(*parts[:i + 1]) for i in range(len(parts))]
    keep = len(parts)                       # index of the outermost folder of the chain
    for i in range(len(parts) - 1, 0, -1):  # parts[0] is a top-level folder: never collapsed
        if _holds_only(dirs[i], names[i + 1]):
            keep = i
        else:
            break
    return Path(*parts[:keep + 1])


def sacdfs_name(number: int, title: str | None, ext: str) -> str:
    """A track's file name: `NN - Title.ext`, or `NN.ext` without a title."""
    safe = (title or "").replace("/", "_").replace("\0", "").strip()
    return f"{number:02d} - {safe}.{ext}" if safe else f"{number:02d}.{ext}"


def sacdfs_path(iso: Path, source: Path | None, flatten: bool, area: str, number: int,
                title: str | None, ext: str = "dsf") -> str:
    """Where a mounted sacdfs shows a track, relative to its mount point."""
    return (image_folder(iso, source, flatten) / AREA_DIRS[area] / sacdfs_name(number, title, ext)).as_posix()


def durations_match(item_lengths: Sequence[float], toc_seconds: Sequence[float]) -> bool:
    """Items (in track order) agree with the area's tracks in number and length."""
    return len(item_lengths) == len(toc_seconds) and all(
        abs(a - b) <= DURATION_TOLERANCE for a, b in zip(item_lengths, toc_seconds, strict=True))
