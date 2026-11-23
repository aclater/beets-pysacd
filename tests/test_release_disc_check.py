"""scripts/release_disc_check.py: the comparison of two installs' imports of a disc (#89)."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release_disc_check as rdc  # noqa: E402


def item(n: int, channels: int = 2) -> dict:
    return {"title": f"Song {n}", "track": n, "disc": 2, "media": "Hybrid SACD (SACD layer, 2 channels)",
            "mb_trackid": f"t{n}", "channels": channels, "length": 180.0 + n, "exists": True, "size": 1000 + n,
            "ext": "dsf", "sha256": f"{n:064x}", "path": f"Artist/Album/{n:02d} Song {n}.dsf"}


def record(*areas: str) -> dict:
    albums = []
    for area in areas:
        ch = 2 if area == "stereo" else 6
        albums.append({"album": "Album", "albumartist": "Artist", "mb_albumid": "r1", "sacd_area": area,
                       "items": [item(n, ch) for n in (1, 2)]})
    return {"mode": "asis", "steps": [{"rc": 0, "log": {"duplicate": 0}}], "albums": albums,
            "singletons": 0, "stray_files": 0, "staging_left": 0}


class Compare(unittest.TestCase):
    def test_identical_runs_have_no_differences(self):
        self.assertEqual(rdc.compare_runs(record("stereo", "multichannel"), record("stereo", "multichannel")), [])

    def test_a_skipped_area_is_reported(self):
        rows = rdc.compare_runs(record("stereo"), record("stereo", "multichannel"))
        self.assertIn(("run", "albums", "1", "2"), rows)
        self.assertIn(("album:multichannel", "present", "False", "True"), rows)

    def test_release_and_medium_are_compared(self):
        b = record("stereo")
        b["albums"][0]["mb_albumid"] = "r2"
        b["albums"][0]["items"][1]["media"] = "CD"
        rows = rdc.compare_runs(record("stereo"), b)
        self.assertIn(("album:stereo", "mb_albumid", "r1", "r2"), rows)
        self.assertIn(("track:stereo:02", "media", "Hybrid SACD (SACD layer, 2 channels)", "CD"), rows)

    def test_titles_and_paths_never_appear(self):
        b = record("stereo")
        b["albums"][0]["album"] = "Other Album"
        b["albums"][0]["items"][0]["title"] = "Other Song"
        b["albums"][0]["items"][0]["path"] = "Artist/Other Album/01 Other Song.dsf"
        rows = rdc.compare_runs(record("stereo"), b)
        self.assertEqual({(s, f) for s, f, _, _ in rows},
                         {("album:stereo", "album"), ("track:stereo:01", "title"), ("track:stereo:01", "path_hash")})
        text = json.dumps(rows)
        for word in ("Album", "Song", "Artist", ".dsf"):
            self.assertNotIn(word, text)

    def test_tiny_length_differences_are_ignored(self):
        b = record("stereo")
        b["albums"][0]["items"][0]["length"] += 0.0004
        self.assertEqual(rdc.compare_runs(record("stereo"), b), [])

    def test_an_area_is_known_by_channels_without_sacd_area(self):
        b = record("multichannel")
        del b["albums"][0]["sacd_area"]
        self.assertEqual(list(rdc.keyed_albums(b)), ["multichannel"])

    def test_two_albums_of_one_area_are_both_kept(self):
        self.assertEqual(list(rdc.keyed_albums(record("stereo", "stereo"))), ["stereo", "stereo#2"])

    def test_compare_writes_tsv_and_summary_and_flags_failures(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "runs").mkdir()
            (out / "installs.json").write_text(json.dumps(["prev", "new"]))
            a, b = record("stereo"), record("stereo", "multichannel")
            failed = copy.deepcopy(a)
            failed["steps"][0]["rc"] = 1
            for disc, mode, name, rec in (("d1", "asis", "prev", a), ("d1", "asis", "new", b),
                                          ("d2", "asis", "prev", failed), ("d2", "asis", "new", a)):
                (out / "runs" / f"{disc}-{mode}-{name}.json").write_text(
                    json.dumps({**rec, "disc": disc, "mode": mode, "install": name}))
            self.assertEqual(rdc.compare(out), 1)
            tsv = (out / "diff.tsv").read_text().splitlines()
            self.assertEqual(tsv[0], "disc\tmode\tscope\tfield\tprev\tnew")
            self.assertIn("d1\tasis\trun\talbums\t1\t2", tsv)
            summary = (out / "summary.txt").read_text()
            self.assertIn("FAILED", summary)
            self.assertIn("2 disc/mode pairs, 2 with differences, 1 with a failed import", summary)


if __name__ == "__main__":
    unittest.main()
