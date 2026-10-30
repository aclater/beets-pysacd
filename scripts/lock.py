#!/usr/bin/env python3
"""Write CI's hash-locked requirement files (#19).

    python3 -I scripts/lock.py          # needs uv (https://docs.astral.sh/uv/)

CI installs every Python dependency with `pip install --require-hashes`, so a replaced or
tampered release on PyPI fails the install instead of running in CI. Two locks, both the
whole dependency closure of the plugin, its `dev` extra and the build tools, for Python 3.11
to 3.14 on Linux, macOS and Windows (a universal resolution, with every file's sha256):

- locks/latest/requirements.txt: the newest beets 2.x, pysacd and everything else;
- locks/oldest/requirements.txt: the same, but beets held at the floor in pyproject.toml.

Releases younger than two weeks are left out (CLAUDE.md), except the owner's own pysacd, so
the "pysacd release" legs test what users get. Dependabot keeps both files current between
runs (beets held at the floor in the oldest one); rerun this when a new release brings a new
dependency, or after changing pyproject.toml.
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
OWN = ["pysacd"]
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
    locks = {"latest": [], "oldest": [f"beets=={beets_floor()}.*"]}
    with tempfile.TemporaryDirectory() as tmp:
        tools = Path(tmp, "build-tools.in")
        tools.write_text("\n".join(BUILD_TOOLS) + "\n")
        for name, constraints in locks.items():
            out = ROOT / "locks" / name / "requirements.txt"
            cmd = [uv, "pip", "compile", "--no-config", "--quiet", "--universal",
                   "--python-version", "3.11", "--generate-hashes",
                   "--exclude-newer", cutoff,
                   *[f"--exclude-newer-package={p}={now.isoformat().replace('+00:00', 'Z')}" for p in OWN],
                   "--custom-compile-command", "python3 -I scripts/lock.py",
                   "--extra", "dev", "pyproject.toml", str(tools), "-o", str(out)]
            if constraints:
                c = Path(tmp, f"{name}-constraints.txt")
                c.write_text("\n".join(constraints) + "\n")
                cmd += ["--constraint", str(c)]
            subprocess.run(cmd, cwd=ROOT, check=True)
            # temporary paths in uv's "via" annotations would differ on every run
            text = out.read_text().replace(str(tools), "build tools").replace(tmp + "/", "")
            out.write_text(text)
            print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
