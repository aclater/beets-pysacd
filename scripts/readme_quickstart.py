#!/usr/bin/env python3
"""Run the README's "Quick start" as written, against a wheel built from this checkout.

    python3 -I scripts/readme_quickstart.py print
    python3 -I scripts/readme_quickstart.py make-disc --pysacd-tests DIR DIR/album.iso
    python3 -I scripts/readme_quickstart.py run --wheel dist/beets_pysacd-X.whl --workdir DIR --home HOME

The commands come from the ```sh blocks under "## Quick start" in README.md, so a change to
the README is what CI runs: nothing here repeats them. They run in order in one bash session in
DIR (`set -eo pipefail`), so the venv step 1 activates stays active for the later steps, with
HOME set to the throwaway HOME (the config heredoc and `~/Music` land there).

One line is swapped, and only that one: `pip install beets beets-pysacd` installs the plugin from
PyPI, so it becomes `pip install beets <the built wheel>`. If the README no longer has exactly
that line, the run fails. beets and pysacd still come from PyPI, as for a user.

No MusicBrainz traffic: after step 1 (which needs PyPI), every later step runs with a
sitecustomize.py that answers pysacd's and beets' MusicBrainz requests from tests/mbfixture.py,
as the test suite does, and with HTTP(S)_PROXY pointing at a closed port, so a request the fixture
doesn't answer fails instead of reaching the network. `beet sacd-import` gets "A" (apply) on
stdin, in case the importer asks.

Checks: step 3 (`sacd-info`) prints the album and every track title; after the import, each
`beet ...` command the section's prose names (`beet ls -a`) prints the album, and `~/Music` holds
one .dsf per track. `make-disc` writes the README's `album.iso` with pysacd's test generator
(tests/sacdgen.py from a pysacd checkout): the fixture's album, stereo and multichannel.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SECTION = "Quick start"
# README line -> replacement; each must match exactly one command line
SWAPS = {"pip install beets beets-pysacd": "pip install beets {wheel}"}
MARK = "@@readme-quickstart-step"
FRAMES = 75     # per track: 1 s, as the fixture's track lengths

sys.path.insert(0, str(ROOT / "tests"))
import mbfixture  # noqa: E402

SITECUSTOMIZE = f"""\
# Written by scripts/readme_quickstart.py: MusicBrainz answered from tests/mbfixture.py
import sys
sys.path.insert(0, {str(ROOT / "tests")!r})
import mbfixture
import pysacd.musicbrainz
import beetsplug._utils.requests
pysacd.musicbrainz._json = mbfixture.pysacd_json
beetsplug._utils.requests.RequestHandler.get_json = mbfixture.beets_get_json
"""
DEAD_PROXY = "http://127.0.0.1:9"


def section(text: str, title: str = SECTION) -> list[str]:
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.fullmatch(rf"##\s+{re.escape(title)}\s*", ln)), None)
    if start is None:
        sys.exit(f"README.md has no '## {title}' section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start + 1:end]


def steps(text: str) -> tuple[list[list[str]], list[str]]:
    """The section's shell code blocks, and the `beet ...` commands its prose names."""
    blocks: list[list[str]] = []
    prose: list[str] = []
    lines = section(text)
    i = 0
    while i < len(lines):
        m = re.match(r"(\s*)```(\w*)\s*$", lines[i])
        if not m:
            prose.append(lines[i])
            i += 1
            continue
        indent, lang = len(m.group(1)), m.group(2)
        body = []
        i += 1
        while i < len(lines) and not re.match(r"\s*```\s*$", lines[i]):
            body.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i])
            i += 1
        i += 1
        if lang not in ("sh", "bash", "shell", "console"):
            sys.exit(f"Quick start: a ```{lang} block; this tool runs only sh blocks")
        blocks.append(body)
    if not blocks:
        sys.exit("README.md's Quick start has no ```sh blocks")
    named = re.findall(r"`(beet [^`]+)`", "\n".join(prose))
    return blocks, [c for c in named if not any(c in ln for b in blocks for ln in b)]


def swapped(blocks: list[list[str]], wheel: str) -> list[list[str]]:
    used = dict.fromkeys(SWAPS, 0)
    for b in blocks:
        for n, ln in enumerate(b):
            if ln.strip() in SWAPS:
                used[ln.strip()] += 1
                b[n] = ln.replace(ln.strip(), SWAPS[ln.strip()].format(wheel=wheel))
    wrong = [k for k, v in used.items() if v != 1]
    if wrong:
        sys.exit(f"README.md's Quick start must have each of these lines exactly once: {wrong}; "
                 f"update SWAPS in {Path(__file__).name} to match the README")
    return blocks


