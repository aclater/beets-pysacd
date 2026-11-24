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

<!-- docs-run: skip="maintainer release step: PYSACD and VERSION are filled in at release time, and it starts a Podman container" -->
```sh
git clone https://github.com/dsd-toolbox/beets-pysacd beets-pysacd-release
git clone --depth 1 --branch vPYSACD https://github.com/dsd-toolbox/pysacd pysacd-PYSACD
podman run --rm -it --memory 4g --cpus 2 -v ./beets-pysacd-release:/src:ro,Z -v ./pysacd-PYSACD:/pysacd:ro,Z registry.fedoraproject.org/fedora:44 bash
```

Inside the container:

<!-- docs-run: skip="runs inside the container the previous block starts; maintainer release step: PYSACD and VERSION are filled in at release time" -->
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

**On real discs, against PREVIOUS.** The fixtures can't show how matching behaves on real
releases with many editions. `scripts/release_disc_check.py` imports each disc with PREVIOUS and
with VERSION, each run into its own throwaway library with a throwaway HOME and config, with live
MusicBrainz, and compares the albums (one per area), the release and medium matched, the tags, and
the files' count, format, size and checksum. It runs four modes: `beet import -q` and `beet import
-q -A`, each with both areas in one run, and, on hybrid discs, the multichannel area first and the
stereo area in a second run, which checks the duplicate handling in both orders. Use at least the
[minimum set](#5-the-real-disc-corpus), with VERSION from the release commit and the same beets in both:

<!-- docs-run: skip="needs the maintainer's own SACD images; PYSACD and PREVIOUS are filled in at release time" -->
```sh
mkdir -p ~/release-check && cd ~/release-check
git clone https://github.com/dsd-toolbox/beets-pysacd beets-pysacd-release
python3 -m venv prev && prev/bin/pip install beets pysacd==PYSACD beets-pysacd==PREVIOUS
python3 -m venv new && new/bin/pip install beets pysacd==PYSACD ./beets-pysacd-release
systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 -p CPUQuota=400% \
  python3 -I beets-pysacd-release/scripts/release_disc_check.py run --install prev=prev --install new=new \
  --work work --out out DISC1.iso DISC2.iso DISC3.iso DISC4.iso DISC5.iso
```

DISC1 to DISC5 are the maintainer's images. The tool prints one line per disc and mode and writes
`out/diff.tsv` (every difference, with text tags as short hashes) and `out/summary.txt`; it exits
non-zero when anything differs, an import fails, or MusicBrainz was unavailable after two retries
(the pair is then inconclusive). `out/index.tsv`, `out/logs` and `out/runs` hold paths and titles:
keep them private. *Expected:* no difference, or only what VERSION's changelog says changed. Record
counts (discs, modes, differences) in the release issue, never titles, paths or release IDs.
*Validated:* 2026-11-24, 0.2.2 from PyPI against `main` with the fixes for #85, #86 and #90, both on
beets 2.14.1, pysacd 0.5.5 and Python 3.13, on 9 discs (3 hybrid with both areas, 1 multichannel
only, 5 stereo only; DST and plain DSD; 3 without disc text; both discs of a 2-disc set): 24 disc
and mode pairs. Files were identical wherever both imported an area. The one difference is #85: on
the hybrid disc with no MusicBrainz match, 0.2.2 took the second area for a duplicate and skipped it
in all four modes. On the hybrid discs that match, both releases import both areas, as the areas'
tags differ. No multichannel area matched a release, in either version.

## 3. Timed fuzzing

The plugin's own parser of untrusted bytes is the DVD and Blu-ray identifier
(`beetsplug/_sacd_discimage.py`). SACD images are parsed by pysacd and scarletbook-rs, which fuzz
them in their repositories. On the release commit, with Atheris (libFuzzer) from `locks/fuzz`:

| Target | Sanitizer | Time |
|---|---|---|
| `fuzz/fuzz_discimage.py` | Python exceptions (anything but `OSError` is a crash) | 30 min |

<!-- docs-run: skip="30 minutes of fuzzing from a checkout of the release commit" -->
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

<!-- docs-run: skip="maintainer release step: PYSACD and VERSION are filled in at release time, and it starts a Podman container" -->
```sh
git clone --depth 1 --branch vVERSION https://github.com/dsd-toolbox/beets-pysacd beets-pysacd-VERSION
git clone --depth 1 --branch vPYSACD https://github.com/dsd-toolbox/pysacd pysacd-PYSACD
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

