# Changelog

Notable changes in each release of beets-pysacd. Versions follow
[semantic versioning](https://semver.org/); before 1.0, a minor version may change
behaviour, and a patch version only adds or fixes. Releases are on
[GitHub](https://github.com/aclater/beets-pysacd/releases) and
[PyPI](https://pypi.org/project/beets-pysacd/), with signed build provenance.

## Unreleased

- CI's Linux jobs run in Red Hat-derived containers: lint, the Linux test legs, fuzzing and the live
  MusicBrainz check and the release build in Fedora 44, semgrep, zizmor and the privacy check in UBI 10, with semgrep and
  zizmor installed from PyPI by hash instead of their vendors' images. CI only; the plugin is unchanged.
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