def cmd_print(_: argparse.Namespace) -> int:
    blocks, named = steps(README.read_text(encoding="utf-8"))
    for n, b in enumerate(blocks, 1):
        print(f"# step {n}")
        print("\n".join(b))
    print(f"# checks named in the prose: {named}")
    return 0


def cmd_make_disc(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(a.pysacd_tests).resolve()))
    import sacdgen
    frames2 = [bytes([0x69]) * (4704 * 2)] * (FRAMES * 3)
    frames6 = [bytes([0x69]) * (4704 * 6)] * (FRAMES * 3)
    sacdgen.build_iso(a.iso, [sacdgen.AreaSpec(2, frames2, [FRAMES] * 3, dst=False, titles=mbfixture.TITLES),
                              sacdgen.AreaSpec(6, frames6, [FRAMES] * 3, dst=False, titles=mbfixture.TITLES)],
                      info=sacdgen.DiscInfo(title=mbfixture.ALBUM, artist="Test Artist", album_catalog="PYSACD-TEST"))
    print(f"{a.iso}: {mbfixture.ALBUM!r}, stereo and multichannel, {len(mbfixture.TITLES)} tracks")
    return 0


def run(script: list[str], cwd: Path) -> tuple[int, str]:
    print("\n".join(script), "\n----", flush=True)
    proc = subprocess.Popen(["bash", "--noprofile", "--norc", "-c", "\n".join(script)], cwd=cwd,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    out = []
    for ln in proc.stdout:
        sys.stdout.write(ln)
        out.append(ln)
    return proc.wait(), "".join(out)


def cmd_run(a: argparse.Namespace) -> int:
    wheel = Path(a.wheel).resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        sys.exit(f"not a wheel: {wheel}")
    work, home = Path(a.workdir).resolve(), Path(a.home).resolve()
    blocks, named = steps(README.read_text(encoding="utf-8"))
    blocks = swapped(blocks, str(wheel))
    offline = Path(tempfile.mkdtemp(prefix="quickstart-mb-"))
    (offline / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    env = [f"export HOME={home}", "unset XDG_CONFIG_HOME BEETSDIR"]
    no_mb = [f"export PYTHONPATH={offline}", f"export HTTP_PROXY={DEAD_PROXY} HTTPS_PROXY={DEAD_PROXY}",
             f"export http_proxy={DEAD_PROXY} https_proxy={DEAD_PROXY}", "unset NO_PROXY no_proxy"]
    script = ["set -eo pipefail", *env]
    for n, b in enumerate(blocks, 1):
        script += [f"echo '{MARK} {n}'", *(no_mb if n == 2 else []),
                   *[f"{ln} <<< A" if re.fullmatch(r"\s*beet sacd-import\b.*", ln) else ln for ln in b]]
    for c in named:
        script += [f"echo '{MARK} {c}'", c]
    rc, out = run(script, work)
    if rc != 0:
        print(f"::error::the Quick start failed (exit {rc})")
        return 1
    parts = re.split(rf"^{re.escape(MARK)} (.+)\n", out, flags=re.MULTILINE)
    output = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    bad = []
    info = next((str(n) for n, b in enumerate(blocks, 1) if any("sacd-info" in ln for ln in b)), None)
    if info is None:
        bad.append("no Quick start step runs `beet sacd-info`")
    else:
        bad += [f"step {info} (sacd-info): {want!r} isn't in the output"
                for want in [mbfixture.ALBUM, *mbfixture.TITLES] if want not in output[info]]
    if not named:
        bad.append("the Quick start's prose no longer names a `beet ...` command that lists the album")
    for c in named:
        if mbfixture.ALBUM not in output.get(c, ""):
            bad.append(f"`{c}` doesn't list the imported album {mbfixture.ALBUM!r}")
    dsf = sorted((home / "Music").rglob("*.dsf"))
    if len(dsf) != len(mbfixture.TITLES):
        bad.append(f"~/Music should hold {len(mbfixture.TITLES)} .dsf files; it holds {[p.name for p in dsf]}")
    for msg in bad:
        print(f"::error::{msg}")
    if not bad:
        print(f"README Quick start: {len(blocks)} steps ran as written, MusicBrainz from the fixture; "
              f"{len(dsf)} tracks imported into ~/Music")
    return 1 if bad else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("print", help="show the extracted steps").set_defaults(fn=cmd_print)
    d = sub.add_parser("make-disc", help="write the fixture's album as an SACD image")
    d.add_argument("--pysacd-tests", required=True, help="a pysacd checkout's tests/ (for sacdgen.py)")
    d.add_argument("iso", type=Path)
    d.set_defaults(fn=cmd_make_disc)
    r = sub.add_parser("run", help="run the steps in WORKDIR with the wheel")
    r.add_argument("--wheel", required=True)
    r.add_argument("--workdir", required=True)
    r.add_argument("--home", required=True, help="a throwaway HOME")
    r.set_defaults(fn=cmd_run)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
