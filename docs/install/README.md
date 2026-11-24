[beets-pysacd](../../README.md) › [Documentation](../README.md) › Install

# Install

How to install the plugin with pip, what it needs, and how to check a release download. With
beets from a Linux distribution's package, see [beets from a distribution package](packages.md).

## From PyPI

<!-- docs-run: setup="dnf -y -q --setopt=install_weak_deps=False install python3-pip gh && python3 -m pip download -q --no-deps --only-binary :all: beets-pysacd && curl -fsSLO https://github.com/dsd-toolbox/beets-pysacd/releases/latest/download/$(ls beets_pysacd-*.whl).intoto.jsonl" expect="Successfully installed" -->
```sh
# facts:install kind=pip name=beets-pysacd
pip install beets-pysacd
# /facts
```

Then enable the plugin, with beets' MusicBrainz plugin, in your beets config:

```yaml
plugins: musicbrainz sacd
```

## Requirements

| Component | Version |
|---|---|
| Python | <!-- facts:python-min -->3.11<!-- /facts --> to 3.14 |
| beets | 2.12 or later (2.x) |
| pysacd | 0.2 or later (its engine, and libFLAC for `format: flac`) |

The plugin is pure Python. pysacd's wheels carry the engine for Linux (x86-64, aarch64), macOS
and Windows.

Python 3.15 is tested in CI ahead of beets' own support: beets itself doesn't yet install on
Python 3.15 without `--ignore-requires-python` (beets 2.9 to 2.14.1, the latest, declare
`Requires-Python <3.15`), and the PyYAML release CI locks (6.0.3) has no 3.15 wheel, so CI builds
it from its sdist. The suite passes there. Until beets supports 3.15, use Python <!-- facts:python-min -->3.11<!-- /facts --> to 3.14.

## Checking a download

Each [GitHub release](https://github.com/dsd-toolbox/beets-pysacd/releases) has the wheel and the
sdist, each with its build provenance attestation beside it as a `.intoto.jsonl` file. They are
not otherwise signed.

<!-- docs-lint: ignore old-owner -- releases up to 0.2.2 were signed as aclater/beets-pysacd and verify only under that name -->
Releases up to 0.2.2 verify under the repository's old name, `aclater/beets-pysacd`, as they were
built before it moved to the DSD Toolbox organisation; later releases verify as
`dsd-toolbox/beets-pysacd`. For the <!-- facts:release repo=dsd-toolbox/beets-pysacd fmt="{version}" -->0.2.2<!-- /facts --> wheel, with a GitHub login (`gh auth login`):

<!-- docs-run: skip="needs a GitHub login: the online check asks GitHub's attestation API" -->
<!-- docs-lint: ignore old-owner -- releases up to 0.2.2 were signed as aclater/beets-pysacd and verify only under that name -->
```sh
# facts:release repo=dsd-toolbox/beets-pysacd fmt="gh attestation verify beets_pysacd-{version}-py3-none-any.whl --owner aclater --signer-repo aclater/beets-pysacd"
gh attestation verify beets_pysacd-0.2.2-py3-none-any.whl --owner aclater --signer-repo aclater/beets-pysacd
# /facts
```

or offline, against the attached bundle, with no login:

<!-- docs-run: -->
<!-- docs-lint: ignore old-owner -- releases up to 0.2.2 were signed as aclater/beets-pysacd and verify only under that name -->
```sh
# facts:release repo=dsd-toolbox/beets-pysacd fmt="gh attestation verify beets_pysacd-{version}-py3-none-any.whl --repo aclater/beets-pysacd --bundle beets_pysacd-{version}-py3-none-any.whl.intoto.jsonl"
gh attestation verify beets_pysacd-0.2.2-py3-none-any.whl --repo aclater/beets-pysacd --bundle beets_pysacd-0.2.2-py3-none-any.whl.intoto.jsonl
# /facts
```

## See also

- [Beets from a distribution package](packages.md)
- [User guide](../user-guide.md)
- [Options and configuration](../options.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
