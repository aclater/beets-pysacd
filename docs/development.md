[beets-pysacd](../README.md) › [Documentation](README.md) › Development

# Development

How to run the checks and tests locally, and what CI runs on every pull request and every week.

## Tests

From a clone of beets-pysacd, with pysacd's source cloned next to it:

```sh
git clone https://github.com/aclater/pysacd ../pysacd
pip install -e '.[dev]'
ruff check . && mypy beetsplug
pytest -q
```

The tests build synthetic SACD images with pysacd's test generator
(`tests/sacdgen.py` in the pysacd source tree, found through `PYSACD_TESTS`,
default `../pysacd/tests`) and import them into a throwaway beets library. CI checks out the
pysacd tag that matches the installed pysacd; if a test fails locally against pysacd's master
branch, do the same (`git -C ../pysacd checkout v0.5.5` for pysacd 0.5.5).
MusicBrainz is mocked with a hybrid release whose media share recordings, so
the tests need no network. DVD and Blu-ray images for the cataloguing tests
come from `tests/discgen.py`, which writes minimal UDF and ISO 9660 file
systems. `tests/test_tags_export.py` has one test that mounts sacdfs and reads the tags it
serves; it runs when `SACDFS_IMAGE` names a container build of sacdfs main (needs podman and
`/dev/fuse`), and CI builds one.

`tests/test_live_musicbrainz.py` is the exception: it runs the plugin's matching
against a real hybrid SACD release on musicbrainz.org (two requests). It skips
unless `PYSACD_LIVE_MB=1`:

```sh
PYSACD_LIVE_MB=1 pytest tests/test_live_musicbrainz.py
```

## CI

Every pull request runs ruff, mypy and the tests (Python 3.11 to 3.14, plus 3.15 as an early warning; the oldest
and newest beets on Linux, the newest on macOS and Windows; pysacd's release and master branch),
only the expected tests skipping (`tests/expected-skips.json` lists each skip and why; a new,
stopped or changed skip fails the job), CodeQL, semgrep, a privacy check (`scripts/check-private-names.sh`, which fails when it cannot run;
`tests/test_check_private_names.py` tests it), dependency review (fails on high or critical
vulnerabilities) and an AI review. One test leg runs under coverage.py and shows
the report in its job summary, with HTML and XML reports as the `coverage`
artifact; the XML report also goes to [Codecov](https://codecov.io/gh/aclater/beets-pysacd)
for the badge, authenticated with the job's GitHub OIDC token (no stored secret;
pull requests from forks skip the upload). Changes to workflows are linted with
[zizmor](https://docs.zizmor.sh), at the version pinned in `.github/requirements/zizmor.txt`
(`pip install --require-hashes -r .github/requirements/zizmor.txt`, then
`zizmor --offline .github/workflows`), and changes to the README or `docs/` get a link check (lychee, `#fragment`
links to headings included).

Two more checks keep the docs true. The `quickstart` workflow (also weekly) runs the README's
Quick start as written (`scripts/readme_quickstart.py`): it builds the wheel as the release does,
writes the fixture's album as `album.iso` with pysacd's test generator, and runs the README's own
`sh` blocks in order in one shell, as a normal user with a throwaway HOME. The one change: `pip
install beets beets-pysacd` installs beets and the built wheel. beets and pysacd come from PyPI,
as for a user, but MusicBrainz doesn't: from step 2 on, a `sitecustomize.py` answers pysacd's and
beets' MusicBrainz requests from `tests/mbfixture.py`, as the tests do, and a dead proxy fails any
other request. It checks that `sacd-info` shows the album and tracks, that `beet ls -a` lists the
imported album and that `~/Music` holds its DSF files. To see the steps:
`python3 -I scripts/readme_quickstart.py print`. The lint job checks the version claims in README.md
and `docs/` (`scripts/check_doc_versions.py`): the Python badge, "Python 3.N to 3.M", "beets X.Y or
later (N.x)", the pysacd floor and the install requirements table must match `pyproject.toml`; a
reworded sentence fails until the pattern there follows it.

The Linux jobs run in Red Hat-derived containers, pinned by digest: GitHub's hosted Linux runners
are Ubuntu only, so the lint, the Linux test legs, the fuzzing and the live MusicBrainz check run in
Fedora 44 (Python from Fedora's packages), as does the release build, and semgrep, zizmor and the privacy check in UBI 10,
with semgrep and zizmor installed from PyPI by hash (`.github/requirements/`) instead of their
vendors' images. The `sacdfs main` tags test stays on the runner, since it builds sacdfs's own
image (UBI 10 and Fedora based) with the runner's Podman.

Changes to the DVD/Blu-ray identifier (`beetsplug/_sacd_discimage.py`) or the
harness are fuzzed for 150 seconds with [Atheris](https://github.com/google/atheris)
(`fuzz/fuzz_discimage.py`, seeded from `tests/discgen.py`'s images; its docstring shows
how to run it locally). A crashing input is uploaded as the `fuzz-crashes` artifact; once
fixed, it goes into `fuzz/regressions/`, which the tests replay.

Weekly: CodeQL, OpenSSF Scorecard (also on every push to `main`; results published for
the badge and shown under code scanning), the live MusicBrainz test, the link
check, the test matrix, to catch new beets and pysacd releases, and 20 minutes of
fuzzing.

CI installs every Python dependency hash-checked (`pip install --require-hashes`),
from two lock files written by `python3 -I scripts/lock.py` (needs
[uv](https://docs.astral.sh/uv/)): `locks/latest/requirements.txt` with the newest
beets and `locks/oldest/requirements.txt` with beets held at the floor in
`pyproject.toml` (plus `locks/fuzz/requirements.txt`, Atheris). Both cover Python 3.11 to 3.14 on Linux (3.15 too, see [install](install/README.md)), macOS and Windows, and
leave out releases younger than two weeks, except pysacd's and the security fixes listed in
the script. The plugin, and pysacd's master branch on that leg, are installed on
top with `--no-deps`, so nothing unhashed is downloaded. Dependabot keeps both locks
current (beets stays on the floor in the oldest); when a new release brings a new
dependency, the locked install fails on Dependabot's PR, and rerunning
`scripts/lock.py` there fixes it. Rerun it, too, after changing dependencies in
`pyproject.toml`, and at each pysacd release: every run moves pysacd to its newest release, so
the "pysacd release" legs test what users install. For local work, `pip install -e '.[dev]'` still works.

## See also

- [Contributing](../CONTRIBUTING.md): reporting bugs and proposing changes
- [Security policy](../SECURITY.md): reporting a vulnerability privately
- [Changelog](../CHANGELOG.md): what changed in each release
- [Releases by major version](https://github.com/aclater/dsd-toolbox/blob/main/RELEASES.md), across the DSD Toolbox projects

Part of the [DSD Toolbox](https://github.com/aclater/dsd-toolbox).
