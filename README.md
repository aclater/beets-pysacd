# beets-pysacd

A [beets](https://beets.io) plugin that imports SACD ISO images, using
[pysacd](https://github.com/aclater/pysacd).

beets can't tag an `.iso`. For each disc image this plugin reads the TOC,
finds the MusicBrainz release and the medium (the SACD stereo or multichannel
layer) that the disc is, converts each selected area to DSF or FLAC in a
staging directory, and imports that through beets' normal importer. Each area
becomes an album of its own, on its own medium of the release.

## Install

```sh
pip install beets-pysacd
```

Then enable the plugin, with beets' MusicBrainz plugin, in your beets config:

```yaml
plugins: musicbrainz sacd
```

Requirements: Python 3.11 or later, beets 2.12 or later (2.x), pysacd 0.2 or
later (its engine, and libFLAC for `format: flac`).

## Use

```sh
beet sacd-import Album.iso              # one image
beet sacd-import ~/rips/                # every .iso under a directory
beet sacd-import -a both -f flac Album.iso
beet sacd-import --release 1d1f0a6e-... Album.iso   # use this MusicBrainz release
beet sacd-info Album.iso                # print the TOC; changes nothing
```

Plain `beet import` also converts the ISO images it finds (an `.iso` given on
the command line, or inside a directory being imported) before importing them.
Your other files in the same run are imported exactly as your settings say.
Turn this off with `auto: no`.

An area that is already in the library is skipped. Imported albums carry two
flexible attributes, `sacd_iso_sha` (a fingerprint of the disc's TOCs) and
`sacd_area` (`stereo` or `multichannel`), so `beet ls sacd_area:multichannel`
lists the multichannel albums.

## Configuration

```yaml
sacd:
    areas: stereo        # stereo | multichannel | both
    format: dsf          # dsf | flac (24-bit PCM)
    pcm_rate: 88200      # flac: 88200 | 176400
    auto: yes            # convert ISOs found by plain `beet import`
    remove_iso: no       # delete an ISO once its import is verified
    staging: ''          # where to convert; default: a hidden directory in the library directory
    musicbrainz: yes     # let pysacd find the release (barcode, catalogue number, ISRCs)
    contact: ''          # contact (e.g. an e-mail address) for pysacd's MusicBrainz User-Agent
    threads: 0           # conversion threads; 0 = one per CPU
```

`sacd-import` options override `areas`, `format`, `pcm_rate` and `remove_iso`
for one run.

### Keeping or removing ISO images

ISO images are kept by default, and never written to. With `remove_iso: yes`
(or `--remove-iso`) an image is deleted only after every selected area has
been imported and verified: an album with that disc's fingerprint and area
exists in the library, with all of the area's tracks, and every file exists.
An import you skip, or one that fails, keeps the image.

### Files and staging

Converted files always move from the staging directory into your library,
whatever `copy`, `move` or in-place settings you use for other files: the
staging directory is temporary and is deleted afterwards, also after an error.
By default it is created inside the library directory, so the move is a
rename on the same filesystem; set `staging` to put it elsewhere.

## Hybrid SACDs

MusicBrainz lists a hybrid SACD as one release with several media: the CD
layer, the SACD stereo layer and sometimes the SACD multichannel layer, all
with the same recordings. beets puts the tracks of every medium into one
candidate and then matches files to tracks. With the same recordings on every
layer, it maps the SACD files to the CD layer (medium 1), overwrites their
release track IDs, and writes the album-level `media` as "Media". See the
[beets discussion](https://github.com/beetbox/beets/discussions/6614).

This plugin keeps each area on its own medium:

- When pysacd matched the release, it knows the medium: that release's
  candidates are cut down to that medium before beets compares them, and the
  album's `media` is that medium's format, e.g. "Hybrid SACD (SACD layer,
  2 channels)".
- Without pysacd's match, the medium is the one SACD-layer medium of the
  candidate with the area's track count and channel type. If that is
  ambiguous (a set of two SACDs, say), the candidate is left as beets made it.
- A final check after you choose a match maps the files to the medium if
  they still point elsewhere, and logs it.

Two areas of one release are different albums (different media), so beets
doesn't treat the second as a duplicate of the first.

## Development

```sh
pip install -e '.[dev]'
ruff check . && mypy beetsplug
PYSACD_TESTS=/path/to/pysacd/tests pytest -q
```

The tests build synthetic SACD images with pysacd's test generator
(`tests/sacdgen.py` in the pysacd source tree, found through `PYSACD_TESTS`,
default `../pysacd/tests`) and import them into a throwaway beets library.
MusicBrainz is mocked with a hybrid release whose media share recordings, so
the tests need no network.

## Licence

GPL-2.0-or-later (see [LICENSE](LICENSE)). The plugin imports pysacd, which is
GPL-2.0-or-later.
