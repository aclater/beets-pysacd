"""Pure helpers for `beet sacd-migrate`: where sacdfs shows a track, and whether library items
are the extracts of an ISO's area. No beets, no pysacd imports: callers pass plain values."""

from __future__ import annotations

import os
import unicodedata
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


NAME_MAX = 255      # longest file name sacdfs shows, in bytes


def _sanitize(text: str) -> str:
    """sacdfs's `names::sanitize`: `/`, NUL and control characters become `_`; the ends are trimmed."""
    return "".join("_" if c == "/" or unicodedata.category(c) == "Cc" else c for c in text).strip()


def _cut(text: str, room: int) -> str:
    """At most `room` bytes of UTF-8, cut at a character boundary."""
    return text.encode()[:room].decode("utf-8", "ignore")


def sacdfs_name(number: int, title: str | None, ext: str, *, legacy: bool = False) -> str:
    """A track's file name as sacdfs 0.4.1 and later show it (sacdfs `names::track_file_name`):
    `NN - Title.ext`, and `NN - Track NN.ext` for a track whose title is missing or empty once
    sanitised. `legacy=True` gives sacdfs 0.4.0's name for such a track, `NN.ext`."""
    safe = _sanitize(title or "")
    if not safe:
        if legacy:
            return f"{number:02d}.{ext}"
        safe = f"Track {number:02d}"
    prefix = f"{number:02d} - "
    room = max(NAME_MAX - (len(prefix) + 1 + len(ext) + 6), 0)      # room for " (NNN)" de-duplication
    return f"{prefix}{_cut(safe, room).rstrip()}.{ext}"


def sacdfs_path(iso: Path, source: Path | None, flatten: bool, area: str, number: int,
                title: str | None, ext: str = "dsf", *, legacy: bool = False) -> str:
    """Where a mounted sacdfs shows a track, relative to its mount point."""
    return (image_folder(iso, source, flatten) / AREA_DIRS[area]
            / sacdfs_name(number, title, ext, legacy=legacy)).as_posix()


def durations_match(item_lengths: Sequence[float], toc_seconds: Sequence[float]) -> bool:
    """Items (in track order) agree with the area's tracks in number and length."""
    return len(item_lengths) == len(toc_seconds) and all(
        abs(a - b) <= DURATION_TOLERANCE for a, b in zip(item_lengths, toc_seconds, strict=True))


# ----------------------------------------------------------------- sacdfs verify reports

VERIFIED = frozenset({"IDENTICAL", "IDENTICAL-PAUSE"})      # the statuses that make an extract safe to replace
_ESCAPES = {ord("t"): 9, ord("n"): 10, ord("\\"): 92}


def _unescape(field: bytes) -> bytes:
    """Undo `sacdfs verify`'s field escaping: `\\t`, `\\n`, `\\\\` and `\\xNN` (a byte that isn't UTF-8)."""
    if b"\\" not in field:
        return field
    out = bytearray()
    i = 0
    while i < len(field):
        c = field[i]
        if c == 92 and i + 1 < len(field):
            n = field[i + 1]
            if n in _ESCAPES:
                out.append(_ESCAPES[n])
                i += 2
                continue
            if n == ord("x") and i + 4 <= len(field):
                try:
                    out.append(int(field[i + 2:i + 4], 16))
                    i += 4
                    continue
                except ValueError:
                    pass
        out.append(c)
        i += 1
    return bytes(out)


def parse_verify_report(data: bytes) -> dict[bytes, bool]:
    """Read a `sacdfs verify` report (tab-separated, header row with `status` and `path`).
    Returns {absolute file path: True when every row for it is IDENTICAL or IDENTICAL-PAUSE}.
    Raises ValueError when it isn't such a report."""
    lines = data.split(b"\n")
    header = lines[0].rstrip(b"\r").split(b"\t")
    if b"status" not in header or b"path" not in header:
        raise ValueError("not a sacdfs verify report: the header row needs `status` and `path` columns")
    s, p = header.index(b"status"), header.index(b"path")
    result: dict[bytes, bool] = {}
    for line in lines[1:]:
        cols = line.rstrip(b"\r").split(b"\t")
        if len(cols) <= max(s, p):
            continue
        path = _unescape(cols[p])
        if not (path.startswith((b"/", b"\\\\")) or path[1:2] == b":"):      # relative: as given to verify
            path = os.getcwdb() + os.sep.encode() + path
        ok = cols[s].decode("ascii", "replace") in VERIFIED
        result[path] = result.get(path, True) and ok
    return result
