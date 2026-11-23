#!/usr/bin/env python3
"""Check that the version claims in README.md and docs/ match pyproject.toml.

    python3 -I scripts/check_doc_versions.py      # Python 3.11 or later (tomllib)

A short list of known sentences, not a scan for every number: each pattern below is matched
in README.md and every docs/**/*.md, and each match must say what the source of truth says.
Patterns marked required must match somewhere, so a reworded sentence fails here instead of
going unchecked; reword the pattern with it. Exits 1 with one line per mismatch.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def truth() -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    m = re.fullmatch(r">=\s*(3\.\d+)", project["requires-python"])
    if not m:
        sys.exit(f"pyproject.toml: requires-python {project['requires-python']!r} isn't '>=3.N'")
    minors = sorted(int(c.rsplit(".", 1)[1]) for c in project["classifiers"]
                    if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", c))
    deps = {re.match(r"[A-Za-z0-9_.-]+", d).group(0).lower(): d for d in project["dependencies"]}  # type: ignore[union-attr]
    beets = re.fullmatch(r"beets>=(\d+\.\d+),<(\d+)", deps["beets"].replace(" ", ""))
    pysacd = re.fullmatch(r"pysacd>=([\d.]+)", deps["pysacd"].replace(" ", ""))
    if not beets or not pysacd:
        sys.exit(f"pyproject.toml: expected beets>=X.Y,<N and pysacd>=X.Y, got {deps['beets']!r}, {deps['pysacd']!r}")
    return {"version": project["version"], "python_min": m.group(1),
            "classifier_min": f"3.{minors[0]}", "python_max": f"3.{minors[-1]}",
            "beets_min": beets.group(1), "beets_major": str(int(beets.group(2)) - 1), "pysacd_min": pysacd.group(1)}


# (what, pattern, expected value from truth(), required): a pattern's groups, joined with " to ",
# are compared with the expected value.
CHECKS = [
    ("minimum Python", r"Python (3\.\d+) or later", "{python_min}", False),
    ("minimum Python (badge)", r"python-(3\.\d+)%2B", "{python_min}", True),
    ("minimum Python (badge text)", r"Python (3\.\d+)\+", "{python_min}", True),
    ("supported Python range", r"Python (3\.\d+) to (3\.\d+)", "{python_min} to {python_max}", True),
    ("supported beets", r"beets (\d+\.\d+) or later \((\d+)\.x\)", "{beets_min} to {beets_major}", True),
    # the plugin's floor, as the requirements state it; feature notes ("pysacd 0.2.1 or later") are not it
    ("minimum pysacd", r"(?:Requirements:|wheel on PyPI)[^\n]*?pysacd (\d+\.\d+(?:\.\d+)?) or\s+later",
     "{pysacd_min}", True),
    # the requirements table in the install docs
    ("Python (requirements table)", r"(?m)^\| Python \| (3\.\d+) to (3\.\d+) \|", "{python_min} to {python_max}", False),
    ("beets (requirements table)", r"(?m)^\| beets \| (\d+\.\d+) or later \((\d+)\.x\) \|", "{beets_min} to {beets_major}",
     False),
    ("pysacd (requirements table)", r"(?m)^\| pysacd \| (\d+\.\d+(?:\.\d+)?) or later", "{pysacd_min}", False),
    ("pinned plugin release", r"beets-pysacd==(\d+\.\d+\.\d+)", "{version}", False),
]


def docs() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def main() -> int:
    t = truth()
    bad = []
    if t["classifier_min"] != t["python_min"]:
        bad.append(f"pyproject.toml: requires-python is >={t['python_min']} but the oldest Python "
                   f"classifier is {t['classifier_min']}")
    texts = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in docs()}
    for what, pattern, expected, required in CHECKS:
        want = expected.format(**t)
        seen = 0
        for name, text in texts.items():
            for m in re.finditer(pattern, text):
                seen += 1
                got = " to ".join(m.groups())
                if got != want:
                    line = text.count("\n", 0, m.start()) + 1
                    bad.append(f"{name}:{line}: {what} says {got}; pyproject.toml says {want}")
        if required and not seen:
            bad.append(f"{what}: no sentence matches {pattern!r} any more; update "
                       f"scripts/check_doc_versions.py with the new wording")
    for b in bad:
        print(f"::error::{b}")
    if not bad:
        print(f"doc versions match: beets-pysacd {t['version']}, Python {t['python_min']} to {t['python_max']}, "
              f"beets {t['beets_min']} to {t['beets_major']}.x, pysacd {t['pysacd_min']} or later")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