<!-- docs-run: skip="runs from a checkout of the release tag; docs-run runs the same test in docs/development.md" -->
```sh
PYSACD_LIVE_MB=1 python -m pytest tests/test_live_musicbrainz.py
```

*Validated:* 2026-11-23 with beets-pysacd 0.2.2 and pysacd 0.5.5 from PyPI (0.2.2's tag predates
`scripts/readme_quickstart.py`, so `main`'s copy ran the same Quick start); the live test on `main`.

## 7. Docs commands

Every command block in README.md and `docs/` either runs or says why it can't. The `docs-run`
workflow runs the blocks marked to run in a fresh Fedora container that holds only the blocks, so
they install the published release from PyPI, and lists every block it skips with the reason
(a sacdfs mount, the maintainer's discs, a GitHub login, an interactive import, or a release step
whose versions are filled in by hand). Run it from the Actions tab (Run workflow) once the release
is on PyPI, and link the run in the sign-off.

*Expected:* every block marked to run passes, and no block is unmarked. For a release that
changes `sacd-migrate`, also run the user guide's `sacdfs verify`, `--catalogue --mount` and
`--mount` commands by hand against a sacdfs container build, as the `tags served by sacdfs main`
job does. *Validated:* VALIDATED-TBD

## 8. Performance

No timing table: an import's time is pysacd's conversion, timed in
[pysacd's plan](https://github.com/dsd-toolbox/pysacd/blob/master/docs/release-test-plan.md). The
plugin's own work per disc (TOC, fingerprint, matching) is small next to it, and
MusicBrainz's rate limit dominates matching.

## 9. Security

**Before the tag.** The security auditor, a reviewer separate from the release's author, reviews the
range from PREVIOUS's tag to the release commit (`git diff vPREVIOUS HEAD`): file deletion
(`remove_iso`), paths, staging, untrusted text, workflows and dependencies. The tag waits for its
`go` on that exact commit; a later commit needs a new `go`.

**After publishing.** The files on PyPI are the GitHub release's assets, and each carries a valid
build provenance attestation:

<!-- docs-run: skip="needs a GitHub login, and VERSION is filled in at release time" -->
```sh
mkdir release-check && cd release-check
gh release download vVERSION -R dsd-toolbox/beets-pysacd -D github
curl -s https://pypi.org/pypi/beets-pysacd/VERSION/json | python3 -I -c 'import json,sys; [print(u["digests"]["sha256"] + "  " + u["filename"]) for u in json.load(sys.stdin)["urls"]]' > pypi.sha256
(cd github && sha256sum -c ../pypi.sha256)
ls github | grep -vc intoto.jsonl && wc -l < pypi.sha256
find github -name '*.whl' -o -name '*.tar.gz' | xargs -I FILE gh attestation verify FILE --repo dsd-toolbox/beets-pysacd
find github -name '*.whl' -o -name '*.tar.gz' | xargs -I FILE gh attestation verify FILE --repo dsd-toolbox/beets-pysacd --bundle FILE.intoto.jsonl
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
| After the release: `docs-audit` workflow run, checklist items fixed | | |

<!-- docs-audit:begin -->
## After the release: run the docs audit

After the release: run the docs audit. Do it once the tag, the packages and the release notes are public, and before the release is announced.

1. Run the `docs-audit` workflow from the Actions tab of the repository (Run workflow). It runs the docs lint, the link check with external URLs and the docs facts check, and fails if any of them does.
2. Open the checklist it prints: every page that mentions a version, a command-line option or a platform, to compare with the release just published. Fix each mismatch in a docs-only change, or write down why it is right.
3. Record the result in the release notes or the release checklist: the workflow run, and how many checklist items were fixed.

Every project also runs this audit each month (the `docs-monthly` workflow in the DSD Toolbox repository), so a missed audit shows up within a month.
<!-- docs-audit:end -->

## See also

- [Releasing](../CONTRIBUTING.md#releasing)
- [Development](development.md): tests and CI
- [pysacd's release test plan](https://github.com/dsd-toolbox/pysacd/blob/master/docs/release-test-plan.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
