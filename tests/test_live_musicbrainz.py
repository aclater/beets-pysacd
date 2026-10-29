"""The plugin's matching against the live MusicBrainz, to notice when the real data stops fitting.

The rest of the suite mocks MusicBrainz (tests/mbfixture.py). This test is skipped unless
PYSACD_LIVE_MB=1; the weekly `live-musicbrainz` workflow sets it. It makes two requests, one
through each MusicBrainz client the plugin relies on, both throttled to MusicBrainz's one request
per second and naming this repository as the User-Agent contact:

1. pysacd's find_release for a stereo area, which the plugin's vet_match must accept, medium
   included;
2. beets' MusicBrainz plugin's lookup of the same release, which the plugin's choose_medium and
   pin_candidate must cut down to the area's SACD layer.

The release is the 2003 EMI hybrid SACD of Pink Floyd's "The Dark Side of the Moon": three media
(CD layer, SACD stereo, SACD multichannel) of ten tracks each sharing recordings, the case the
medium pin exists for.
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

if os.environ.get("PYSACD_LIVE_MB") != "1":
    pytest.skip("live MusicBrainz test: set PYSACD_LIVE_MB=1", allow_module_level=True)

# As in test_sacd.py: beets 2.12's test helpers hide a source checkout's beetsplug
_PLUGIN_DIR = os.path.dirname(importlib.util.find_spec("beetsplug.sacd").origin)  # type: ignore[union-attr,arg-type]
from beets.test.helper import PluginTestHelper  # noqa: E402

import beetsplug  # noqa: E402

if _PLUGIN_DIR not in list(beetsplug.__path__):
    beetsplug.__path__ = [*beetsplug.__path__, _PLUGIN_DIR]

RELEASE_ID = "1a2a37a4-2ee5-3aa8-b1bf-4976dbb8007c"
CONTACT = "https://github.com/aclater/beets-pysacd"
CD = "Hybrid SACD (CD layer)"
STEREO = "Hybrid SACD (SACD layer, 2 channels)"
MULTI = "Hybrid SACD (SACD layer, multichannel)"
# The SACD stereo layer's track lengths in seconds, as MusicBrainz listed them in 2026
STEREO_SECONDS = [70, 169, 210, 429, 285, 382, 469, 205, 228, 132]


def pin(area: str, **kw):
    from beetsplug.sacd import Pin
    return Pin(Path("disc.iso"), "0" * 64, area, 10, Path("staging"), **kw)


class TestLiveMusicBrainz(PluginTestHelper):
    preload_plugin = False

    def setup_beets(self) -> None:
        super().setup_beets()
        self.load_plugins("musicbrainz", "sacd")

    def test_matching_against_the_real_release(self):
        from beets import plugins
        from pysacd import musicbrainz

        from beetsplug.sacd import choose_medium, pin_candidate, vet_match

        # 1. pysacd's match, as the plugin's convert step gets it (one request)
        tracks = [SimpleNamespace(duration=SimpleNamespace(seconds_float=float(s)), isrc=None)
                  for s in STEREO_SECONDS]
        disc = SimpleNamespace(album_set_size=1, album_sequence_number=1)
        area = SimpleNamespace(tracks=tracks, is_multichannel=False)
        match = musicbrainz.find_release(disc, area, CONTACT, release_id=RELEASE_ID)  # type: ignore[arg-type]
        assert match is not None
        assert match.release_id == RELEASE_ID
        assert [m.get("format") for m in match.release["media"]] == [CD, STEREO, MULTI]
        assert match.medium.get("format") == STEREO
        assert vet_match(match) == (True, True)

        time.sleep(1.1)     # MusicBrainz: one request per second, whichever client sends it

        # 2. beets' lookup of the same release (one request), as the importer gets candidates
        [mb] = [p for p in plugins.find_plugins() if p.name == "musicbrainz"]
        mb.mb_api.session.headers["User-Agent"] = f"beets-pysacd-live-test ( {CONTACT} )"
        info = mb.album_for_id(RELEASE_ID)
        assert info is not None
        assert info.album_id == RELEASE_ID
        assert info.album == "The Dark Side of the Moon"
        assert len(info.tracks) == 30
        assert sorted({(t.medium, t.media) for t in info.tracks}) == [(1, CD), (2, STEREO), (3, MULTI)]

        # Without pysacd's match: chosen by track count and channels
        assert choose_medium(info, pin("stereo")) == 2
        assert choose_medium(info, pin("multichannel")) == 3
        # With it: the medium pysacd matched
        stereo = pin("stereo", release_id=RELEASE_ID, medium=match.medium.get("position"), media=STEREO)
        assert choose_medium(info, stereo) == 2
        pin_candidate(info, stereo)
        assert info.media == STEREO
        assert len(info.tracks) == 10
        assert {t.medium for t in info.tracks} == {2}
        assert all(t.track_id for t in info.tracks)
