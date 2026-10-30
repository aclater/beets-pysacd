# beets-pysacd

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/aclater/beets-pysacd/badge)](https://scorecard.dev/viewer/?uri=github.com/aclater/beets-pysacd)

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

Each [GitHub release](https://github.com/aclater/beets-pysacd/releases) has the wheel
and the sdist, each with its build provenance attestation beside it as
`<file>.intoto.jsonl`. Check a download with
`gh attestation verify <file> --repo aclater/beets-pysacd`, or offline against the
attached bundle by adding `--bundle <file>.intoto.jsonl`.

The plugin must be importable by the Python that runs `beet`. With beets from a
Linux distribution's package, that is the system Python, and it may not look
where `pip` installed the plugin. Fedora's `/usr/bin/beet`, for example, runs
`python3 -sP`, which leaves out both `~/.local` and `/usr/local`, so beets
reports that it can't load the `sacd` plugin. Either install beets and the
plugin into one environment of their own:

```sh
pipx install beets
pipx inject beets beets-pysacd
```

or keep the packaged beets and add pip's directory to its path, for example
`PYTHONPATH=/usr/local/lib/python3.14/site-packages:/usr/local/lib64/python3.14/site-packages beet ...`
(pysacd's engine is under `lib64`).

## Use

```sh
beet sacd-import Album.iso              # one image
beet sacd-import ~/rips/                # every .iso under a directory
beet sacd-import -a both -f flac Album.iso
beet sacd-import --release 1d1f0a6e-... Album.iso   # use this MusicBrainz release
beet sacd-info Album.iso                # print the TOC; changes nothing
beet sacd-info ~/rips/                  # ...of every image under a directory
```

Plain `beet import` also converts the ISO images it finds (an `.iso` given on
the command line, or inside a directory being imported) before importing them.
Your other files in the same run are imported exactly as your settings say.
Turn this off with `auto: no`.

An area that is already in the library is skipped. Imported albums carry two
flexible attributes, `sacd_iso_sha` (a fingerprint of the disc's TOCs) and
`sacd_area` (`stereo` or `multichannel`), so `beet ls sacd_area:multichannel`
lists the multichannel albums.

### DVD-Audio, DVD-Video and Blu-ray images

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
`AUDIO_TS` with `AUDIO_TS.IFO` for DVD-Audio, `VIDEO_TS` for DVD-Video and
`BDMV` for Blu-ray. The count is of DVD title sets or Blu-ray playlists.
This lives in the plugin (`beetsplug/_sacd_discimage.py`), not in pysacd, and
reads only directory structures, never the audio.

## Configuration

```yaml
sacd:
    areas: stereo        # stereo | multichannel | both
    format: dsf          # dsf | flac (24-bit PCM)
    pcm_rate: 88200      # flac: 88200 | 176400
    pauses: no           # include the pauses between tracks (pysacd 0.2.1 or later)
    auto: yes            # convert ISOs found by plain `beet import`
    remove_iso: no       # delete an ISO once its import is verified
    staging: ''          # where to convert; default: a hidden directory in the library directory
    musicbrainz: yes     # let pysacd find the release (barcode, catalogue number, ISRCs)
    contact: ''          # contact (e.g. an e-mail address) for pysacd's MusicBrainz User-Agent
    threads: 0           # conversion threads; 0 = one per CPU
```

`sacd-import` options override `areas`, `format`, `pcm_rate`, `pauses` and
`remove_iso` for one run.

Tracks are cut at their timecodes, without the pauses between them, like
`pysacd convert`. With `pauses: yes` (or `--pauses`) each pause goes with the
track before it, exactly as `pysacd-extract -b` and `sacd_extract -b` cut them:
use it when your library already holds extracts made that way, so the same
disc gives the same tracks. It needs pysacd 0.2.1 or later.

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

## How it works

For each ISO image, and each selected area of it:

1. pysacd reads the TOC (read-only) and fingerprints the disc from its TOCs.
   An area whose fingerprint and area are already in the library is skipped.
2. pysacd matches the MusicBrainz release and medium, and converts the area
   into the staging directory, writing the release's IDs into the files.
   A match on a medium that isn't an SACD layer (a vinyl, CD or digital
   edition sharing the catalogue number or barcode) isn't used: the area is
   converted without IDs and beets matches it the normal way, preferring
   an SACD edition (see below). A match on the
   CD layer of a hybrid release keeps the release; the area goes to that
   release's SACD layer with its track count and channels.
3. beets imports the staging directory. Because the files agree on the
   release ID, beets looks that release up directly. For this one import task
   only, the plugin then:
   - **hides the physical-disc tags from matching.** pysacd tags the physical
     disc ("disc 1 of 1", media "Hybrid SACD"), but MusicBrainz counts each
     layer as a medium ("disc 2 of 3", "Hybrid SACD (SACD layer, 2
     channels)"). beets would count those tags against the right candidate,
     enough to keep a correct match from being applied automatically. beets
     writes the medium's own values when it applies the match;
   - **cuts the release's candidates down to the area's medium** (see
     [Hybrid SACDs](#hybrid-sacds));
   - **prefers SACD editions.** Without pysacd's release, beets would take
     whichever edition of the album scores best, often the CD. For this task
     only, an SACD medium goes first in `match.preferred.media`; your own
     preferred media follow it, and other imports don't see the change;
   - **counts only an album on the same medium as a duplicate.** beets' default
     duplicate keys are album artist and album, which both areas of a disc
     (and a CD rip of the same release) share: without this, importing the
     multichannel area after the stereo one would be skipped as a duplicate.
     Another copy of the same layer is still a duplicate;
   - **moves the files** into the library (see [Files and staging](#files-and-staging)).
4. The album gets `sacd_iso_sha` and `sacd_area`; with `remove_iso`, the ISO is
   deleted once every area is verified. The staging directory is removed.

Nothing here changes how beets treats your other files in the same import.

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
the tests need no network. DVD and Blu-ray images for the cataloguing tests
come from `tests/discgen.py`, which writes minimal UDF and ISO 9660 file
systems.

`tests/test_live_musicbrainz.py` is the exception: it runs the plugin's matching
against a real hybrid SACD release on musicbrainz.org (two requests). It skips
unless `PYSACD_LIVE_MB=1`:

```sh
PYSACD_LIVE_MB=1 pytest tests/test_live_musicbrainz.py
```

### CI

Every pull request runs ruff, mypy and the tests (Python 3.11 to 3.14, the oldest
and newest beets, Linux, macOS and Windows, pysacd's release and master branch),
CodeQL, semgrep, a privacy check, dependency review (fails on high or critical
vulnerabilities) and an AI review. One test leg runs under coverage.py and shows
the report in its job summary, with HTML and XML reports as the `coverage`
artifact; nothing goes to an external service. Changes to workflows are linted with
[zizmor](https://docs.zizmor.sh) (`pipx run zizmor==1.30.1 --no-online-audits
.github/workflows`), and changes to this README get a link check (lychee).

Changes to the DVD/Blu-ray identifier (`beetsplug/_sacd_discimage.py`) or the
harness are fuzzed for 150 seconds with [Atheris](https://github.com/google/atheris)
(`fuzz/fuzz_discimage.py`, seeded from `tests/discgen.py`'s images; its docstring shows
how to run it locally). A crashing input is uploaded as the `fuzz-crashes` artifact; once
fixed, it goes into `fuzz/regressions/`, which the tests replay.

Weekly: OpenSSF Scorecard (also on every push to `main`; results published for
the badge and shown under code scanning), the live MusicBrainz test, the link
check, the test matrix, to catch new beets and pysacd releases, and 20 minutes of
fuzzing.

CI installs every Python dependency hash-checked (`pip install --require-hashes`),
from two lock files written by `python3 -I scripts/lock.py` (needs
[uv](https://docs.astral.sh/uv/)): `locks/latest/requirements.txt` with the newest
beets and `locks/oldest/requirements.txt` with beets held at the floor in
`pyproject.toml` (plus `locks/fuzz/requirements.txt`, Atheris). Both cover Python 3.11 to 3.14 on Linux, macOS and Windows, and
leave out releases younger than two weeks, except pysacd's and security fixes listed
in the script. The plugin, and pysacd's master branch on that leg, are installed on
top with `--no-deps`, so nothing unhashed is downloaded. Dependabot keeps both locks
current (beets stays on the floor in the oldest); when a new release brings a new
dependency, the locked install fails on Dependabot's PR, and rerunning
`scripts/lock.py` there fixes it. Rerun it, too, after changing dependencies in
`pyproject.toml`. For local work, `pip install -e '.[dev]'` still works.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report bugs and propose changes,
[SECURITY.md](SECURITY.md) for reporting a vulnerability privately, and the
[changelog](CHANGELOG.md) for what changed in each release.

## Licence

GPL-2.0-or-later (see [LICENSE](LICENSE)). The plugin imports pysacd, which is
GPL-2.0-or-later.
