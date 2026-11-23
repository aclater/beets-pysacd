#!/usr/bin/env python3
"""Release disc check: import real SACD images with two installs of the plugin and compare (#89).

Each image is imported with each install (a virtual environment holding beets, pysacd and
beets-pysacd) into its own throwaway beets library, with a throwaway HOME and config, in each
mode below. The albums, MusicBrainz release and medium, tags and files are then compared, with
the first install as the baseline.

    matched            beet import -q, both areas in one run (stereo first)
    matched-mc-first   beet import -q, the multichannel area, then the stereo area in a second run
    asis               beet import -q -A, both areas in one run (stereo first)
    asis-mc-first      beet import -q -A, multichannel, then stereo in a second run

The mc-first modes run only on discs with both areas. Quiet imports take a strong match and,
with the default `--quiet-fallback asis`, import anything else as is, so a disc without a match
still makes albums. Images are only read (`remove_iso` stays off).

    release_disc_check.py run --install prev=VENV1 --install new=VENV2 --work DIR --out DIR ISO...
    release_disc_check.py compare --out DIR

`run` writes one JSON record per disc, mode and install to OUT/runs, the beets output to
OUT/logs, the image paths to OUT/index.tsv, then compares. `compare` writes OUT/diff.tsv and
OUT/summary.txt. Discs are named by an ID made from their path; text tags (titles, artists, album
names, genres) appear in the TSV only as short hashes. index.tsv, the logs and the JSON records
hold paths and titles: keep them private.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

MODES: dict[str, list[tuple[bool, str]]] = {     # mode: [(as-is, areas) for each beet import run]
    "matched": [(False, "both")],
    "matched-mc-first": [(False, "multichannel"), (False, "stereo")],
    "asis": [(True, "both")],
    "asis-mc-first": [(True, "multichannel"), (True, "stereo")],
}
HYBRID_ONLY = {"matched-mc-first", "asis-mc-first"}

ALBUM_FIELDS = ("albumartist", "album", "mb_albumid", "mb_releasegroupid", "mb_albumartistid", "albumtype",
                "albumstatus", "genre", "year", "original_year", "label", "catalognum", "barcode", "country",
                "media", "disctotal")
ITEM_FIELDS = ("title", "artist", "albumartist", "album", "track", "tracktotal", "disc", "disctotal", "media",
               "mb_trackid", "mb_releasetrackid", "mb_albumid", "mb_artistid", "mb_albumartistid", "genre",
               "year", "format", "channels", "samplerate", "bitdepth", "length", "isrc")
# String fields shown as they are; every other string is hashed (titles, names, genres, labels)
PLAIN = re.compile(r"^(mb_\w+|sacd_area|sacd_iso_sha|format|media|albumtype|albumstatus|country|ext|sha256)$")
LOG_PATTERNS = {
    "area_skipped": re.compile(r"area already imported, skipped", re.I),
    "duplicate": re.compile(r"duplicate|already in the library", re.I),
    "skipping": re.compile(r"\bskipping\b", re.I),
    "error": re.compile(r"\berror\b|traceback", re.I),
    "mb_unavailable": re.compile(r"HTTP 50[234]|50[234] error|MusicBrainz lookup failed|Error searching MusicBrainz",
                                 re.I),
}
SAFE_ENV = ("PATH", "LANG", "LC_ALL", "TZ")


def disc_id(iso: Path) -> str:
    return hashlib.sha256(os.fsencode(iso.resolve())).hexdigest()[:12]


def shown(field: str, value) -> str:
    """A value for the TSV: numbers and IDs as they are, other text as a short hash."""
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, str) and not PLAIN.match(field):
        return "h:" + hashlib.sha256(value.encode()).hexdigest()[:8]
    return str(value)


# ------------------------------------------------------------------ running

def areas_of(python: Path, iso: Path) -> tuple[bool, bool]:
    """(has stereo, has multichannel), read with the install's own pysacd."""
    code = ("import sys\nfrom pysacd.toc import read_toc\nd = read_toc(sys.argv[1])\n"
            "print(int(d.stereo is not None), int(d.multichannel is not None))")
    out = subprocess.run([str(python), "-I", "-c", code, str(iso)], check=True, capture_output=True, text=True)
    s, m = out.stdout.split()
    return s == "1", m == "1"


