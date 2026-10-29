"""beets-pysacd: SACD ISOs imported through pysacd into a throwaway beets library.

No network: pysacd's and beets' MusicBrainz requests are answered from tests/mbfixture.py, a
hybrid release whose CD layer and SACD layers share their recordings. Disc images come from
pysacd's synthetic ISO builder (tests/sacdgen.py in the pysacd source tree; set PYSACD_TESTS
when it isn't at ../pysacd/tests).
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# beets 2.12's test helpers pin beetsplug.__path__ to beets' own plugin directory on import, which
# hides this plugin when it runs from a source checkout. Note where it is, and put it back.
_PLUGIN_DIR = os.path.dirname(importlib.util.find_spec("beetsplug.sacd").origin)  # type: ignore[union-attr,arg-type]
from beets.test.helper import PluginTestHelper  # noqa: E402

import beetsplug  # noqa: E402

if _PLUGIN_DIR not in list(beetsplug.__path__):
    beetsplug.__path__ = [*beetsplug.__path__, _PLUGIN_DIR]

sys.path.insert(0, os.path.dirname(__file__))
import mbfixture  # noqa: E402

PYSACD_TESTS = Path(os.environ.get("PYSACD_TESTS", Path(__file__).resolve().parents[2] / "pysacd" / "tests"))
sys.path.insert(0, str(PYSACD_TESTS))
sacdgen = pytest.importorskip("sacdgen", reason=f"pysacd's tests/sacdgen.py not found in {PYSACD_TESTS}")

FRAMES = 75                     # per track: 1 s, as in the fixture
STEREO = "Hybrid SACD (SACD layer, 2 channels)"
MULTI = "Hybrid SACD (SACD layer, multichannel)"


def build_iso(path: Path, title: str = mbfixture.ALBUM, catalog: str = "PYSACD-TEST") -> Path:
    frames2 = [bytes([0x69]) * (4704 * 2)] * (FRAMES * 3)
    frames6 = [bytes([0x69]) * (4704 * 6)] * (FRAMES * 3)
    sacdgen.build_iso(path, [sacdgen.AreaSpec(2, frames2, [FRAMES] * 3, dst=False, titles=mbfixture.TITLES),
                             sacdgen.AreaSpec(6, frames6, [FRAMES] * 3, dst=False, titles=mbfixture.TITLES)],
                      info=sacdgen.DiscInfo(title=title, artist="Test Artist", album_catalog=catalog))
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Base(PluginTestHelper):
    preload_plugin = False

    @pytest.fixture(autouse=True)
    def offline(self):
        with patch("pysacd.musicbrainz._json", mbfixture.pysacd_json), \
                patch("beetsplug._utils.requests.RequestHandler.get_json", mbfixture.beets_get_json):
            yield

    def setup_beets(self) -> None:
        super().setup_beets()
        self.config["import"].set({"quiet": True, "write": True, "copy": True, "move": False})
        self.config["sacd"].set({"threads": 2})
        self.load_plugins("musicbrainz", "sacd")
        self.isodir = self.tmp_root / "isos"
        self.isodir.mkdir()
        self.iso = build_iso(self.isodir / "disc.iso")

    @property
    def tmp_root(self) -> Path:
        """The helper's temporary directory: `temp_dir_path` in beets 2.12, `temp_path` later."""
        root = getattr(self, "temp_path", None) or self.temp_dir_path
        return Path(root)

    def accept_weak_matches(self) -> None:
        """Let quiet mode apply the penalised match beets proposes on its own (missing tracks
        cap the recommendation at medium)."""
        self.config["match"]["strong_rec_thresh"] = 0.5
        self.config["match"]["max_rec"]["missing_tracks"] = "strong"

    def albums(self):
        return list(self.lib.albums())

    def staging_left(self) -> list[Path]:
        return [p for p in self.lib_path.rglob(".sacd-staging-*")]


