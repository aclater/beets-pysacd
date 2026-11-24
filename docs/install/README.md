[beets-pysacd](../../README.md) › [Documentation](../README.md) › Install

# Install

How to install the plugin with pip, what it needs, and how to check a release download. With
beets from a Linux distribution's package, see [beets from a distribution package](packages.md).
On Windows, follow [install on Windows](windows.md).

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
Releases up to 0.2.2 were built before the repository moved to the DSD Toolbox organisation, so
their attestation names `aclater/beets-pysacd`. For the <!-- facts:release repo=dsd-toolbox/beets-pysacd fmt="{version}" -->0.2.2<!-- /facts --> wheel, checked offline against the attached bundle, with no sign-in:

<!-- docs-run: -->
<!-- docs-lint: ignore old-owner -- releases up to 0.2.2 were signed as aclater/beets-pysacd and verify only under that name -->
```sh
# facts:release repo=dsd-toolbox/beets-pysacd fmt="gh attestation verify beets_pysacd-{version}-py3-none-any.whl --repo aclater/beets-pysacd --bundle beets_pysacd-{version}-py3-none-any.whl.intoto.jsonl"
gh attestation verify beets_pysacd-0.2.2-py3-none-any.whl --repo aclater/beets-pysacd --bundle beets_pysacd-0.2.2-py3-none-any.whl.intoto.jsonl
# /facts
```

The command prints nothing and exits 0 when the wheel matches. Tested on the 0.2.2 wheel
(2026-11-24):

<!-- docs-lint: ignore old-owner -- the table lists what each name gives for the 0.2.2 release signed as aclater/beets-pysacd -->
| Command | Result |
|---|---|
| `--repo aclater/beets-pysacd --bundle` | passes, no sign-in needed |
| `--repo dsd-toolbox/beets-pysacd --bundle` | fails: `verifying with issuer "sigstore.dev"` |
| `--repo aclater/beets-pysacd` (online) | fails: HTTP 404 |
| `--repo dsd-toolbox/beets-pysacd` (online) | fails: HTTP 404 |
| `--owner aclater --signer-repo aclater/beets-pysacd` (online, signed in with `gh auth login`) | passes |

So for 0.2.2 and earlier use the bundle form above; the online form works only with `--owner`
and `--signer-repo`, not with `--repo`.

Releases from 0.2.3 are published and signed from `dsd-toolbox/beets-pysacd`, so they verify with
`--repo dsd-toolbox/beets-pysacd`, with the bundle (as above, with the release's wheel and bundle
names) or online after `gh auth login` and without `--bundle`. The
[release test plan](../release-test-plan.md) checks both forms on each release.

## See also

- [Install on Windows](windows.md)
- [Beets from a distribution package](packages.md)
- [User guide](../user-guide.md)
- [Options and configuration](../options.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
