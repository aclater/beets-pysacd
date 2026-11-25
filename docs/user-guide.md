[beets-pysacd](../README.md) › [Documentation](README.md) › User guide

# User guide

How to import SACD images into beets, move a library from extracts to images served by
[sacdfs](https://github.com/dsd-toolbox/sacdfs), keep your tags, and what happens to DVD and Blu-ray
images. Every option and setting is in [options and configuration](options.md).

The commands use example folders: `~/isos` holds your SACD images (ISO), `~/dsf` the files
extracted from them, `~/sacd` is where sacdfs is mounted and `~/sacd-tags` is sacdfs' tags
directory. Use your own folders in their place.

## Importing SACD images

<!-- docs-run: setup="dnf -y -q --setopt=install_weak_deps=False install python3-pip git-core flac-libs && pip install -q beets-pysacd && mkdir -p isos sacd-tags .config/beets && git init -q /tmp/pysacd && git -C /tmp/pysacd fetch -q --depth 1 https://github.com/dsd-toolbox/pysacd a2a6c03a525e73a3566d1aa86bedc57a922cb961 && git -C /tmp/pysacd checkout -q FETCH_HEAD && python3 -c \"import sys; sys.path.insert(0, '/tmp/pysacd/tests'); import sacdgen as g; a = lambda c: g.AreaSpec(c, [bytes([105]) * 4704 * c] * 225, [75] * 3, dst=False, titles=['One', 'Two', 'Three']); g.build_iso('isos/Album.iso', [a(2), a(6)], info=g.DiscInfo(title='Docs run album', artist='Docs run artist'))\" && cp isos/Album.iso Album.iso && printf 'directory: ~/Music\\nplugins: musicbrainz sacd\\nimport:\\n  quiet: yes\\n  quiet_fallback: asis\\n' > .config/beets/config.yaml" -->
```sh
beet sacd-import Album.iso              # one image
beet sacd-import ~/isos/                # every .iso under a directory
beet sacd-import -a both -f flac Album.iso
beet sacd-import --release 1a2a37a4-2ee5-3aa8-b1bf-4976dbb8007c Album.iso   # use this MusicBrainz release
beet sacd-info Album.iso                # print the TOC; changes nothing
beet sacd-info ~/isos/                  # ...of every image under a directory
```

Plain `beet import` also converts the SACD images it finds (an `.iso` given on
the command line, or inside a directory being imported) before importing them.
Your other files in the same run are imported exactly as your settings say.
Turn this off with `auto: no`.

An area that is already in the library is skipped. Imported albums carry two
flexible attributes, `sacd_iso_sha` (a fingerprint of the disc's TOCs) and
`sacd_area` (`stereo` or `multichannel`), so `beet ls sacd_area:multichannel`
lists the multichannel albums.

## Moving a library from extracts to SACD images (sacdfs)

If you serve your ISOs with [sacdfs](https://github.com/dsd-toolbox/sacdfs) and delete the extracted
files, the beets items for those extracts would dangle. `beet sacd-migrate` finds the albums that
are extracts of an ISO and records where the ISO and sacdfs hold each track, keeping their
MusicBrainz IDs and your other beets data:

<!-- docs-run: expect="01 - One.dsf" -->
<!-- docs-lint: ignore placeholder -- $path and $sacdfs_path are beets format fields in single quotes, not shell variables -->
```sh
beet sacd-migrate ~/isos/                  # report which albums are extracts of which ISO area
beet sacd-migrate --apply --source ~/isos --flatten ~/isos/    # record it
beet ls -f '$path $sacdfs_path' sacd_area:stereo
```

An album is an extract of an ISO area when it carries that disc's `sacd_iso_sha` and
`sacd_area` (imported with this plugin), or when it lives under the ISO's folder and its
tracks agree with the area's in number and length (within 2 seconds). With `--apply` each item
gets the flexible attributes `sacd_iso` (the ISO), `sacd_track`, `sacd_area` and `sacdfs_path`
(`Folder/Stereo/NN - Title.dsf`, relative to the sacdfs mount; `--source` is sacdfs' SOURCE
and `--flatten` matches its option). It writes only to the beets database: nothing is moved
or deleted, and tags are not written to files. The check is of the TOC, not the audio; run
`sacdfs verify` before deleting any extract. Item paths are not changed. `sacdfs_path` follows
sacdfs 0.4.1's naming, including `NN - Track NN.dsf` for a track with no title (sacdfs 0.4.0 showed
`NN.dsf`; with `--catalogue --mount`, a mount that shows only that name gets it). It is derived from the
TOC's titles, so an image served with a tags file that changes titles is untested. Checked against a mounted 0.4.0 and
0.4.1-rc.2 on three real discs (two with text, one with none): every recorded path exists.

**Only verified extracts.** `sacdfs verify` writes a tab-separated report (`-o report.tsv`) with a
row for each extract. Give it to the migration and `--apply` records an album only when every
one of its items is `IDENTICAL` or `IDENTICAL-PAUSE` in it (matched by file path); any other
status, or a missing row, holds the whole album back and says so:

<!-- docs-run: skip="needs sacdfs and the extracted files it compares with the images" -->
```sh
sacdfs verify -o report.tsv --map ~/dsf ~/isos ~/isos ~/dsf
beet sacd-migrate --apply --verify report.tsv --source ~/isos ~/isos/
```

**ISOs with no extracts.** `--catalogue --mount DIR --apply` adds an album for each ISO area
that has no extracts in the library (no album imported from it, none under its folder with
the area's track count). Its items carry the disc's text, track order, length, channel count
and `sacdfs_path`, and their `path` is that file under `DIR`, where sacdfs is mounted; the
albums have `sacd_catalogued: 1`. They have no MusicBrainz match: run beets' own tools on
the mounted files for that. Without `--apply` the command only reports; a second run
adds nothing. With sacdfs mounted at `~/sacd` from the images in `~/isos`:

<!-- docs-run: skip="needs a sacdfs mount (FUSE) at ~/sacd" -->
```sh
beet sacd-migrate --catalogue --mount ~/sacd --source ~/isos ~/isos/            # report
beet sacd-migrate --catalogue --mount ~/sacd --source ~/isos --apply ~/isos/    # add the albums
```

**Fields set by hand on catalogued items.** The mount is read-only, so `beet modify` can't
write a tag to a catalogued item's file; the edit lives in the library. Each item records its
file's mtime when it is catalogued, and again when a tag field is set on it, so `beet update`
leaves its tag fields (genre, year, title, ...) alone until the file's mtime changes on the
mount. That mtime comes from the ISO, so it stays the same when sacdfs is remounted; it moves
when the ISO changes, when an sacdfs upgrade changes the files' bytes, or when the disc's tags
file (`sacd-tags-export`) changes. `beet update` then reads the file's tags over the item's
tag fields, as it does for any changed file; flexible fields stay. To keep a genre across
that, export it with `sacd-tags-export`. Items catalogued by 0.2.1 or earlier have no recorded
mtime, so every `beet update` reads their tags from the mount: `sacd-migrate --mount DIR`
reports them and with `--apply` records each existing file's mtime, changing no other field.
Tested in a throwaway library with DSF files from pysacd standing in for the mount (beets
2.12.0 and 2.14.1); that sacdfs main keeps a track's mtime across remounts and moves it for a
new tags file is checked in CI on a real mount; the rest is not yet run on a real mount.

**Upgrading the mount from sacdfs 0.4.0 to 0.4.1.** sacdfs 0.4.0 showed a track without a
title as `NN.dsf`; 0.4.1 shows it as `NN - Track NN.dsf`. Albums catalogued on a 0.4.0 mount
by beets-pysacd 0.2.0 or 0.2.1 point at the old names, and once the mount is upgraded
`beet update` removes their items, with any fields you set on them. In this order:

1. Back up the beets library database (`library.db`).
2. Upgrade and remount sacdfs. Don't run `beet update` yet.
3. Run `sacd-migrate` with `--mount` (and `--flatten` if the mount uses it). With sacdfs mounted
   at `~/sacd` from the images in `~/isos`, this reports which catalogued items would move to the
   new names:

   <!-- docs-run: skip="needs a sacdfs mount (FUSE) at ~/sacd" -->
   ```sh
   beet sacd-migrate --mount ~/sacd --source ~/isos ~/isos/
   ```

   Add `--apply` to move them. A `--catalogue --mount ~/sacd --apply` run does the same.
4. Then `beet update` keeps them.

An item is moved only when its path is the 0.4.0 name under `--mount`, that file is gone, and
the 0.4.1 name is the one file the mount shows for that track number; anything else is reported
and left alone. Only the item's `path`, `sacdfs_path` and `mtime` (the new file's) change: its id, added date and other
fields stay, nothing on the mount is touched and no item is removed. A second run changes
nothing. If `beet update` already removed the items, `--catalogue` adds the album again with
new ids and added dates and without the fields set by hand; restore the backup from step 1
instead to keep them. Tested in a throwaway library on a directory laid out like each mount's
names (synthetic disc, beets 2.12.0 and 2.14.1); not yet run against a real sacdfs mount.
The same run records the file's mtime for catalogued items that have none (see above).

## Keeping your tags: `sacd-tags-export`

sacdfs 0.3.0 can serve your own tags over an image's: a **tags directory** (`--tags DIR`,
`SACDFS_TAGS` in the container) holds one TOML file per disc. `beet sacd-tags-export` writes
those files from beets, so the genres, MusicBrainz IDs and cover art you have in beets survive
deleting the extracts:

<!-- docs-run: -->
```sh
beet sacd-tags-export --tags ~/sacd-tags                  # every SACD album
beet sacd-tags-export --tags ~/sacd-tags -n genre:jazz    # a query; -n only reports
```

It covers the albums whose items have `sacd_iso`, `sacd_area` and `sacd_track` (from
`sacd-migrate` or `--catalogue`). For each disc it works out the file name the way sacdfs does
(`sacdfs tags key`: a hash of the disc's table of contents, read from the ISO, which is only
read) and writes, for the album's area (`[stereo.*]` or `[multichannel.*]`): `genre`,
`publisher` (the label), `MusicBrainz Album Id`, `Release Group Id` and `Album Artist Id`, and
the album's cover as a `.jpg` or `.png` file (JPEG or PNG up to 960 KiB) named by `art`, whose name is the file name's key, a hyphen and the area;
per track, the recording (`UFID`), release track and artist IDs. It leaves everything else in
an existing file alone, so your own edits stay, and rewrites the file atomically, only when
something changed (comments in it are not kept). A beets value replaces the same field in the
area's section; a field beets has no value for is not touched. A file that is not valid TOML is
left as it is. A disc with nothing to export (no genre, label, IDs or cover) gets no file. sacdfs
shows the change within a few seconds.

## DVD-Audio, DVD-Video and Blu-ray images

Disc-image folders often hold DVD and Blu-ray images next to SACDs. The plugin
identifies them and lists them, but doesn't convert them: `beet sacd-info`
prints one line for each, and imports log why each was left alone.

```text
== .../Bluray/LIVE_CONCERT.iso
  Blu-ray image, volume 'LIVE_CONCERT', 4 playlists: catalogued, not converted
== .../DVDA/SURROUND_MIX.iso
  DVD-Audio + DVD-Video image, volume 'SURROUND_MIX', 5 title sets: catalogued, not converted
```

It reads the image's file system (UDF, including the UDF 2.50 metadata
partition that Blu-ray uses, or ISO 9660) and looks for the standard folders:
`AUDIO_TS` with `AUDIO_TS.IFO` for DVD-Audio, `VIDEO_TS` with `VIDEO_TS.IFO` for
DVD-Video and `BDMV` with `index.bdmv` for Blu-ray. The count is of DVD title sets or Blu-ray playlists.
This lives in the plugin (`beetsplug/_sacd_discimage.py`), not in pysacd, and
reads only directory structures, never the audio.

## See also

- [Options and configuration](options.md)
- [Design](design.md): hybrid SACDs and the import steps
- [Install](install/README.md)
- [sacdfs](https://github.com/dsd-toolbox/sacdfs)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
