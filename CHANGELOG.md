# Changelog

Notable changes in each release of beets-pysacd. Versions follow
[semantic versioning](https://semver.org/); before 1.0, a minor version may change
behaviour, and a patch version only adds or fixes. Releases are on
[GitHub](https://github.com/aclater/beets-pysacd/releases) and
[PyPI](https://pypi.org/project/beets-pysacd/), with signed build provenance.

## Unreleased

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
