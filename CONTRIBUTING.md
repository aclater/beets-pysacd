# Contributing to beets-pysacd

Thanks for helping. Bug reports, logs and pull requests are all welcome.

## Reporting a bug

Open an [issue](https://github.com/aclater/beets-pysacd/issues). Include your beets and
pysacd versions (`beet version`, `pip show pysacd`), the command you ran, the output of
the same command with `beet -v`, what you expected and what happened. Describe your
discs and library in general terms; you don't need to share your collection.

**Security problems** go through a private report instead, never a public issue: see
[SECURITY.md](SECURITY.md), which uses GitHub's
[private vulnerability reporting](https://github.com/aclater/beets-pysacd/security/advisories/new).

## Changing code

1. **Start with an issue,** so the change can be discussed first.
2. **Work on a branch and open a pull request** against `main`. The default branch only
   accepts pull requests whose checks pass.
3. **Run the checks before you push:**

   ```sh
   pip install -e '.[dev]'
   ruff check . && mypy beetsplug
   PYSACD_TESTS=/path/to/pysacd/tests pytest -q
   ```

   CI runs the tests on Python 3.11 to 3.14, against the oldest and newest supported
   beets, on Linux, macOS and Windows, with pysacd's release and master branch, plus
   CodeQL, semgrep and a privacy check (see the README, "Development").
4. **Add tests with every change.** Anything that touches matching needs a test with a
   release whose media share recordings, like a real hybrid SACD (`tests/mbfixture.py`).
   Tests never touch a real library or music collection: they use a throwaway beets
   directory and synthetic images.
5. **Update the README in the same pull request,** and add an entry to the
   [changelog](CHANGELOG.md) for anything a user would notice.
6. **Answer the review.** An AI reviewer comments on every pull request; reply to each
   finding (fix it, or say why not).

## Rules

- **Never lose user data.** An ISO is deleted only with `remove_iso: yes`, after every
  area is verified in the library; staging directories are always removed.
- **beets compatibility.** Support every beets release from the floor in
  `pyproject.toml` to the latest 2.x; don't use newer APIs without raising the floor.
- **Untrusted text.** Disc text, volume labels and MusicBrainz data are hostile: print
  them only through pysacd's `safetext`, and never pass them to a shell.
- **Privacy.** No host names, private addresses, local paths, library contents or
  personal details in code, tests, docs or commits.

Contributions are accepted under the project's licence,
[GPL-2.0-or-later](LICENSE).

## Issues: milestones, labels and claiming

Every open issue says which release it is for, how important it is, where it stands, and
what kind of agent should work on it. The issue list then shows what's up without opening
each issue.

- **Milestone:** the release it is planned for (`0.2.0`, `0.3.0`, ...) or `Later`. Umbrella
  issues have no milestone.
- **Priority:**
  - `P1`: must be in its milestone's release;
  - `P2`: planned for it, can slip one release;
  - `P3`: nice to have.
- **Status:**
  - `status: in progress`: claimed and being worked on;
  - `status: in review`: a PR is open;
  - `status: fixed on main`: merged. The issue stays open until the release ships and has
    been verified, then it is closed.
  - `status: needs decision`: waiting on the owner.
- **Type:** `bug`, `enhancement`, `performance`, `documentation`, `plan`, or `tracking`
  (umbrella and design issues that track other work).
- **Model:**
  - `model: opus` for hard work: concurrency, performance, design, unexplained bugs;
  - `model: sonnet` for routine work: well-specified features, tests, docs, CI.

**Claiming.** Before starting on an issue, check that nobody has claimed it. Then:
1. Comment `Claimed by <agent> (<model>)`, and add `status: in progress`.
2. If you stop without a PR, comment that you're releasing it, and remove the label.
3. When you open a PR, switch the label to `status: in review`. The PR says
   `Closes #N` only if it fully resolves the issue, else `Part of #N`.
4. Don't start on an issue that someone else has claimed. Ask on the issue instead.

