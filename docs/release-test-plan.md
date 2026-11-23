[beets-pysacd](../README.md) › [Documentation](README.md) › Release test plan

# Release test plan

Every beets-pysacd release runs this plan in full, on the release commit or on the published files,
and records each result in the release issue with the [sign-off table](#sign-off). CI proves what
the tests say on synthetic discs and a mocked MusicBrainz; this plan adds the newest pysacd, real
discs, live MusicBrainz, the published wheel and longer fuzzing. The plan was validated on
2026-11-23 against 0.2.2 from PyPI and pysacd 0.5.5; each section says which steps were run and
which are new.

## How to use this plan

- **Two words stand for versions.** VERSION is the release under test (`version` in
  `pyproject.toml` after the bump) and PREVIOUS is the release before it (`git describe --tags
  --abbrev=0` on `main` before tagging, without the `v`). PYSACD is the newest pysacd release
  ([PyPI](https://pypi.org/project/pysacd/)). Every other value is literal.
- **When each step runs.** Steps 1 to 4 run on the release commit before the tag; steps 5 to 9 on
  the published files after it. A failing step blocks the tag; a failure after the tag means a patch
  release.
- **What blocks.** A failing or newly skipping test, a fuzz crash, an import that matches,
  tags or files differently from PREVIOUS without a changelog entry saying so, a Quick start or
  docs command that fails as written, or a security finding without a `go`.
- **Where.** Linux steps run in a Fedora 44 container, like CI, with a memory cap. Tests never touch
  a real beets library: every run uses a throwaway beets directory.

## 1. The suite on every platform

**What CI covers** on the release pull request (link its run in the sign-off):

| Job | Platform | Python | beets | pysacd |
|---|---|---|---|---|
| `tests` | Fedora 44 x86-64 container | 3.11 | oldest (the floor) and latest | the locked release |
| `tests` | Fedora 44 x86-64 container | 3.12, 3.13 (with coverage), 3.14, 3.15 | latest | the locked release |
| `tests` | Fedora 44 x86-64 container | 3.13 | latest | master |
| `tests` | macOS (arm64), Windows x86-64 | 3.13 | latest | the locked release |
| `tags served by sacdfs main` | Ubuntu runner, sacdfs in a container | 3.13 | latest | the locked release |
| `lint` | Fedora 44 | 3.13 | | ruff, mypy, the version claims in the docs |

Every test job fails if a test starts or stops skipping, or its reason changes
(`tests/expected-skips.json`).

**The locked pysacd can be older than the newest.** `locks/latest` pins the pysacd release that was
current when the lock was last written (0.5.2 on 2026-11-23, when 0.5.5 was out), so "release" in
CI can mean an old one. Run the suite against PYSACD on the oldest and the latest beets, from the
release commit:

```sh
git clone https://github.com/aclater/beets-pysacd beets-pysacd-release
git clone --depth 1 --branch vPYSACD https://github.com/aclater/pysacd pysacd-PYSACD
podman run --rm -it --memory 4g --cpus 2 -v ./beets-pysacd-release:/src:ro,Z -v ./pysacd-PYSACD:/pysacd:ro,Z registry.fedoraproject.org/fedora:44 bash
```

Inside the container:

```sh
dnf -y install git-core findutils python3.13 python3.13-devel gcc
cp -a /src /beets-pysacd && cd /beets-pysacd
python3.13 -m venv /v-latest && . /v-latest/bin/activate
pip install --require-hashes --only-binary :all: -r locks/latest/requirements.txt
pip install --no-deps --no-build-isolation -e . && pip install --no-deps pysacd==PYSACD
ruff check . && mypy beetsplug && python -I scripts/check_doc_versions.py
PYSACD_TESTS=/pysacd/tests PYSACD_TEST_REPORT=latest.json python -m pytest -q
python -I scripts/check_skips.py --job tests latest.json
deactivate && python3.13 -m venv /v-oldest && . /v-oldest/bin/activate
pip install --require-hashes --only-binary :all: -r locks/oldest/requirements.txt
pip install --no-deps --no-build-isolation -e . && pip install --no-deps pysacd==PYSACD
PYSACD_TESTS=/pysacd/tests PYSACD_TEST_REPORT=oldest.json python -m pytest -q
python -I scripts/check_skips.py --job tests oldest.json
```

*Expected:* every test passes and only the listed skips happen. *Validated:* 2026-11-23 on `main`
after 0.2.2, with pysacd 0.5.5 and with the locked 0.5.2, on beets 2.14.1 and 2.12.0.

**By hand on other platforms.** The plugin is pure Python; what differs by platform is pysacd's
wheel, which pysacd's own plan tests. Run the [Quick start](#6-quick-start-in-a-fresh-container) on
macOS 15 in a VM on Apple hardware with the published wheel. Windows is covered by CI's suite; the
plugin's Windows behaviour with a real disc is untested.

## 2. Identity: fixtures and real discs

**On fixtures (CI and step 1).** `tests/test_sacd.py` imports synthetic hybrid discs (stereo and
5.1) into a throwaway library against a MusicBrainz release whose media share recordings
(`tests/mbfixture.py`). It checks the match (release, medium and area), the tags written to each
DSF and FLAC file, the disc fingerprint, skipping an area already imported, `remove_iso` and the
staging clean-up. `tests/test_discimage.py` identifies DVD-Audio, DVD-Video and Blu-ray images.

**On real discs, against PREVIOUS (new).** The fixtures can't show how matching behaves on real
releases with many editions. Import the five discs of the [minimum set](#5-the-real-disc-corpus)
with PREVIOUS and with VERSION, each into its own throwaway library, with live MusicBrainz, and
compare:

```sh
mkdir -p ~/release-check/prev ~/release-check/new && cd ~/release-check
python3 -m venv prev/venv && prev/venv/bin/pip install beets beets-pysacd==PREVIOUS
python3 -m venv new/venv && new/venv/bin/pip install beets beets-pysacd==VERSION
printf 'directory: ~/release-check/prev/music\nlibrary: ~/release-check/prev/library.db\nplugins: musicbrainz sacd\n' > prev/config.yaml
printf 'directory: ~/release-check/new/music\nlibrary: ~/release-check/new/library.db\nplugins: musicbrainz sacd\n' > new/config.yaml
yes A | prev/venv/bin/beet -c prev/config.yaml sacd-import -a both DISC1.iso DISC2.iso DISC3.iso DISC4.iso DISC5.iso
yes A | new/venv/bin/beet -c new/config.yaml sacd-import -a both DISC1.iso DISC2.iso DISC3.iso DISC4.iso DISC5.iso
prev/venv/bin/beet -c prev/config.yaml ls -f '$mb_albumid $disc $track $title $sacd_area $sacd_iso_sha' > prev.txt
new/venv/bin/beet -c new/config.yaml ls -f '$mb_albumid $disc $track $title $sacd_area $sacd_iso_sha' > new.txt
diff prev.txt new.txt
(cd prev/music && find . -type f -name '*.dsf' -exec sha256sum {} +) | sort -k2 > prev.sha256
(cd new/music && find . -type f -name '*.dsf' -exec sha256sum {} +) | sort -k2 > new.sha256
diff prev.sha256 new.sha256
```

DISC1 to DISC5 are the maintainer's images (the `'$...'` fields are beets' own format, not shell
variables). *Expected:* no difference, or only what VERSION's changelog says changed. Record counts
(albums, items, matching releases) in the release issue, never titles. *New:* not yet run; the
first run sets the baseline.

## 3. Timed fuzzing

The plugin's own parser of untrusted bytes is the DVD and Blu-ray identifier
(`beetsplug/_sacd_discimage.py`). SACD images are parsed by pysacd and scarletbook-rs, which fuzz
them in their repositories. On the release commit, with Atheris (libFuzzer) from `locks/fuzz`:

| Target | Sanitizer | Time |
|---|---|---|
| `fuzz/fuzz_discimage.py` | Python exceptions (anything but `OSError` is a crash) | 30 min |

```sh
pip install --require-hashes --only-binary :all: -r locks/fuzz/requirements.txt
python fuzz/fuzz_discimage.py --seeds /tmp/fuzz-seeds
mkdir -p /tmp/fuzz-corpus crashes
python fuzz/fuzz_discimage.py -max_total_time=1800 -max_len=1048576 -timeout=10 -rss_limit_mb=2048 \
  -artifact_prefix=crashes/ /tmp/fuzz-corpus /tmp/fuzz-seeds
```

*Expected:* no crash. A crash's input goes, minimised, into `fuzz/regressions/` with its fix.
*Validated:* 2026-11-23 on `main` after 0.2.2, for 60 s.

## 4. Leak checks

Not applicable: the plugin has no native code. Its memory use is bounded by the suite's container
cap and pysacd's engine, which pysacd's plan checks with LeakSanitizer, valgrind and TSan.

## 5. The real-disc corpus

The real discs are the maintainer's SACD image library: images of discs the maintainer owns, read
only and never named in public. The minimum set is pysacd's, so results line up:

| Disc | Areas | Coding | Layers | Disc text |
|---|---|---|---|---|
| 1 | stereo and 5.1 | stereo plain DSD, 5.1 DST | hybrid | yes |
| 2 | stereo and 5.1 | both DST | hybrid | yes |
| 3 | stereo | DST | hybrid | yes |
| 4 | stereo | plain DSD | hybrid | none |
| 5 | stereo | plain DSD | single layer | yes |

Two cases the set lacks matter most for matching: a release with several SACD editions on
MusicBrainz, and a disc with no MusicBrainz release. Add one of each when the library has them.

## 6. Quick start in a fresh container

The README's Quick start, as written, with the wheel from PyPI, in a fresh Fedora 44 container, as a
normal user with a throwaway HOME. The `quickstart` workflow runs it on every pull request with a
wheel built from the branch; this step runs it on what users download. MusicBrainz answers come
from `tests/mbfixture.py`; [step 2](#2-identity-fixtures-and-real-discs) and the live test below
cover the real service.

```sh
git clone --depth 1 --branch vVERSION https://github.com/aclater/beets-pysacd beets-pysacd-VERSION
git clone --depth 1 --branch vPYSACD https://github.com/aclater/pysacd pysacd-PYSACD
podman run --rm --memory 4g --cpus 2 -v ./beets-pysacd-VERSION:/src:ro,Z -v ./pysacd-PYSACD:/pysacd:ro,Z registry.fedoraproject.org/fedora:44 bash -euc '
dnf -y -q install python3 python3-pip python3-numpy shadow-utils util-linux findutils
useradd -m quickstart && mkdir /work /qshome
python3 -I /src/scripts/readme_quickstart.py make-disc --pysacd-tests /pysacd/tests /work/album.iso
python3 -m pip download --no-deps --only-binary :all: -d /wheel beets-pysacd==VERSION
chown -R quickstart /work /qshome
runuser -u quickstart -- python3 -I /src/scripts/readme_quickstart.py run --wheel /wheel/*.whl --workdir /work --home /qshome'
```

*Expected:* "README Quick start: 4 steps ran as written, MusicBrainz from the fixture; 3 tracks
imported into ~/Music". Then, live, from the same tag:

```sh
PYSACD_LIVE_MB=1 python -m pytest tests/test_live_musicbrainz.py
```

*Validated:* 2026-11-23 with beets-pysacd 0.2.2 and pysacd 0.5.5 from PyPI (0.2.2's tag predates
`scripts/readme_quickstart.py`, so `main`'s copy ran the same Quick start); the live test on `main`.

## 7. Docs commands

Every command block in README.md and `docs/` is run against the release, or listed in the release
issue as not runnable with the reason. List them:

```sh
grep -n -E '^ *```(sh|console|python|yaml)$' README.md docs/*.md docs/install/*.md
```

0.2.2 had 17 shell and Python blocks and 2 YAML. Run them in the Quick start's container on the
generated `album.iso` (named `Album.iso` in the user guide). Not runnable, with why:

- `docs/user-guide.md`, `sacd-migrate --verify` and `--catalogue --mount`: need a sacdfs mount and
  `sacdfs verify`; run them with a sacdfs container build, as the `tags served by sacdfs main` job
  does, for a release that changes `sacd-migrate`;
- `docs/install/packages.md`, the `PYTHONPATH` line: needs beets from a distribution package
  installed under `/usr/local`; run it in a container with that layout for a release that changes
  packaging.

*Validated:* 2026-11-23, every shell and Python block parsed (`bash -n`, Python `compile`) on
`main` after 0.2.2; not yet run as a whole against a release.

## 8. Performance

No timing table: an import's time is pysacd's conversion, timed in
[pysacd's plan](https://github.com/aclater/pysacd/blob/master/docs/release-test-plan.md). The
plugin's own work per disc (TOC, fingerprint, matching) is small next to it, and
MusicBrainz's rate limit dominates matching.

## 9. Security

**Before the tag.** The security auditor, a reviewer separate from the release's author, reviews the
range from PREVIOUS's tag to the release commit (`git diff vPREVIOUS HEAD`): file deletion
(`remove_iso`), paths, staging, untrusted text, workflows and dependencies. The tag waits for its
`go` on that exact commit; a later commit needs a new `go`.

**After publishing.** The files on PyPI are the GitHub release's assets, and each carries a valid
build provenance attestation:

```sh
mkdir release-check && cd release-check
gh release download vVERSION -R aclater/beets-pysacd -D github
curl -s https://pypi.org/pypi/beets-pysacd/VERSION/json | python3 -I -c 'import json,sys; [print(u["digests"]["sha256"] + "  " + u["filename"]) for u in json.load(sys.stdin)["urls"]]' > pypi.sha256
(cd github && sha256sum -c ../pypi.sha256)
ls github | grep -vc intoto.jsonl && wc -l < pypi.sha256
find github -name '*.whl' -o -name '*.tar.gz' | xargs -I FILE gh attestation verify FILE --repo aclater/beets-pysacd
find github -name '*.whl' -o -name '*.tar.gz' | xargs -I FILE gh attestation verify FILE --repo aclater/beets-pysacd --bundle FILE.intoto.jsonl
```

*Expected:* both files `OK`, the two counts equal (2), every verification passes. *Validated:*
2026-11-23 on 0.2.2.

## 10. Fresh-eyes review for first releases

For a new minor or major line (0.3.0, 1.0.0) and for a release that adds a component (a new command
or a new kind of disc), a reviewer agent that did not write or review the changes, and gets none of
the author's notes, reads the release as a new user would. It gets the tag diff from the previous
minor line, the README and `docs/`, and the changelog section, and checks:

- that every changelog claim is true of the diff, and every user-visible change is in it;
- that each new command and setting works as the docs say, on a throwaway library;
- that nothing new can delete or overwrite a user's files or library entries without the
  documented checks;
- what is tested only on fixtures, and whether the docs say so.

Its findings go in the release issue. Each is fixed or answered before the tag.

## Sign-off

Copy this table into the release issue. Evidence is a link: a CI run, a comment with the output, a
changelog section.

| Step | Result | Evidence |
|---|---|---|
| 1. CI on the release pull request, all jobs | | |
| 1. Suite against the newest pysacd, oldest and latest beets | | |
| 2. Real discs: PREVIOUS against VERSION, counts | | |
| 3. Fuzzing: disc image identifier, 30 min | | |
| 6. Quick start from PyPI in a fresh container; live MusicBrainz test | | |
| 6. Quick start on macOS 15 (VM) | | |
| 7. Docs commands: run, or listed with why | | |
| 9. Auditor `go` on the release commit | | |
| 9. PyPI files match the GitHub assets, attestations verify | | |
| 10. Fresh-eyes review (new lines and components only) | | |

## See also

- [Releasing](../CONTRIBUTING.md#releasing)
- [Development](development.md): tests and CI
- [pysacd's release test plan](https://github.com/aclater/pysacd/blob/master/docs/release-test-plan.md)

Part of the [DSD Toolbox](https://github.com/aclater/dsd-toolbox).