class TestImport(Base):
    def test_stereo_area_is_pinned_to_its_medium(self):
        self.run_command("sacd-import", str(self.iso))
        [album] = self.albums()
        assert album.mb_albumid == mbfixture.RID
        assert album.media == STEREO                      # not "Media"
        assert album.sacd_area == "stereo"
        assert len(album.sacd_iso_sha) == 64
        items = sorted(album.items(), key=lambda i: i.track)
        assert [i.disc for i in items] == [2, 2, 2]       # the SACD stereo layer, not the CD layer
        assert [i.media for i in items] == [STEREO] * 3
        assert [i.mb_releasetrackid for i in items] == [t["id"] for t in mbfixture.release()["media"][1]["tracks"]]
        for i in items:
            assert Path(os.fsdecode(i.path)).is_relative_to(self.lib_path)
            assert Path(os.fsdecode(i.path)).exists()
        assert self.staging_left() == []
        assert self.iso.exists()                          # kept by default

    def test_both_areas_of_one_release_in_one_run(self):
        self.config["sacd"]["areas"] = "both"
        self.run_command("sacd-import", str(self.iso))
        albums = {a.sacd_area: a for a in self.albums()}
        assert set(albums) == {"stereo", "multichannel"}
        assert albums["stereo"].media == STEREO
        assert albums["multichannel"].media == MULTI
        assert {i.disc for i in albums["stereo"].items()} == {2}
        assert {i.disc for i in albums["multichannel"].items()} == {3}
        assert {i.channels for i in albums["multichannel"].items()} == {6}

    def test_already_imported_is_skipped(self):
        self.run_command("sacd-import", str(self.iso))
        self.run_command("sacd-import", str(self.iso))
        assert len(self.albums()) == 1

    def test_flac(self):
        from pysacd import _native
        if not _native.has_flac():
            pytest.skip("pysacd engine built without libFLAC")
        self.run_command("sacd-import", "-f", "flac", str(self.iso))
        [album] = self.albums()
        assert {i.format for i in album.items()} == {"FLAC"}
        assert album.media == STEREO

    def test_in_place_session_still_moves_staged_files(self):
        # copy: no and move: no import other files in place; staged files must still move
        self.config["import"].set({"copy": False, "move": False})
        self.run_command("sacd-import", str(self.iso))
        [album] = self.albums()
        for i in album.items():
            assert Path(os.fsdecode(i.path)).is_relative_to(self.lib_path)
            assert ".sacd-staging-" not in os.fsdecode(i.path)
            assert Path(os.fsdecode(i.path)).exists()
        assert self.staging_left() == []

    def test_without_pysacd_match_the_medium_comes_from_the_candidate(self):
        # no MusicBrainz ids in the files: beets searches, and the SACD-layer medium with the
        # area's track count and channel type is chosen
        self.config["sacd"]["musicbrainz"] = False
        self.run_command("sacd-import", str(self.iso))
        [album] = self.albums()
        assert album.media == STEREO
        assert {i.disc for i in album.items()} == {2}


class TestOtherEditions(Base):
    """pysacd's match can be another format's edition (a catalogue number shared with the vinyl,
    say): it is not used to pin or tag an SACD area (#7)."""

    def test_vinyl_match_is_not_used(self, monkeypatch, caplog):
        monkeypatch.setattr(mbfixture, "MEDIA", [(1, '12" Vinyl')])
        with caplog.at_level(logging.INFO, logger="beets"):
            self.run_command("sacd-import", str(self.iso))
        assert f'MusicBrainz match {mbfixture.RID} is a 12" Vinyl medium, not SACD; not used' in caplog.text
        assert "area is medium" not in caplog.text

    def test_release_listing_only_the_cd_layer_is_kept_unpinned(self, monkeypatch, caplog):
        monkeypatch.setattr(mbfixture, "MEDIA", [(1, "Hybrid SACD (CD layer)")])
        self.accept_weak_matches()
        with caplog.at_level(logging.INFO, logger="beets"):
            self.run_command("sacd-import", str(self.iso))
        assert "has no SACD medium matching it (Hybrid SACD (CD layer)); medium not pinned" in caplog.text
        [album] = self.albums()
        assert album.mb_albumid == mbfixture.RID
        assert album.sacd_area == "stereo"


