# Install

```sh
pip install beets-pysacd
```

Then enable the plugin, with beets' MusicBrainz plugin, in your beets config:

```yaml
plugins: musicbrainz sacd
```

Requirements: Python 3.11 or later, beets 2.12 or later (2.x), pysacd 0.2 or
later (its engine, and libFLAC for `format: flac`).

Python 3.15 is tested in CI ahead of beets' own support: beets itself doesn't yet install on
Python 3.15 without `--ignore-requires-python` (beets 2.9 to 2.14.1, the latest, declare
`Requires-Python <3.15`), and PyYAML has no 3.15 wheel, so CI builds it from its sdist. The suite
passes there. Until beets supports 3.15, use Python 3.11 to 3.14.

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
