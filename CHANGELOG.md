# Changelog

Notable changes in each release of beets-pysacd. Versions follow
[semantic versioning](https://semver.org/); before 1.0, a minor version may change
behaviour, and a patch version only adds or fixes. Releases are on
[GitHub](https://github.com/aclater/beets-pysacd/releases) and
[PyPI](https://pypi.org/project/beets-pysacd/), with signed build provenance.

## Unreleased

### Fixes
- `sacd-migrate --mount DIR` moves albums catalogued on a sacdfs 0.4.0 mount to the names
  sacdfs 0.4.1 shows (`NN.dsf` to `NN - Track NN.dsf` for a track with no title), so `beet update`
  no longer removes their items after the mount is upgraded (#57). Without `--apply` it only
  reports. An item moves only when its old file is gone and the new name is the one file the
  mount shows for that track number; it keeps its id, added date and every other field. Nothing
  on the mount is touched and no item is removed. The upgrade order is in the README ("Upgrading
  the mount from sacdfs 0.4.0 to 0.4.1"). Tested on a throwaway library with directories laid
  out like each version's names, on the oldest and newest beets; not yet against a real mount.
  Measured on such a library: `beet update` after the upgrade removed all 3 items of a
  catalogued album, and cataloguing it again gave new items without the fields set by hand; with
  this change, the items keep those fields.

### Build and release
- The release workflow refuses a `v*` tag that isn't `v` plus the package version, or whose commit
  isn't on `main` or a `release/*` branch, before anything is built or published (#65).

## 0.2.1 (2026-11-14)

A security release for users of `remove_iso` (off by default). **If you use `remove_iso: yes` or
`--remove-iso`, upgrade.** Found in a private review asked for by the maintainer. Checked by hand
before release, since CI doesn't run on private fixes: ruff, mypy and the test suite on the newest
and the oldest supported beets (2.14.1 and 2.12.0; Python 3.13, pysacd 0.5.0, in a Fedora 44
container): 122 passed, the 3 expected skips.

### Security

- Advisory GHSA-mjx6-hpg7-mjqj (medium; only with `remove_iso: yes` or `--remove-iso`, which are
  off by default): an image whose areas were all already in the library was deleted without any
  check of its own audio. "Already in the library" is decided by the disc fingerprint, which is the
  TOCs and the image size, not the audio, so a good rip could be deleted as a duplicate of a damaged
  one imported earlier, or of another image with the same TOC and size, and the library kept the
  first one's audio. Now an image is removed only when every selected area was imported from it in
  that run and verified; an image with an area already in the library is kept, and the log names
  that area. An area whose conversion fails also keeps the image. Each image is now verified by the
  album made from that image, not by any album with its fingerprint: when two images with one
  fingerprint are imported together, beets imports one and skips the other as a duplicate, and the
  skipped one is kept. Upgrade to 0.2.1.

### Other changes

- `sacdfs_path` now follows sacdfs 0.4.1's file names, so it matches a mount for a disc whose tracks have
  no title (`NN - Track NN.dsf`; control characters and long titles are handled as sacdfs does) (#55).
  Before, `sacd-migrate --catalogue --mount` recorded `NN.dsf` for such discs: the catalogued items
  pointed at files an 0.4.1 mount does not have, and `beet update` then removed them from the library
  (12 of 12 on one disc). With `--catalogue --mount`, a mount that shows only `NN.dsf` (sacdfs 0.4.0)
  still gets that name. Catalogued titles without a disc title are now `Track NN`, as sacdfs tags them.
  Albums already catalogued by 0.2.0 on a no-text disc keep their old paths; this change does not rewrite them.
  Tested with sacdfs's own naming cases and against a real no-text disc on both sacdfs versions.
- CI tests on Python 3.15 ahead of beets' own support (#50). Not claimed as supported: beets doesn't
  yet install on 3.15 without `--ignore-requires-python`. See the README.
- CI names every skipped test and fails if a skip is new, has stopped or has a different reason
  (`tests/expected-skips.json`), so a test job can't go quiet the way pysacd's comparison did (#51).
  The three skips today: the live MusicBrainz test, the fuzz-regression replay (no regression files
  yet) and the sacdfs mount test, which has its own job.

## 0.2.0 (2026-11-02)

- New `beet sacd-tags-export --tags DIR [QUERY]`: writes sacdfs's tag-layer files (genre, label,
  MusicBrainz IDs, cover art) from the albums `sacd-migrate` matched to an ISO, keyed by the
  disc's TOC as sacdfs does, merging with the fields already in each file (#42).
- New `beet sacd-migrate`: finds the library albums that are extracts of an ISO and records
  `sacd_iso`, `sacd_track` and the sacdfs path of each track, so extracts can be deleted once
  sacdfs serves the ISO (part of #38). Report-only unless `--apply`; never deletes files.
  `--verify REPORT` reads a `sacdfs verify` report and records only albums whose every
  extract is IDENTICAL or IDENTICAL-PAUSE; `--catalogue --mount DIR` adds an album for an
  ISO area that has no extracts (#38).
- CI's "pysacd release" legs test pysacd 0.3.0, which reads and decodes through
  scarletbook-rs. Disc fingerprints are unchanged from 0.2.2 (checked on the owner's
  library), so the plugin needs no change.
- Releases carry their build provenance as `<file>.intoto.jsonl` assets, so a download
  can be verified offline (`gh attestation verify <file> --repo aclater/beets-pysacd
  --bundle <file>.intoto.jsonl`); 0.1.0 to 0.1.2 have them too (#20).

## 0.1.2 (2026-10-30)

- When pysacd's MusicBrainz match isn't used, or there is none, beets now prefers an
  SACD edition over the same album's CD edition, for the plugin's own imports only:
  an SACD pattern goes first in `match.preferred.media` during their lookup, and your
  own setting is restored afterwards (#9, #17).

No security fixes.

## 0.1.1 (2026-10-29)

- `pauses: yes` (or `sacd-import --pauses`) includes the pauses between tracks, cutting
  them as `pysacd-extract -b` does, so a library extracted with pauses gets identical
  tracks. Needs pysacd 0.2.1 (#10, #13).
- README: installing next to a distribution-packaged `beet`, such as Fedora's, which
  can't see packages pip installs into `~/.local` or `/usr/local` (#11, #12).

No security fixes.

## 0.1.0 (2026-10-29)

First release.

- `beet sacd-import` converts each SACD area (stereo, multichannel or both) with pysacd
  to DSF or FLAC and imports it as an album; plain `beet import` does the same for ISOs
  it finds (`auto`). `beet sacd-info` prints a disc's TOC.
- Hybrid SACDs: each area is imported onto its own medium of the MusicBrainz release,
  not the CD layer beets would otherwise choose.
- A match on another format's edition (vinyl, CD, digital) isn't used; a match on a
  hybrid's CD layer keeps the release and takes its SACD layer (#7, #8).
- DVD-Audio, DVD-Video and Blu-ray images are identified and catalogued, never
  converted (#5, #6).
- ISO images are kept unless `remove_iso: yes`, and then removed only after every area's
  import is verified.
- Supports beets 2.12 and later, Python 3.11 to 3.14, on Linux, macOS and Windows.
