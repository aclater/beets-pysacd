[beets-pysacd](../../README.md) › [Documentation](../README.md) › Install

# Install

How to install the plugin with pip, what it needs, and how to check a release download. With
beets from a Linux distribution's package, see [beets from a distribution package](packages.md).

## From PyPI

```sh
pip install beets-pysacd
```

Then enable the plugin, with beets' MusicBrainz plugin, in your beets config:

```yaml
plugins: musicbrainz sacd
```

## Requirements

| Component | Version |
|---|---|
| Python | 3.11 to 3.14 |
| beets | 2.12 or later (2.x) |
| pysacd | 0.2 or later (its engine, and libFLAC for `format: flac`) |

The plugin is pure Python. pysacd's wheels carry the engine for Linux (x86-64, aarch64), macOS
and Windows.

Python 3.15 is tested in CI ahead of beets' own support: beets itself doesn't yet install on
Python 3.15 without `--ignore-requires-python` (beets 2.9 to 2.14.1, the latest, declare
`Requires-Python <3.15`), and the PyYAML release CI locks (6.0.3) has no 3.15 wheel, so CI builds
it from its sdist. The suite passes there. Until beets supports 3.15, use Python 3.11 to 3.14.

## Checking a download

Each [GitHub release](https://github.com/dsd-toolbox/beets-pysacd/releases) has the wheel and the
sdist, each with its build provenance attestation beside it as a `.intoto.jsonl` file. They are
not otherwise signed. For the 0.2.2 wheel:

```sh
gh attestation verify beets_pysacd-0.2.2-py3-none-any.whl --repo aclater/beets-pysacd
```

or offline, against the attached bundle:

```sh
gh attestation verify beets_pysacd-0.2.2-py3-none-any.whl --repo aclater/beets-pysacd \
    --bundle beets_pysacd-0.2.2-py3-none-any.whl.intoto.jsonl
```

## See also

- [Beets from a distribution package](packages.md)
- [User guide](../user-guide.md)
- [Options and configuration](../options.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