class TestVetMatch:
    @staticmethod
    def match(fmt, *others):
        media = [{"format": f} for f in (fmt, *others)]
        return SimpleNamespace(medium=media[0], release={"media": media})

    def test_sacd_layers_are_used(self):
        from beetsplug.sacd import vet_match
        assert vet_match(self.match(STEREO, "Hybrid SACD (CD layer)")) == (True, True)
        assert vet_match(self.match("SACD")) == (True, True)

    def test_other_formats_are_not(self):
        from beetsplug.sacd import vet_match
        for fmt in ('12" Vinyl', "CD", "Digital Media", ""):
            assert vet_match(self.match(fmt, STEREO)) == (False, False)

    def test_cd_layer(self):
        from beetsplug.sacd import vet_match
        assert vet_match(self.match("Hybrid SACD (CD layer)")) == (True, False)          # all MB lists
        assert vet_match(self.match("Hybrid SACD (CD layer)", STEREO)) == (False, False)  # SACD layer exists

    def test_malformed_media_list(self):
        from beetsplug.sacd import vet_match
        cd = {"format": "Hybrid SACD (CD layer)"}
        for media in (None, [None, "x", cd]):
            assert vet_match(SimpleNamespace(medium=cd, release={"media": media})) == (True, False)


class TestMediumBug(Base):
    def test_beets_maps_to_the_cd_layer_without_the_pin(self, monkeypatch):
        # Documents the beets 2.14 behaviour this plugin works around. If beets fixes it, this
        # test fails: then the pin is only a safety net.
        from beetsplug import sacd
        monkeypatch.setattr(sacd, "choose_medium", lambda info, pin: None)
        self.accept_weak_matches()
        self.run_command("sacd-import", str(self.iso))
        [album] = self.albums()
        assert album.media == "Media"
        assert {i.disc for i in album.items()} != {2}         # some other medium (CD layer or multichannel)

    def test_guard_remaps_when_the_candidate_was_not_restricted(self, monkeypatch, caplog):
        from beetsplug import sacd
        monkeypatch.setattr(sacd, "pin_candidate", lambda info, pin: None)     # only the guard is left
        self.accept_weak_matches()
        with caplog.at_level(logging.INFO, logger="beets"):
            self.run_command("sacd-import", str(self.iso))
        [album] = self.albums()
        assert album.media == STEREO
        assert {i.disc for i in album.items()} == {2}
        assert any("remapped 3 tracks to medium 2" in r.getMessage() for r in caplog.records)

    def test_guard_is_a_no_op_when_already_pinned(self, caplog):
        with caplog.at_level(logging.INFO, logger="beets"):
            self.run_command("sacd-import", str(self.iso))
        assert not any("remapped" in r.getMessage() for r in caplog.records)


class TestRemoveIso(Base):
    def test_removed_after_a_verified_import(self):
        self.run_command("sacd-import", "--remove-iso", str(self.iso))
        assert len(self.albums()) == 1
        assert not self.iso.exists()

    def test_kept_when_the_import_was_skipped(self):
        self.config["sacd"]["remove_iso"] = True
        self.config["match"]["strong_rec_thresh"] = 0.0      # nothing is strong: quiet mode skips
        self.run_command("sacd-import", str(self.iso))
        assert self.albums() == []
        assert self.iso.exists()

    def test_kept_when_an_area_is_missing(self):
        self.config["sacd"].set({"remove_iso": True, "areas": "both"})
        from beetsplug import sacd
        real = sacd.SacdPlugin.convert

        def stereo_only(plugin, lib, iso, fmt, release):
            job = real(plugin, lib, iso, fmt, release)
            job.pins = [p for p in job.pins if p.area == "stereo"]      # the other one "failed"
            job.pins.append(sacd.Pin(iso, job.pins[0].fingerprint, "multichannel", 3, Path("/nonexistent")))
            return job
        with patch.object(sacd.SacdPlugin, "convert", stereo_only):
            self.run_command("sacd-import", str(self.iso))
        assert self.iso.exists()


