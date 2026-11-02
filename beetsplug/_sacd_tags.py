"""Pure helpers for `beet sacd-tags-export`: a disc's sacdfs tags key, and tags files read, merged
and written. No beets imports; callers pass plain values."""

from __future__ import annotations

import contextlib
import hashlib
import os
import struct
import tomllib
from collections.abc import Mapping
from pathlib import Path

START_OF_MASTER_TOC = 510
ART_MAX_BYTES = 960 * 1024              # what sacdfs embeds (docs/user-guide.md, "Your own tags")
AREA_SLOTS = {"stereo": 0, "multichannel": 1}
OWNED_SECTIONS = ("stereo", "multichannel")


def _stored(raw: bytes) -> bytes:
    """A fixed text field's bytes up to the first NUL, padding kept (scarletbook's `*_stored`)."""
    return raw.split(b"\0", 1)[0]


def disc_key(img, disc) -> str:
    """The key sacdfs names a disc's tags file by (`sacdfs tags key`, src/tags.rs `disc_key`):
    32 hex digits of a SHA-256 over the master and area TOCs' numbers. `img` is a pysacd
    SACDImage and `disc` its read_toc(). Two fields are not in pysacd's parsed TOC (the catalogue
    numbers with their padding, and the disc flags byte), so they come from the master TOC's
    sector, which pysacd's reader hands over."""
    m = img.read_sectors(START_OF_MASTER_TOC, 1)
    h = hashlib.sha256(b"sacdfs disc v1\0")
    h.update(struct.pack(">HH", disc.album_set_size, disc.album_sequence_number))
    for field in (m[24:40], m[88:104]):
        stored = _stored(field)
        h.update(struct.pack(">I", len(stored)) + stored)
    year, month, day = disc.date
    h.update(struct.pack(">HBBB", year, month, day, m[80]))
    h.update(struct.pack(">I", len(disc.areas)))
    for a in disc.areas:
        h.update(struct.pack(">BBIII", AREA_SLOTS["stereo" if a.is_stereo else "multichannel"],
                             a.channel_count, a.toc_start, a.track_start, a.track_end))
        h.update(struct.pack(">I", len(a.tracks)))
        for t in a.tracks:
            h.update(struct.pack(">BIIII", t.number, t.start_lsn, t.length_lsn,
                                 t.start.total_frames, t.duration.total_frames))
    return h.hexdigest()[:32]


# ---------------------------------------------------------------- TOML

def _quote(s: str) -> str:
    out = ['"']
    for c in s:
        if c in '"\\':
            out.append("\\" + c)
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif ord(c) < 0x20 or ord(c) == 0x7F:
            out.append(f"\\u{ord(c):04X}")
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def _key(k: str) -> str:
    return k if k and all(c.isascii() and (c.isalnum() or c in "-_") for c in k) else _quote(k)


def _tables(prefix: tuple[str, ...], node: Mapping, out: list[str]) -> None:
    scalars = {k: v for k, v in node.items() if not isinstance(v, Mapping)}
    tables = {k: v for k, v in node.items() if isinstance(v, Mapping)}
    if scalars:
        out.append("[" + ".".join(_key(p) for p in prefix) + "]")
        out.extend(f"{_key(k)} = {_quote(str(v))}" for k, v in scalars.items())
        out.append("")
    for k, v in tables.items():
        _tables((*prefix, k), v, out)


def dumps(data: Mapping) -> str:
    """A tags file's text: sections `album`, `track.N`, `stereo.*`, `multichannel.*`."""
    out = ["# sacdfs tags for one disc; beets-pysacd keeps the genre, MusicBrainz IDs and art in",
           "# the [stereo.*] and [multichannel.*] sections up to date. Other fields are yours.", ""]
    for k, v in data.items():
        _tables((k,), v, out)
    return "\n".join(out).rstrip("\n") + "\n"


def loads(text: str) -> dict:
    return tomllib.loads(text)


def merge(existing: Mapping, ours: Mapping) -> dict:
    """`existing` with every field of `ours` set (nested mappings merge; other fields stay)."""
    out = {k: (dict(v) if isinstance(v, Mapping) else v) for k, v in existing.items()}
    for k, v in ours.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = merge(out[k], v)
        else:
            out[k] = dict(v) if isinstance(v, Mapping) else v
    return out


def write_atomic(path: Path, data: bytes) -> bool:
    """Write `data` to `path` through a temporary file in the same folder; False (and no write,
    so no new modification time) when the file already holds exactly this."""
    try:
        if path.read_bytes() == data:
            return False
    except OSError:
        pass
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    try:
        # created with the umask's permissions, as any file the user makes
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return True


def picture_ext(b: bytes) -> str | None:
    if b.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return None
