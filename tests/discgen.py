"""Synthetic DVD and Blu-ray images for the disc-image tests: just enough UDF and ISO 9660 for a
reader to list the root and its folders. Files are empty.

    build(path, {"AUDIO_TS": {"AUDIO_TS.IFO": None}}, label="DISC", udf="1.02", iso9660=True)

A tree maps names to a dict (a folder) or None (a file). `udf` is "1.02" (one physical
partition, short allocation descriptors), "2.50" (a metadata partition and extended file
entries, as on Blu-ray), "long" (long allocation descriptors) or None.
"""

from __future__ import annotations

import struct
from pathlib import Path

SECTOR = 2048
PART = 272                  # first sector of the UDF partition
ISO_DIRS = 20               # first sector of the ISO 9660 directories


def tag(ident: int, body: bytes, location: int = 0) -> bytes:
    t = bytearray(struct.pack("<HHBBHHHI", ident, 2, 0, 0, 0, 0, 0, location))
    t[4] = (sum(t[:4]) + sum(t[5:16])) & 0xFF
    return bytes(t) + body


def dstring(text: str, size: int) -> bytes:
    raw = b"\x08" + text.encode("latin-1")
    return raw.ljust(size - 1, b"\0") + bytes([len(raw)])


def long_ad(length: int, block: int, ref: int) -> bytes:
    return struct.pack("<IIH", length, block, ref) + bytes(6)


class _Udf:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.meta = mode == "2.50"
        self.blocks: dict[int, bytes] = {}       # logical block of the file-set partition -> data
        self.next = 1                            # block 0: the file set descriptor
        self.ref = 1 if self.meta else 0         # partition reference of the file set

    def alloc(self) -> int:
        self.next += 1
        return self.next - 1

    def entry(self, data_block: int | None, length: int) -> bytes:
        ext = self.meta
        if data_block is None:
            ads, kind = b"", 0
        elif self.mode == "long":
            ads, kind = long_ad(length, data_block, self.ref), 1
        else:
            ads, kind = struct.pack("<II", length, data_block), 0
        icb = bytearray(20)
        struct.pack_into("<H", icb, 18, kind)
        head = bytearray((216 if ext else 176) - 16)
        head[0:20] = icb
        struct.pack_into("<II", head, (208 if ext else 168) - 16, 0, len(ads))
        return tag(266 if ext else 261, bytes(head) + ads)

    def directory(self, tree: dict, parent: int | None = None) -> int:
        fe, data = self.alloc(), self.alloc()
        fids = [self.fid("", True, parent if parent is not None else fe, parent=True)]
        for name, sub in tree.items():
            if isinstance(sub, dict):
                fids.append(self.fid(name, True, self.directory(sub, fe)))
            else:
                block = self.alloc()
                self.blocks[block] = self.entry(None, 0)
                fids.append(self.fid(name, False, block))
        raw = b"".join(fids)
        assert len(raw) <= SECTOR
        self.blocks[data] = raw
        self.blocks[fe] = self.entry(data, len(raw))
        return fe

    def fid(self, name: str, is_dir: bool, block: int, parent: bool = False) -> bytes:
        ident = b"\x08" + name.encode("latin-1") if name else b""
        body = struct.pack("<HBB", 1, (0x02 if is_dir else 0) | (0x08 if parent else 0), len(ident))
        body += long_ad(SECTOR, block, self.ref) + struct.pack("<H", 0) + ident
        raw = tag(257, body)
        return raw + bytes(-len(raw) % 4)

    def write(self, img: bytearray, tree: dict, label: str) -> None:
        root = self.directory(tree)
        fsd = bytearray(512 - 16)
        fsd[400 - 16:400 - 16 + 16] = long_ad(SECTOR, root, self.ref)
        self.blocks[0] = tag(256, bytes(fsd))
        # Physical layout: with a metadata partition, physical block 0 holds the metadata
        # file's entry and blocks 1.. hold the metadata partition's blocks
        base = PART + (1 if self.meta else 0)
        for block, data in self.blocks.items():
            put(img, base + block, data)
        if self.meta:
            n = max(self.blocks) + 1
            efe = bytearray(216 - 16)
            struct.pack_into("<II", efe, 208 - 16, 0, 8)
            put(img, PART, tag(266, bytes(efe) + struct.pack("<II", n * SECTOR, 1)))
        end = PART + 1 + max(self.blocks) + 1
        # anchor, volume descriptor sequence: partition, logical volume, terminator
        put(img, 256, tag(2, struct.pack("<IIII", 3 * SECTOR, 32, 3 * SECTOR, 32)))
        pd = bytearray(512 - 16)
        struct.pack_into("<H", pd, 22 - 16, 0)
        struct.pack_into("<II", pd, 188 - 16, PART, end - PART)
        put(img, 32, tag(5, bytes(pd)))
        lvd = bytearray(SECTOR - 16)
        lvd[84 - 16:84 - 16 + 128] = dstring(label, 128)
        struct.pack_into("<I", lvd, 212 - 16, SECTOR)
        maps = struct.pack("<BBHH", 1, 6, 1, 0)
        if self.meta:
            m = bytearray(64)
            m[0], m[1] = 2, 64
            m[5:28] = b"*UDF Metadata Partition"
            struct.pack_into("<HHI", m, 36, 1, 0, 0)        # volume sequence, partition 0, file at block 0
            maps += bytes(m)
        lvd[248 - 16:248 - 16 + 16] = long_ad(SECTOR, 0, self.ref)
        struct.pack_into("<II", lvd, 264 - 16, len(maps), 2 if self.meta else 1)
        lvd[440 - 16:440 - 16 + len(maps)] = maps
        put(img, 33, tag(6, bytes(lvd)))
        put(img, 34, tag(8, b""))