def write_config(run: Path, areas: str, threads: int, fallback: str) -> Path:
    cfg = {
        "directory": str(run / "music"),
        "library": str(run / "library.db"),
        "plugins": ["musicbrainz", "sacd"],
        "import": {"write": True, "quiet_fallback": fallback, "log": str(run / "import.log")},
        "musicbrainz": {"ratelimit": 1, "ratelimit_interval": 1.0},
        "sacd": {"areas": areas, "threads": threads, "musicbrainz": True, "remove_iso": False},
    }
    path = run / "config.yaml"
    path.write_text(json.dumps(cfg, indent=1))       # JSON is YAML
    return path


def run_one(venv: Path, iso: Path, mode: str, run: Path, threads: int, fallback: str,
            logs: Path | None = None) -> dict:
    if run.exists():
        shutil.rmtree(run)
    home = run / "home"
    for d in (home / ".config", home / ".cache", run / "tmp", run / "music"):
        d.mkdir(parents=True)
    env = {k: os.environ[k] for k in SAFE_ENV if k in os.environ}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_CACHE_HOME=str(home / ".cache"),
               BEETSDIR=str(home / "beets"), TMPDIR=str(run / "tmp"))
    steps: list[dict] = []
    for asis, areas in MODES[mode]:
        cfg = write_config(run, areas, threads, fallback)
        cmd = [str(venv / "bin" / "beet"), "-c", str(cfg), "-v", "import", "-q", *(["-A"] if asis else []), str(iso)]
        t0 = time.monotonic()
        p = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           errors="replace", cwd=run)
        log = p.stdout + p.stderr
        (run / f"step{len(steps) + 1}.log").write_text(log)
        if logs is not None:
            (logs / f"{run.parent.parent.name}-{mode}-{run.name}-step{len(steps) + 1}.log").write_text(log)
        steps.append({"asis": asis, "areas": areas, "rc": p.returncode, "seconds": round(time.monotonic() - t0, 1),
                      "log": {k: len(r.findall(log)) for k, r in LOG_PATTERNS.items()}})
    rec = {"mode": mode, "steps": steps, **collect(run)}
    return rec


def collect(run: Path) -> dict:
    """The library's albums with their items and files, and anything else left in the music folder."""
    music = run / "music"
    db = run / "library.db"
    albums: list[dict] = []
    owned: set[Path] = set()
    if db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        flex: dict[tuple[str, int], dict] = {}
        for table, kind in (("album_attributes", "album"), ("item_attributes", "item")):
            for r in con.execute(f"SELECT entity_id, key, value FROM {table}"):
                flex.setdefault((kind, r["entity_id"]), {})[r["key"]] = r["value"]
        for a in map(dict, con.execute("SELECT * FROM albums ORDER BY id")):
            af = flex.get(("album", a["id"]), {})
            alb = {k: a[k] for k in ALBUM_FIELDS if k in a}
            alb.update({k: v for k, v in af.items() if k.startswith("sacd_")})
            items = []
            rows = con.execute("SELECT * FROM items WHERE album_id = ? ORDER BY disc, track", (a["id"],))
            for i in map(dict, rows):
                it = {k: i[k] for k in ITEM_FIELDS if k in i}
                it.update({k: v for k, v in flex.get(("item", i["id"]), {}).items() if k.startswith("sacd_")})
                path = Path(os.fsdecode(i["path"]))
                owned.add(path)
                it.update(file_facts(path))
                it["path"] = os.fsdecode(path.relative_to(music)) if path.is_relative_to(music) else str(path)
                items.append(it)
            alb["items"] = items
            albums.append(alb)
        singletons = con.execute("SELECT COUNT(*) FROM items WHERE album_id IS NULL").fetchone()[0]
        con.close()
    else:
        singletons = 0
    stray = [p for p in music.rglob("*") if p.is_file() and p not in owned] if music.exists() else []
    staging = [p for p in music.rglob(".sacd-staging-*")] if music.exists() else []
    return {"albums": albums, "singletons": singletons, "stray_files": len(stray), "staging_left": len(staging)}


def file_facts(path: Path) -> dict:
    try:
        st = path.stat()
    except OSError:
        return {"exists": False}
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return {"exists": True, "size": st.st_size, "ext": path.suffix.lower().lstrip("."), "sha256": h.hexdigest()}


# ------------------------------------------------------------------ comparing

def album_key(alb: dict) -> str:
    area = alb.get("sacd_area")
    if not area:
        ch = {it.get("channels") for it in alb["items"]}
        area = "stereo" if ch == {2} else "multichannel" if ch and all((c or 0) > 2 for c in ch) else "unknown"
    return area


