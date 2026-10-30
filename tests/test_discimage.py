"""Identifying DVD-Audio, DVD-Video and Blu-ray images (catalogue only), on synthetic images from
tests/discgen.py, including malformed ones: an image is hostile input, so identify() must
answer "unknown" for anything it can't read and never raise."""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import discgen

from beetsplug._sacd_discimage import SECTOR, identify

LAYOUTS = [("1.02", True), ("1.02", False), ("2.50", False), ("long", False), (None, True)]


@pytest.mark.parametrize(("udf", "iso9660"), LAYOUTS)
class TestKinds:
    def test_dvd_audio(self, tmp_path, udf, iso9660):
        d = identify(discgen.build(tmp_path / "a.iso", discgen.DVD_AUDIO, "SURROUND_MIX", udf, iso9660))
        assert (d.kind, d.titles, d.video, d.label) == ("dvd-audio", 2, True, "SURROUND_MIX")
        assert d.name == "DVD-Audio + DVD-Video"

    def test_dvd_video_with_an_empty_audio_ts(self, tmp_path, udf, iso9660):
        d = identify(discgen.build(tmp_path / "v.iso", discgen.DVD_VIDEO, "CONCERT", udf, iso9660))
        assert (d.kind, d.titles, d.video) == ("dvd-video", 3, False)

    def test_bluray(self, tmp_path, udf, iso9660):
        d = identify(discgen.build(tmp_path / "b.iso", discgen.BLURAY, "BD_LIVE", udf, iso9660))
        assert (d.kind, d.titles, d.name) == ("bluray", 2, "Blu-ray")


def test_dvd_audio_without_video(tmp_path):
    tree = {"AUDIO_TS": {"AUDIO_TS.IFO": None, "ATS_01_0.IFO": None}}
    d = identify(discgen.build(tmp_path / "a.iso", tree))
    assert (d.kind, d.video, d.name) == ("dvd-audio", False, "DVD-Audio")


def test_other_file_systems_are_unknown(tmp_path):
    assert identify(discgen.build(tmp_path / "data.iso", {"DATA": {"README.TXT": None}})).kind == "unknown"
    blank = tmp_path / "blank.iso"
    blank.write_bytes(bytes(SECTOR * 600))
    assert identify(blank).kind == "unknown"
    tiny = tmp_path / "tiny.iso"
    tiny.write_bytes(b"x")
    assert identify(tiny).kind == "unknown"


def test_ignores_the_listing_of_a_file_named_like_a_folder(tmp_path):
    # BDMV is a file here, not a folder: nothing is listed through it
    d = identify(discgen.build(tmp_path / "f.iso", {"BDMV": None, "VIDEO_TS": {"VIDEO_TS.IFO": None}}))
    assert d.kind == "dvd-video"


def test_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        identify(tmp_path / "missing.iso")


@pytest.mark.parametrize("udf", ["1.02", "2.50"])
def test_mutated_images_never_raise(tmp_path, udf):
    """Flip bytes in the structures of a valid image: every result is a known kind or unknown."""
    good = discgen.build(tmp_path / "good.iso", discgen.BLURAY | discgen.DVD_AUDIO, udf=udf, iso9660=True)
    data = good.read_bytes()
    used = [i for i in range(16 * SECTOR, len(data)) if data[i]]
    rng = random.Random(5)
    bad = tmp_path / "bad.iso"
    for _ in range(400):
        img = bytearray(data)
        for i in rng.sample(used, rng.randint(1, 8)):
            img[i] = rng.choice((0, 0xFF, rng.randrange(256)))
        bad.write_bytes(bytes(img))
        assert identify(bad).kind in ("bluray", "dvd-audio", "dvd-video", "unknown")


def test_out_of_range_lengths_are_bounded(tmp_path):
    """A directory claiming 4 GiB, and a truncated image, read nothing outside the image."""
    p = discgen.build(tmp_path / "x.iso", discgen.DVD_VIDEO, udf=None, iso9660=True)
    img = bytearray(p.read_bytes())
    at = 16 * SECTOR + 156 + 10                                     # root directory size, in the PVD
    img[at:at + 4] = (0xFFFFFFFF).to_bytes(4, "little")
    p.write_bytes(bytes(img))
    assert identify(p).kind == "unknown"
    q = discgen.build(tmp_path / "y.iso", discgen.BLURAY, udf="2.50", iso9660=False)
    q.write_bytes(q.read_bytes()[:(discgen.PART + 2) * SECTOR])     # cut inside the metadata partition
    assert identify(q).kind == "unknown"


REGRESSIONS = Path(__file__).resolve().parent.parent / "fuzz" / "regressions"


@pytest.mark.parametrize("image", sorted(p.name for p in REGRESSIONS.glob("*") if p.name != ".gitkeep"))
def test_fuzz_regressions(image):
    """Inputs that once crashed the Atheris harness (fuzz/fuzz_discimage.py) now give a result."""
    assert identify(REGRESSIONS / image).kind in ("bluray", "dvd-audio", "dvd-video", "unknown")


def test_reads_only(tmp_path):
    p = discgen.build(tmp_path / "r.iso", discgen.DVD_AUDIO)
    before, mtime = p.read_bytes(), p.stat().st_mtime_ns
    identify(p)
    assert p.read_bytes() == before and p.stat().st_mtime_ns == mtime


def test_layout_constant_matches_the_generator():
    assert Path(discgen.__file__).exists() and discgen.SECTOR == SECTOR
