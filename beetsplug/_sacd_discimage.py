"""Identify DVD-Audio, DVD-Video and Blu-ray disc images, for cataloguing only.

The sacd plugin converts SACD images through pysacd. Other disc images in the same folders are
not converted, but the plugin says what they are: this module reads an image's file system and
looks for the standard top-level folders.

- DVD-Audio: AUDIO_TS holding AUDIO_TS.IFO (DVD-Video discs often carry an empty AUDIO_TS)
- DVD-Video: VIDEO_TS holding VIDEO_TS.IFO
- Blu-ray:   BDMV holding index.bdmv

UDF is read first (ECMA-167 / OSTA UDF 1.02 to 2.60, including the metadata partition of UDF
2.50 that Blu-ray uses), then ISO 9660 for images without UDF. Only the root directory and those
folders are listed. Images are untrusted: every read is bounded, and a malformed or unexpected
file system gives kind "unknown", never an exception.
"""

from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass

SECTOR = 2048
MAX_DIR = 1 << 20            # bytes of one directory, at most
MAX_EXTENTS = 64             # allocation descriptors followed per file
MAX_VDS = 64                 # volume descriptor sequence sectors read
MAX_MAPS = 8                 # partition maps read

KINDS = {"dvd-audio": "DVD-Audio", "dvd-video": "DVD-Video", "bluray": "Blu-ray", "unknown": "unknown"}


@dataclass
class DiscImage:
    kind: str                # a key of KINDS
    label: str = ""          # volume label as recorded: untrusted text
    titles: int = 0          # DVD title sets (ATS or VTS), Blu-ray playlists
    video: bool = False      # a DVD-Audio disc with a DVD-Video part as well

    @property
    def name(self) -> str:
        return KINDS[self.kind] + (" + DVD-Video" if self.video else "")


class _Bad(Exception):
    """The file system isn't what it claims to be."""


# Where a directory's entry is: (UDF block, partition reference) or (ISO 9660 extent, size)
Handle = tuple[int, int]
# A directory listing: upper-case name -> (is a directory, handle to list it with)
Listing = dict[str, tuple[bool, Handle]]
Extents = list[tuple[int, int]]            # (length in bytes, first image sector)


