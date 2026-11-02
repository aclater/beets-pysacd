"""beet sacd-tags-export: sacdfs tag-layer files written from the library (temporary libraries,
synthetic discs). One test mounts a container build of sacdfs main (SACDFS_IMAGE) and reads the
tags it serves."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import tomllib

import pytest
from test_sacd import Base, build_iso, sha

from beetsplug import _sacd_tags

# `sacdfs tags key` of build_iso() from sacdfs main (the container test checks it again)
GOLDEN_KEY = "530c027caa43f3733c635a9631f44326"
ENV = dict(os.environ)             # beets' test helper later points HOME elsewhere; podman needs the real one
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 64


class TagsBase(Base):
    def setup_beets(self) -> None:
        super().setup_beets()
        self.tags = self.tmp_root / "tags"
        self.tags.mkdir()

    def migrated(self):
        self.run_command("sacd-import", str(self.iso))
        [album] = self.albums()
        album["genre"] = "Jazz"
        album.store()
        self.run_command("sacd-migrate", "--apply", str(self.iso))
        return self.lib.albums()[0]

    def key(self, iso=None) -> str:
        from pysacd.toc import SACDImage
        with SACDImage(str(iso or self.iso)) as img:
            return _sacd_tags.disc_key(img, img.read_toc())

    def file(self) -> dict:
        return tomllib.loads((self.tags / f"{self.key()}.toml").read_text())


class TestKey(TagsBase):
    def test_key_is_sacdfs_s_for_the_synthetic_disc(self):
        assert self.key() == GOLDEN_KEY

    def test_key_follows_the_toc_not_the_path(self):
        other = self.isodir / "elsewhere.iso"
        shutil.copy(self.iso, other)
        assert self.key(other) == self.key()
        assert self.key(build_iso(self.isodir / "d2.iso", catalog="OTHER-CAT")) != self.key()


class TestExport(TagsBase):
    def test_writes_genre_and_musicbrainz_ids_per_area(self, capsys):
        album = self.migrated()
        before = sha(self.iso)
        self.run_command("sacd-tags-export", "--tags", str(self.tags))
        assert "written" in capsys.readouterr().out
        f = self.file()
        a = f["stereo"]["album"]
        assert a["genre"] == "Jazz"
        assert a["TXXX:MusicBrainz Album Id"] == album.mb_albumid
        tracks = f["stereo"]["track"]
        assert sorted(tracks) == ["1", "2", "3"]
        by_no = {str(int(i.sacd_track)): i for i in album.items()}
        assert all(tracks[n]["TXXX:MusicBrainz Release Track Id"] == by_no[n].mb_releasetrackid for n in tracks)
        assert "multichannel" not in f
        assert sha(self.iso) == before

    def test_keeps_fields_beets_does_not_own_and_is_idempotent(self):
        self.migrated()
        path = self.tags / f"{self.key()}.toml"
        path.write_text('[album]\ncomposer = "Hand Edit"\n[track.2]\ntitle = "Fixed"\n'
                        '[stereo.album]\ngenre = "Old"\nTBPM = "120"\n')
        self.run_command("sacd-tags-export", "--tags", str(self.tags))
        f = self.file()
        assert f["album"] == {"composer": "Hand Edit"} and f["track"]["2"] == {"title": "Fixed"}
        assert f["stereo"]["album"]["TBPM"] == "120" and f["stereo"]["album"]["genre"] == "Jazz"
        assert "title" not in f["stereo"]["track"]["2"]
        os.utime(path, (1, 1))
        self.run_command("sacd-tags-export", "--tags", str(self.tags))
        assert path.stat().st_mtime == 1                      # unchanged: not rewritten
        assert [p.name for p in self.tags.iterdir()] == [path.name]

    def test_dry_run_and_bad_files(self, capsys):
        self.migrated()
        self.run_command("sacd-tags-export", "--tags", str(self.tags), "--dry-run")
        assert "would be written" in capsys.readouterr().out and not list(self.tags.iterdir())
        path = self.tags / f"{self.key()}.toml"
        path.write_text("not [valid")
        self.run_command("sacd-tags-export", "--tags", str(self.tags))
        assert "left alone" in capsys.readouterr().out and path.read_text() == "not [valid"

    def test_cover_art_is_copied_next_to_the_file(self):
        album = self.migrated()
        art = self.tmp_root / "cover.jpg"
        art.write_bytes(JPEG)
        album["artpath"] = str(art)
        album.store()
        self.run_command("sacd-tags-export", "--tags", str(self.tags))
        name = self.file()["stereo"]["album"]["art"]
        assert name == f"{self.key()}-stereo.jpg" and (self.tags / name).read_bytes() == JPEG

    def test_query_and_albums_without_an_image(self, capsys):
        self.migrated()
        self.run_command("sacd-tags-export", "--tags", str(self.tags), "genre:Nothing")
        assert "no albums with an SACD image" in capsys.readouterr().out and not list(self.tags.iterdir())

    def test_needs_a_tags_directory(self):
        from beets.ui import UserError
        with pytest.raises(UserError):
            self.run_command("sacd-tags-export")
        with pytest.raises(UserError):
            self.run_command("sacd-tags-export", "--tags", str(self.tags / "missing"))


class TestToml:
    def test_round_trip_with_awkward_text(self):
        data = {"stereo": {"album": {"genre": 'Jazz "Cool"\\ é\n', "TXXX:MusicBrainz Album Id": "x"}}}
        assert tomllib.loads(_sacd_tags.dumps(data)) == data


@pytest.mark.skipif(not os.environ.get("SACDFS_IMAGE"), reason="SACDFS_IMAGE not set")
class TestServedByRealSacdfs(TagsBase):
    def test_mounted_sacdfs_serves_the_exported_tags(self):
        from mutagen.dsf import DSF
        album = self.migrated()
        self.run_command("sacd-tags-export", "--tags", str(self.tags))
        image = os.environ["SACDFS_IMAGE"]
        run = ["podman", "run", "--rm", "--security-opt", "label=disable", "--entrypoint", "/usr/local/bin/sacdfs"]
        proc = subprocess.run([*run, "-v", f"{self.isodir}:/images:ro", image, "tags", "key", "/images/disc.iso"],
                              capture_output=True, text=True, env=ENV)
        assert proc.returncode == 0, proc.stderr
        keyed = proc.stdout.split()[0]
        assert keyed == self.key()                              # the key is the one sacdfs computes
        name = f"sacdtest-{os.getpid()}"
        subprocess.run(["podman", "run", "-d", "--name", name, "--device", "/dev/fuse", "--cap-add", "SYS_ADMIN",
                        "--security-opt", "label=disable", "--entrypoint", "/usr/local/bin/sacdfs",
                        "-v", f"{self.isodir}:/images:ro", "-v", f"{self.tags}:/tags:ro", image,
                        "-f", "--tags", "/tags", "/images", "/mnt"], check=True, capture_output=True, env=ENV)
        try:
            served = None
            for _ in range(60):
                ls = subprocess.run(["podman", "exec", name, "sh", "-c", "cd /mnt && ls disc/Stereo/*.dsf"],
                                    capture_output=True, text=True, env=ENV)
                if ls.returncode == 0 and ls.stdout.strip():
                    served = ls.stdout.splitlines()[0]
                    break
                time.sleep(1)
            assert served, subprocess.run(["podman", "logs", name], capture_output=True, text=True, env=ENV).stdout
            out = self.tmp_root / "served.dsf"
            with out.open("wb") as fh:
                subprocess.run(["podman", "exec", name, "cat", f"/mnt/{served}"], check=True, stdout=fh, env=ENV)
            tags = DSF(str(out)).tags
            assert [str(g) for g in tags["TCON"].text] == ["Jazz"]
            assert tags["TXXX:MusicBrainz Album Id"].text == [album.mb_albumid]
            assert tags["TXXX:MusicBrainz Release Track Id"].text
        finally:
            subprocess.run(["podman", "rm", "-f", name], capture_output=True, env=ENV)
