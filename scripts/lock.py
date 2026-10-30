#!/usr/bin/env python3
"""Write CI's hash-locked requirement files (#19).

    python3 -I scripts/lock.py          # needs uv (https://docs.astral.sh/uv/)

CI installs every Python dependency with `pip install --require-hashes`, so a replaced or
tampered release on PyPI fails the install instead of running in CI. Two locks, both the
whole dependency closure of the plugin, its `dev` extra and the build tools, for Python 3.11
to 3.14 on Linux, macOS and Windows (a universal resolution, with every file's sha256):

- locks/latest/requirements.txt: the newest beets 2.x, pysacd and everything else;
- locks/oldest/requirements.txt: the same, but beets held at the floor in pyproject.toml;

and locks/fuzz/requirements.txt, Atheris for the fuzz workflow.

Releases younger than two weeks are left out (CLAUDE.md), except the owner's own pysacd, so
the "pysacd release" legs test what users get, and security fixes listed in NOT_HELD_BACK.
Dependabot keeps these files current between runs (beets held at the floor in the oldest one);
rerun this when a new release brings a new dependency, or after changing pyproject.toml.
"""

from __future__ import annotations

import datetime
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# setuptools: the build backend, since CI installs the plugin and pysacd's master branch with
# --no-build-isolation; build and pyproject-hooks: the release workflow's build
BUILD_TOOLS = ["setuptools>=77", "build", "pyproject-hooks"]
# Not held back two weeks: the owner's own pysacd, and security fixes (with the minimum fixed
# version they need, as a constraint). Drop an entry once its fix is older than two weeks.
NOT_HELD_BACK = {
    "pysacd": "",
    "certifi": "==2026.10.18",   # GHSA-6q48-6c7w-9gw2 (critical): the first fixed release
}
# the fuzz workflow (fuzz/fuzz_discimage.py, #22): Atheris, whose wheels start at Python 3.12
FUZZ = ["atheris"]
FUZZ_PYTHON = "3.12"
MIN_AGE = datetime.timedelta(days=14)


def beets_floor() -> str:
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    for dep in deps:
        m = re.match(r"beets\s*>=\s*([0-9.]+)", dep)
        if m:
            return m.group(1)
    sys.exit("no beets>= floor in pyproject.toml")


def main() -> int:
    uv = shutil.which("uv")
    if not uv:
        sys.exit("needs uv: https://docs.astral.sh/uv/")
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    cutoff = (now - MIN_AGE).isoformat().replace("+00:00", "Z")
    fixes = [name + spec for name, spec in NOT_HELD_BACK.items() if spec]
    with tempfile.TemporaryDirectory() as tmp:
        tools = Path(tmp, "build-tools.in")
        tools.write_text("\n".join(BUILD_TOOLS) + "\n")
        fuzz = Path(tmp, "fuzz.in")
        fuzz.write_text("\n".join(FUZZ) + "\n")
        project = ["--extra", "dev", "pyproject.toml", str(tools)]
        # name: (inputs, constraints, oldest Python)
        locks = {"latest": (project, fixes, "3.11"),
                 "oldest": (project, [f"beets=={beets_floor()}.*", *fixes], "3.11"),
                 "fuzz": ([str(fuzz)], fixes, FUZZ_PYTHON)}
        for name, (inputs, constraints, python) in locks.items():
            out = ROOT / "locks" / name / "requirements.txt"
            cmd = [uv, "pip", "compile", "--no-config", "--quiet", "--universal",
                   "--python-version", python, "--generate-hashes",
                   "--exclude-newer", cutoff,
                   *[f"--exclude-newer-package={p}={now.isoformat().replace('+00:00', 'Z')}" for p in NOT_HELD_BACK],
                   "--custom-compile-command", "python3 -I scripts/lock.py",
                   *inputs, "-o", str(out)]
            if constraints:
                c = Path(tmp, f"{name}-constraints.txt")
                c.write_text("\n".join(constraints) + "\n")
                cmd += ["--constraint", str(c)]
            subprocess.run(cmd, cwd=ROOT, check=True)
            # temporary paths in uv's "via" annotations would differ on every run
            text = (out.read_text().replace(str(tools), "build tools").replace(str(fuzz), "fuzz tools")
                    .replace(tmp + "/", ""))
            out.write_text(text)
            print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
