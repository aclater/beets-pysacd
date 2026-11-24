<img src="https://raw.githubusercontent.com/dsd-toolbox/beets-pysacd/main/docs/assets/icon-256.png" alt="" width="96">

# beets-pysacd

[![CI](https://github.com/dsd-toolbox/beets-pysacd/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dsd-toolbox/beets-pysacd/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/aclater/beets-pysacd/branch/main/graph/badge.svg)](https://codecov.io/gh/aclater/beets-pysacd)
[![CodeQL](https://github.com/dsd-toolbox/beets-pysacd/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/dsd-toolbox/beets-pysacd/actions/workflows/codeql.yml)
[![License: GPL-2.0-or-later](https://img.shields.io/badge/license-GPL--2.0--or--later-blue)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/dsd-toolbox/beets-pysacd/badge)](https://scorecard.dev/viewer/?uri=github.com/dsd-toolbox/beets-pysacd)
[![PyPI](https://img.shields.io/pypi/v/beets-pysacd)](https://pypi.org/project/beets-pysacd/)

beets-pysacd is a [beets](https://beets.io) plugin that imports SACD images (`.iso`), which beets
can't tag on its own: it reads each disc with [pysacd](https://github.com/dsd-toolbox/pysacd), finds
the MusicBrainz release and the SACD layer the disc is, and imports each area as DSF or FLAC
through beets' normal importer. Each area becomes an album of its own, on its own medium of the
release, so stereo and multichannel layers stay apart in your library.

## Platforms

| System | How | Guide |
|---|---|---|
| Linux, macOS, Windows | A pure-Python wheel on PyPI, for Python 3.11 to 3.14 with beets 2.12 or later (2.x). It needs pysacd 0.2 or later, whose wheels carry the engine for Linux (x86-64, aarch64), macOS and Windows. CI tests the oldest and newest beets on Linux, and the newest on macOS and Windows | [install](docs/install/README.md) |

Each [GitHub release](https://github.com/dsd-toolbox/beets-pysacd/releases) has the wheel and the
sdist with a build provenance attestation, checkable with `gh attestation verify`. They are not
otherwise signed. With beets from a Linux distribution's package, see
[beets from a distribution package](docs/install/packages.md) for making the plugin importable.

## Quick start

You need Python 3.11 to 3.14 on Linux or macOS, and an SACD image. The commands use
`album.iso` in the current folder; type your image's name instead. They install beets with the
plugin, so start here if you don't use beets yet; if you do, see [install](docs/install/README.md).

1. Install beets and the plugin in a virtual environment of their own:

   ```sh
   python3 -m venv beets-env
   . beets-env/bin/activate
   pip install beets beets-pysacd
   ```

2. Turn the plugin on, with beets' MusicBrainz plugin, and keep the library in `~/Music`:

   ```sh
   mkdir -p ~/.config/beets
   cat > ~/.config/beets/config.yaml <<'EOF'
   directory: ~/Music
   plugins: musicbrainz sacd
   EOF
   ```

3. Check that the plugin reads the disc:

   ```sh
   beet sacd-info album.iso
   ```

   *You should see* the album, then each area with its tracks.

4. Import it:

   ```sh
   beet sacd-import album.iso
   ```

   The plugin converts the stereo area to DSF and hands it to the beets importer, which shows the
   MusicBrainz release it found. Accept it, or pick another, as in any beets import. The tracks
   land in `~/Music`; `beet ls -a` lists the album.

The [user guide](docs/user-guide.md) has the other commands, [options and
configuration](docs/options.md) every option and setting, and [install](docs/install/README.md)
the other ways to install.

## Documentation

- [Documentation index](docs/README.md)
- [Install](docs/install/README.md): requirements, attestations, beets from a Linux distribution
- [User guide](docs/user-guide.md): `sacd-import`, `sacd-info`, moving a library from extracts
  to SACD images with [sacdfs](https://github.com/dsd-toolbox/sacdfs) (`sacd-migrate`), keeping your
  tags (`sacd-tags-export`), DVD and Blu-ray images
- [Options and configuration](docs/options.md): every option and setting, keeping or removing
  SACD images, staging
- [Design](docs/design.md): hybrid SACDs and the import steps
- [Development](docs/development.md): tests and CI
- [Changelog](CHANGELOG.md) · [releases](https://github.com/dsd-toolbox/beets-pysacd/releases) ·
  [contributing](CONTRIBUTING.md) · [security](SECURITY.md) ·
  [releases by major version](https://github.com/dsd-toolbox/dsd-toolbox/blob/main/RELEASES.md)

## Licence and credits

beets-pysacd is free software under the [GNU General Public License](LICENSE), version 2 or (at
your option) any later version.

- [beets](https://beets.io) (MIT) is the music library manager the plugin extends; it uses
  beets' importer, MusicBrainz plugin and test helpers.
- [pysacd](https://github.com/dsd-toolbox/pysacd) (GPL-2.0-or-later) reads the discs, matches
  MusicBrainz releases and converts the areas.
- [MusicBrainz](https://musicbrainz.org) supplies the release data.

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