def keyed_albums(rec: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for alb in rec["albums"]:
        key = album_key(alb)
        n = 2
        while key in out:
            key = f"{album_key(alb)}#{n}"
            n += 1
        out[key] = alb
    return out


def compare_runs(a: dict, b: dict) -> list[tuple[str, str, str, str]]:
    """Differences between two records of one disc and mode: (scope, field, a, b)."""
    rows: list[tuple[str, str, str, str]] = []

    def cmp(scope: str, field: str, x, y) -> None:
        if x != y:
            rows.append((scope, field, shown(field, x), shown(field, y)))

    for n, (sa, sb) in enumerate(zip(a["steps"], b["steps"], strict=True), 1):
        cmp(f"step{n}", "rc", sa["rc"], sb["rc"])
        for k in LOG_PATTERNS:
            cmp(f"step{n}", f"log_{k}", sa["log"].get(k, 0), sb["log"].get(k, 0))
    cmp("run", "albums", len(a["albums"]), len(b["albums"]))
    for k in ("singletons", "stray_files", "staging_left"):
        cmp("run", k, a[k], b[k])
    ka, kb = keyed_albums(a), keyed_albums(b)
    for key in sorted(set(ka) | set(kb)):
        if key not in ka or key not in kb:
            cmp(f"album:{key}", "present", key in ka, key in kb)
            continue
        x, y = ka[key], kb[key]
        for f in sorted((set(x) | set(y)) - {"items"}):
            cmp(f"album:{key}", f, x.get(f), y.get(f))
        cmp(f"album:{key}", "items", len(x["items"]), len(y["items"]))
        for i, (ix, iy) in enumerate(zip(x["items"], y["items"], strict=False), 1):
            for f in sorted((set(ix) | set(iy)) - {"path"}):
                vx, vy = ix.get(f), iy.get(f)
                if f == "length" and vx is not None and vy is not None and abs(vx - vy) < 0.001:
                    continue
                cmp(f"track:{key}:{i:02d}", f, vx, vy)
            cmp(f"track:{key}:{i:02d}", "path_hash", hashlib.sha256(ix.get("path", "").encode()).hexdigest()[:8],
                hashlib.sha256(iy.get("path", "").encode()).hexdigest()[:8])
    return rows


def run_totals(rec: dict) -> dict:
    items = [it for alb in rec["albums"] for it in alb["items"]]
    return {"albums": len(rec["albums"]), "items": len(items), "bytes": sum(it.get("size", 0) for it in items),
            "formats": dict(Counter(it.get("ext", "?") for it in items)),
            "matched": sum(1 for alb in rec["albums"] if alb.get("mb_albumid"))}


def compare(out: Path) -> int:
    recs: dict[tuple[str, str], dict[str, dict]] = {}
    installs: list[str] = []
    for p in sorted((out / "runs").glob("*.json")):
        r = json.loads(p.read_text())
        recs.setdefault((r["disc"], r["mode"]), {})[r["install"]] = r
        if r["install"] not in installs:
            installs.append(r["install"])
    order = json.loads((out / "installs.json").read_text()) if (out / "installs.json").exists() else installs
    if len(order) != 2:
        raise SystemExit(f"compare needs exactly two installs, found {order}")
    base, new = order
    lines = ["disc\tmode\tscope\tfield\t" + base + "\t" + new]
    per_field: Counter[str] = Counter()
    summary = [f"Release disc check: {base} (baseline) against {new}", ""]
    differing = failures = inconclusive = 0
    for (disc, mode), by in sorted(recs.items()):
        if base not in by or new not in by:
            summary.append(f"{disc} {mode}: missing a run ({', '.join(sorted(by))} only)")
            differing += 1
            continue
        rows = compare_runs(by[base], by[new])
        ta, tb = run_totals(by[base]), run_totals(by[new])
        head = (f"{disc} {mode}: albums {ta['albums']}/{tb['albums']}, tracks {ta['items']}/{tb['items']}, "
                f"matched {ta['matched']}/{tb['matched']}")
        failed = sorted({s["rc"] for r in by.values() for s in r["steps"]} - {0})
        if failed:
            failures += 1
            head += f", FAILED (exit {failed})"
        if any(s["log"].get("mb_unavailable") for r in by.values() for s in r["steps"]):
            inconclusive += 1
            head += ", INCONCLUSIVE (MusicBrainz unavailable)"
        if rows:
            differing += 1
            fields = Counter(f"{s.split(':')[0]}.{f}" for s, f, _, _ in rows)
            per_field.update(fields)
            summary.append(head + ": " + ", ".join(f"{k} x{v}" for k, v in sorted(fields.items())))
        else:
            summary.append(head + ": identical")
        lines += [f"{disc}\t{mode}\t{s}\t{f}\t{x}\t{y}" for s, f, x, y in rows]
    summary += ["", f"{len(recs)} disc/mode pairs, {differing} with differences, {failures} with a failed import, "
                f"{inconclusive} inconclusive"]
    if per_field:
        summary.append("Differences by field: " + ", ".join(f"{k} x{v}" for k, v in sorted(per_field.items())))
    (out / "diff.tsv").write_text("\n".join(lines) + "\n")
    (out / "summary.txt").write_text("\n".join(summary) + "\n")
    print("\n".join(summary))
    return 1 if differing or failures or inconclusive else 0


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="import every image with both installs, then compare")
    r.add_argument("--install", action="append", required=True, metavar="NAME=VENV",
                   help="an install to test, twice: the baseline first")
    r.add_argument("--work", required=True, type=Path, help="scratch directory for the throwaway libraries")
    r.add_argument("--out", required=True, type=Path, help="results directory")
    r.add_argument("--modes", default=",".join(MODES), help="comma-separated modes (default: all)")
    r.add_argument("--threads", type=int, default=4, help="conversion threads (sacd.threads)")
    r.add_argument("--quiet-fallback", default="asis", choices=("asis", "skip"),
                   help="what beet import -q does without a strong match (default: asis)")
    r.add_argument("--retries", type=int, default=2,
                   help="run a disc and mode again with both installs when MusicBrainz was unavailable (default: 2)")
    r.add_argument("--retry-wait", type=float, default=120, help="seconds to wait before a retry (default: 120)")
    r.add_argument("--keep", action="store_true", help="keep the throwaway libraries and files")
    r.add_argument("isos", nargs="+", type=Path)
    c = sub.add_parser("compare", help="compare the records in OUT/runs")
    c.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        return compare(args.out)
    args.work, args.out = args.work.resolve(), args.out.resolve()

    installs = []
    for spec in args.install:
        name, sep, venv = spec.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            ap.error(f"--install wants NAME=VENV, got {spec!r}")
        installs.append((name, Path(venv).resolve()))
    if len(installs) != 2:
        ap.error("give exactly two --install")
    modes = args.modes.split(",")
    if unknown := [m for m in modes if m not in MODES]:
        ap.error(f"unknown modes: {unknown}")
    (args.out / "runs").mkdir(parents=True, exist_ok=True)
    (args.out / "logs").mkdir(exist_ok=True)
    (args.out / "installs.json").write_text(json.dumps([n for n, _ in installs]))
    index_file = args.out / "index.tsv"     # several runs can share one OUT
    index = index_file.read_text().splitlines() if index_file.exists() else []
    for iso in args.isos:
        iso = iso.resolve()
        did = disc_id(iso)
        if f"{did}\t{iso}" not in index:
            index.append(f"{did}\t{iso}")
        stereo, multi = areas_of(installs[0][1] / "bin" / "python", iso)
        for mode in modes:
            if mode in HYBRID_ONLY and not (stereo and multi):
                continue
            for attempt in range(1 + args.retries):
                unavailable = False
                for name, venv in installs:      # interleaved, so live MusicBrainz is the same for both
                    run = args.work / did / mode / name
                    rec = run_one(venv, iso, mode, run, args.threads, args.quiet_fallback, args.out / "logs")
                    rec.update(disc=did, install=name, attempt=attempt + 1,
                               areas=[k for k, v in (("stereo", stereo), ("multichannel", multi)) if v])
                    (args.out / "runs" / f"{did}-{mode}-{name}.json").write_text(json.dumps(rec, indent=1))
                    unavailable |= any(s["log"]["mb_unavailable"] for s in rec["steps"])
                    print(f"{did} {mode} {name}: rc {[s['rc'] for s in rec['steps']]}, {len(rec['albums'])} "
                          f"albums, {sum(s['seconds'] for s in rec['steps']):.0f} s"
                          + (", MusicBrainz unavailable" if unavailable else ""), flush=True)
                    if not args.keep:
                        shutil.rmtree(run)
                if not unavailable:
                    break
                if attempt < args.retries:
                    time.sleep(args.retry_wait)     # a MusicBrainz error makes the pair inconclusive: run both again
        index_file.write_text("\n".join(index) + "\n")
    return compare(args.out)


if __name__ == "__main__":
    sys.exit(main())