def _iso_record(name: bytes, extent: int, size: int, is_dir: bool) -> bytes:
    n = 33 + len(name)
    rec = bytearray(n + n % 2)
    rec[0] = len(rec)
    struct.pack_into("<I", rec, 2, extent)
    struct.pack_into(">I", rec, 6, extent)
    struct.pack_into("<I", rec, 10, size)
    struct.pack_into(">I", rec, 14, size)
    rec[25] = 2 if is_dir else 0
    rec[32] = len(name)
    rec[33:33 + len(name)] = name
    return bytes(rec)


def _iso9660(img: bytearray, tree: dict, label: str) -> None:
    sectors = iter(range(ISO_DIRS, PART))

    def directory(tree: dict, parent: int | None) -> int:
        at = next(sectors)
        recs = [_iso_record(b"\0", at, SECTOR, True), _iso_record(b"\1", parent or at, SECTOR, True)]
        for name, sub in tree.items():
            if isinstance(sub, dict):
                recs.append(_iso_record(name.encode(), directory(sub, at), SECTOR, True))
            else:
                recs.append(_iso_record(name.encode() + b";1", 0, 0, False))
        put(img, at, b"".join(recs))
        return at

    root = directory(tree, None)
    pvd = bytearray(SECTOR)
    pvd[0:7] = b"\x01CD001\x01"
    pvd[40:72] = label.encode("latin-1").ljust(32)[:32]
    pvd[156:156 + 34] = _iso_record(b"\0", root, SECTOR, True)
    put(img, 16, bytes(pvd))
    put(img, 17, b"\xffCD001\x01")


def put(img: bytearray, sector: int, data: bytes) -> None:
    img[sector * SECTOR:sector * SECTOR + len(data)] = data


def build(path: Path, tree: dict, label: str = "TEST_DISC", udf: str | None = "1.02",
          iso9660: bool = True, sectors: int = 400) -> Path:
    img = bytearray(sectors * SECTOR)
    if iso9660:
        _iso9660(img, tree, label)
    if udf:
        _Udf(udf).write(img, tree, label)
    path.write_bytes(bytes(img))
    return path


DVD_AUDIO = {"AUDIO_TS": {"AUDIO_TS.IFO": None, "ATS_01_0.IFO": None, "ATS_02_0.IFO": None},
             "VIDEO_TS": {"VIDEO_TS.IFO": None, "VTS_01_0.IFO": None}}
DVD_VIDEO = {"AUDIO_TS": {}, "VIDEO_TS": {"VIDEO_TS.IFO": None, "VTS_01_0.IFO": None,
                                          "VTS_02_0.IFO": None, "VTS_03_0.IFO": None}}
BLURAY = {"BDMV": {"index.bdmv": None, "MovieObject.bdmv": None,
                   "PLAYLIST": {"00000.mpls": None, "00001.mpls": None}, "STREAM": {}},
          "CERTIFICATE": {}}