class _Image:
    def __init__(self, f) -> None:
        self.f = f
        f.seek(0, os.SEEK_END)
        self.sectors = f.tell() // SECTOR

    def read(self, sector: int, length: int = SECTOR) -> bytes:
        if not (sector >= 0 and 0 <= length <= MAX_DIR and sector + -(-length // SECTOR) <= self.sectors):
            raise _Bad("read outside the image")
        self.f.seek(sector * SECTOR)
        data = self.f.read(length)
        if len(data) != length:
            raise _Bad("short read")
        return data


# ---------------------------------------------------------------- UDF

def _tag(data: bytes, *idents: int) -> int:
    """Check an ECMA-167 descriptor tag (identifier and checksum); returns the identifier."""
    if len(data) < 16:
        raise _Bad("short descriptor")
    tid: int = struct.unpack_from("<H", data)[0]
    if tid not in idents:
        raise _Bad(f"descriptor {tid}, expected {idents}")
    if (sum(data[:4]) + sum(data[5:16])) & 0xFF != data[4]:
        raise _Bad("descriptor checksum")
    return tid


def _dchars(raw: bytes) -> str:
    """OSTA compressed unicode: compression id 8 (8-bit) or 16 (UTF-16BE)."""
    if raw[:1] == b"\x08":
        return raw[1:].decode("latin-1")
    if raw[:1] == b"\x10":
        return raw[1:len(raw) - (len(raw) - 1) % 2].decode("utf-16-be", "replace")
    return ""


class _Udf:
    def __init__(self, img: _Image) -> None:
        self.img = img
        avdp = img.read(256)                                # anchor volume descriptor pointer
        _tag(avdp, 2)
        length, loc = struct.unpack_from("<II", avdp, 16)
        parts: dict[int, int] = {}                          # partition number -> start sector
        lvd = None
        for i in range(min(length // SECTOR, MAX_VDS)):
            d = img.read(loc + i)
            tid = struct.unpack_from("<H", d)[0]
            if tid == 8:                                    # terminating descriptor
                break
            if tid == 5:                                    # partition descriptor
                _tag(d, 5)
                parts[struct.unpack_from("<H", d, 22)[0]] = struct.unpack_from("<I", d, 188)[0]
            elif tid == 6:                                  # logical volume descriptor
                _tag(d, 6)
                lvd = d
        if lvd is None or not parts:
            raise _Bad("no logical volume")
        if struct.unpack_from("<I", lvd, 212)[0] != SECTOR:
            raise _Bad("logical block size")
        n = lvd[84 + 127]                                   # dstring: length in the last byte
        self.label = _dchars(lvd[84:84 + n]) if n < 128 else ""
        self.fsd = struct.unpack_from("<IIH", lvd, 248)     # extent length, block, partition ref
        maps_len, n_maps = struct.unpack_from("<II", lvd, 264)
        table = lvd[440:440 + maps_len]

        def start(number: int) -> int:
            if number not in parts:
                raise _Bad("unknown partition")
            return parts[number]

        # partition reference -> ("phys", start sector) | ("meta", extents of the metadata file)
        self.maps: list[tuple[str, int, Extents]] = []
        pos = 0
        for _ in range(min(n_maps, MAX_MAPS)):
            if pos + 2 > len(table) or table[pos + 1] < 6 or pos + table[pos + 1] > len(table):
                raise _Bad("partition map")
            mtype, mlen = table[pos], table[pos + 1]
            entry = table[pos:pos + mlen]
            if mtype == 1:
                self.maps.append(("phys", start(struct.unpack_from("<H", entry, 4)[0]), []))
            elif mtype == 2 and mlen >= 44 and entry[5:28] == b"*UDF Metadata Partition":
                number, meta_file = struct.unpack_from("<HI", entry, 38)
                first = start(number)
                # The metadata file's data, in physical partition `number`, holds the blocks of
                # this partition in order
                extents, _ = self._ads(first + meta_file, physical=first)
                self.maps.append(("meta", 0, extents))
            else:
                self.maps.append(("other", 0, []))          # virtual, sparable: not needed here
            pos += mlen

    def sector(self, ref: int, block: int) -> int:
        """The image sector of logical block `block` of partition reference `ref`."""
        if not 0 <= ref < len(self.maps):
            raise _Bad("partition reference")
        kind, first, extents = self.maps[ref]
        if kind == "phys":
            return first + block
        if kind == "meta":                                  # the metadata file's blocks, in order
            for length, at in extents:
                n = -(-length // SECTOR)
                if block < n:
                    return at + block
                block -= n
            raise _Bad("block outside the metadata file")
        raise _Bad("unsupported partition type")

    def _ads(self, sector: int, ref: int = 0, physical: int | None = None) -> tuple[Extents, bytes]:
        """A file entry's data: (extents, embedded data). Short allocation descriptors are
        blocks of partition reference `ref`, or of the physical partition starting at sector
        `physical` (the metadata file's own entry)."""
        fe = self.img.read(sector)
        tid = _tag(fe, 261, 266)                            # file entry, extended file entry
        kind = struct.unpack_from("<H", fe, 16 + 18)[0] & 7
        at, base = (168, 176) if tid == 261 else (208, 216)
        l_ea, l_ad = struct.unpack_from("<II", fe, at)
        if base + l_ea + l_ad > SECTOR:
            raise _Bad("file entry")
        ads = fe[base + l_ea:base + l_ea + l_ad]
        if kind == 3:                                       # data embedded in the entry
            return [], ads
        size = {0: 8, 1: 16}.get(kind)
        if size is None:
            raise _Bad("allocation descriptor type")
        out = []
        for off in range(0, min(len(ads) // size, MAX_EXTENTS) * size, size):
            length, block = struct.unpack_from("<II", ads, off)
            if length >> 30 or length == 0:                 # unrecorded, or a continuation: stop
                break
            if physical is not None:
                at = physical + block
            else:
                at = self.sector(struct.unpack_from("<H", ads, off + 8)[0] if size == 16 else ref, block)
            out.append((length, at))
        return out, b""

    def _read(self, sector: int, ref: int) -> bytes:
        extents, data = self._ads(sector, ref)
        for length, first in extents:
            if len(data) + length > MAX_DIR:
                raise _Bad("directory too large")
            data += self.img.read(first, length)
        return data

    def root(self) -> Handle:
        _length, block, ref = self.fsd
        fsd = self.img.read(self.sector(ref, block))
        _tag(fsd, 256)                                      # file set descriptor
        _l, rblock, rref = struct.unpack_from("<IIH", fsd, 400)
        return (rblock, rref)

    def listdir(self, handle: Handle) -> Listing:
        block, ref = handle
        d = self._read(self.sector(ref, block), ref)
        out: Listing = {}
        pos = 0
        while pos + 38 <= len(d):
            _tag(d[pos:pos + 16], 257)                      # file identifier descriptor
            chars, l_fi = d[pos + 18], d[pos + 19]
            _l, iblock, iref = struct.unpack_from("<IIH", d, pos + 20)
            l_iu = struct.unpack_from("<H", d, pos + 36)[0]
            name = _dchars(d[pos + 38 + l_iu:pos + 38 + l_iu + l_fi])
            if not chars & 0x0C and name:                   # not deleted, not the parent
                out[name.upper()] = (bool(chars & 0x02), (iblock, iref))
            pos += (38 + l_iu + l_fi + 3) & ~3
        return out


# ---------------------------------------------------------------- ISO 9660

class _Iso9660:
    def __init__(self, img: _Image) -> None:
        self.img = img
        pvd = img.read(16)
        if pvd[:6] != b"\x01CD001":
            raise _Bad("no ISO 9660 volume")
        self.label = pvd[40:72].decode("latin-1").strip()
        # root directory record: extent at +2 and size at +10, each stored LE then BE
        self._root: Handle = (struct.unpack_from("<I", pvd, 156 + 2)[0], struct.unpack_from("<I", pvd, 156 + 10)[0])

    def root(self) -> Handle:
        return self._root

    def listdir(self, handle: Handle) -> Listing:
        extent, size = handle
        d = self.img.read(extent, min(size, MAX_DIR))
        out: Listing = {}
        pos = 0
        while pos < len(d):
            n = d[pos]
            if n == 0:                                      # records don't cross sectors
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            if n < 34 or pos + n > len(d):
                raise _Bad("directory record")
            rext, rsize = struct.unpack_from("<I", d, pos + 2)[0], struct.unpack_from("<I", d, pos + 10)[0]
            name = d[pos + 33:pos + 33 + d[pos + 32]]
            if name not in (b"\x00", b"\x01"):
                out[name.decode("latin-1").split(";")[0].rstrip(".").upper()] = (bool(d[pos + 25] & 2), (rext, rsize))
            pos += n
        return out


# ---------------------------------------------------------------- identifying

def _classify(fs: _Udf | _Iso9660) -> DiscImage:
    root = fs.listdir(fs.root())

    def folder(name: str) -> Listing:
        is_dir, handle = root.get(name, (False, (0, 0)))
        return fs.listdir(handle) if is_dir else {}

    def count(listing: Listing, pattern: str) -> int:
        return sum(1 for n in listing if re.fullmatch(pattern, n))

    bdmv = folder("BDMV")
    if "INDEX.BDMV" in bdmv:
        playlist = bdmv.get("PLAYLIST", (False, (0, 0)))
        titles = count(fs.listdir(playlist[1]), r"\d{5}\.MPLS") if playlist[0] else 0
        return DiscImage("bluray", fs.label, titles)
    audio, video = folder("AUDIO_TS"), folder("VIDEO_TS")
    if "AUDIO_TS.IFO" in audio:
        return DiscImage("dvd-audio", fs.label, count(audio, r"ATS_\d\d_0\.IFO"), "VIDEO_TS.IFO" in video)
    if "VIDEO_TS.IFO" in video:
        return DiscImage("dvd-video", fs.label, count(video, r"VTS_\d\d_0\.IFO"))
    return DiscImage("unknown", fs.label)


def identify(path: str | os.PathLike) -> DiscImage:
    """What kind of disc image `path` is. Reads only file-system structures; never raises for
    a malformed image (OSError from opening or reading the file still propagates)."""
    with open(path, "rb") as f:
        img = _Image(f)
        found = DiscImage("unknown")
        for reader in (_Udf, _Iso9660):
            try:
                found = _classify(reader(img))
            except (_Bad, struct.error, ValueError, IndexError):
                continue
            if found.kind != "unknown":
                return found
        return found