class TestAutoDetect(Base):
    def test_plain_import_converts_isos_in_a_directory(self):
        before = sha(self.iso)
        self.run_command("import", str(self.isodir))
        [album] = self.albums()
        assert album.media == STEREO
        assert album.sacd_area == "stereo"
        assert sha(self.iso) == before                 # read only
        assert sorted(p.name for p in self.isodir.iterdir()) == ["disc.iso"]
        assert self.staging_left() == []

    def test_plain_import_of_the_iso_itself(self):
        self.run_command("import", str(self.iso))
        assert len(self.albums()) == 1

    def test_auto_off(self):
        self.config["sacd"]["auto"] = False
        self.run_command("import", str(self.isodir))
        assert self.albums() == []

    def test_a_dvd_iso_is_left_alone(self):
        dvd = self.isodir / "dvd.iso"
        dvd.write_bytes(bytes(2048 * 600))
        self.run_command("import", str(self.isodir))
        assert len(self.albums()) == 1
        assert dvd.exists()


class TestInfo(Base):
    def test_prints_the_toc_read_only(self, capsys):
        hostile = build_iso(self.isodir / "hostile.iso", title="evil\x1b]0;pwned\x07\x9b31mtitle")
        before = sha(hostile)
        self.run_command("sacd-info", str(hostile))
        out = capsys.readouterr().out
        assert "Area TWOCHTOC" in out and "Area MULCHTOC" in out
        assert "One" in out
        assert "\x1b" not in out and "\x9b" not in out
        assert "\\x9b" in out              # C1 CSI shown as an escape (the reader already turns ESC into a space)
        assert sha(hostile) == before


class TestChooseMedium:
    """The medium choice on its own, with AlbumInfo-like stand-ins."""

    @staticmethod
    def info(album_id, *media):
        from types import SimpleNamespace
        tracks = [SimpleNamespace(medium=pos, media=fmt, medium_index=i + 1, index=i + 1)
                  for pos, (fmt, n) in enumerate(media, 1) for i in range(n)]
        return SimpleNamespace(album_id=album_id, tracks=tracks, media="Media")

    @staticmethod
    def pin(area="stereo", tracks=3, release=None, medium=None):
        from beetsplug.sacd import Pin
        return Pin(Path("x.iso"), "f", area, tracks, Path("s"), release, medium)

    def test_sacd_layer_is_not_the_cd_layer(self):
        from beetsplug.sacd import is_sacd_layer
        assert is_sacd_layer("SACD")
        assert is_sacd_layer("Hybrid SACD (SACD layer, 2 channels)")
        assert is_sacd_layer("Hybrid SACD (SACD layer)")
        assert not is_sacd_layer("Hybrid SACD (CD layer)")      # "SACD layer" contains "CD layer"
        assert not is_sacd_layer("CD")

    def test_pysacd_match_decides_for_its_release(self):
        from beetsplug.sacd import choose_medium
        info = self.info("r", ("Hybrid SACD (CD layer)", 3), (STEREO, 3), (MULTI, 3))
        assert choose_medium(info, self.pin(release="r", medium=3)) == 3
        assert choose_medium(info, self.pin(release="other", medium=3)) == 2     # another release: derived

    def test_derived_from_track_count_and_channels(self):
        from beetsplug.sacd import choose_medium
        info = self.info("r", ("Hybrid SACD (CD layer)", 3), (STEREO, 3), (MULTI, 3))
        assert choose_medium(info, self.pin("stereo")) == 2
        assert choose_medium(info, self.pin("multichannel")) == 3
        assert choose_medium(info, self.pin("stereo", tracks=4)) is None

    def test_ambiguous_or_single_medium_left_alone(self):
        from beetsplug.sacd import choose_medium
        assert choose_medium(self.info("r", (STEREO, 3)), self.pin()) is None
        two_discs = self.info("r", ("SACD", 3), ("SACD", 3))         # a two-disc set: can't tell
        assert choose_medium(two_discs, self.pin()) is None

    def test_restrict(self):
        from beetsplug.sacd import restrict
        info = self.info("r", ("Hybrid SACD (CD layer)", 3), (STEREO, 3))
        restrict(info, 2)
        assert {t.medium for t in info.tracks} == {2}
        assert info.media == STEREO
