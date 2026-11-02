"""beets plugin: import SACD ISO images through pysacd.

beets can't tag an .iso, so each selected area of a disc (stereo, multichannel) is converted by
pysacd to DSF or FLAC in a staging directory, and that directory is imported as an album of its
own. pysacd's MusicBrainz match (barcode, catalogue number, ISRCs) is written into the files, so
beets looks up that release by ID.

Hybrid SACDs need one more step. MusicBrainz lists the CD layer and each SACD layer as media of
one release with the same recordings, and beets puts the tracks of every medium into one
candidate. It then maps the SACD files to the CD layer (medium 1), and sets album `media` to
"Media". This plugin pins each area to its own medium: candidates for that release are cut
down to the medium before matching, and a guard fixes a chosen match that still points
elsewhere. See README.md, "Hybrid SACDs".

Commands: `beet sacd-import <iso|dir>...` and `beet sacd-info <iso|dir>...`. Plain `beet import`
converts the ISOs it finds first (config `auto`). Imported albums carry the flexible attributes
`sacd_iso_sha` (a fingerprint of the disc's TOCs) and `sacd_area`, so an ISO already imported
is skipped.

DVD-Audio, DVD-Video and Blu-ray images are identified by _sacd_discimage and catalogued (in
`sacd-info` and in the import log), never converted.
"""

from __future__ import annotations

import contextvars
import hashlib
import inspect
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from beets import config, ui
from beets.plugins import BeetsPlugin
from beets.ui.commands.import_ import import_files
from beets.util import MoveOperation, bytestring_path, displayable_path, syspath

from beetsplug import _sacd_tags
from beetsplug._sacd_discimage import identify
from beetsplug._sacd_migrate import durations_match, parse_verify_report, sacdfs_path

AREAS = ("stereo", "multichannel")
FORMATS = ("dsf", "flac")
# match.preferred.media pattern for the plugin's own lookups: any SACD medium ("SACD",
# "SHM-SACD", "Hybrid SACD (...)"); beets anchors each pattern at the start of the format
SACD_MEDIA = ".*SACD"

# The task whose candidates are being looked up, if it is one of ours (set around
# task.lookup_candidates; albuminfo_received is sent in the same thread)
_current: contextvars.ContextVar[Pin | None] = contextvars.ContextVar("sacd_pin", default=None)


@dataclass
class Pin:
    """One converted area: where it was staged, and which MusicBrainz medium it is."""
    iso: Path
    fingerprint: str
    area: str                       # "stereo" | "multichannel"
    tracks: int
    staging: Path                   # the directory beets imports
    release_id: str | None = None   # pysacd's match, if any
    medium: int | None = None       # its position in the release
    media: str | None = None        # its format, e.g. "Hybrid SACD (SACD layer, 2 channels)"


@dataclass
class Job:
    """One ISO: its areas, and whether every one of them made it into the library."""
    iso: Path
    pins: list[Pin] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)     # areas already in the library


def fingerprint(img, disc) -> str:
    """sha256 of the master TOC, every area TOC and the image size: the disc's identity, without
    reading gigabytes of audio."""
    from pysacd.toc import MASTER_TOC_LEN, START_OF_MASTER_TOC
    h = hashlib.sha256(img.read_sectors(START_OF_MASTER_TOC, MASTER_TOC_LEN))
    for a in disc.areas:
        h.update(img.read_sectors(a.toc_start, a.toc_size))
    h.update(str(img.total_sectors).encode())
    return h.hexdigest()


def pysacd_has_pauses() -> bool:
    """Whether the installed pysacd's convert can include pauses (pysacd 0.2.1)."""
    from dataclasses import fields

    from pysacd.convert import Options
    return any(f.name == "pauses" for f in fields(Options))


def is_iso(path: str | os.PathLike) -> bool:
    return str(path).lower().endswith(".iso") and os.path.isfile(path)


def find_isos(path: str | os.PathLike) -> list[Path]:
    p = Path(path)
    if is_iso(p):
        return [p]
    if p.is_dir():
        return sorted(q for q in p.rglob("*") if is_iso(q))
    return []


def describe_other(path: str | os.PathLike) -> str:
    """A catalogue line for an image that isn't an SACD: DVD-Audio, DVD-Video or Blu-ray, with
    its volume label (untrusted: callers print it through safetext). These are identified only,
    never converted."""
    try:
        d = identify(path)
    except OSError as e:
        return f"  not an SACD image, and not readable ({e})"
    if d.kind == "unknown":
        return "  not an SACD, DVD or Blu-ray image"
    parts = [f"  {d.name} image"]
    if d.label:
        parts.append(f"volume {d.label!r}")
    if d.titles:
        unit = "playlist" if d.kind == "bluray" else "title set"
        parts.append(f"{d.titles} {unit}{'' if d.titles == 1 else 's'}")
    return ", ".join(parts) + ": catalogued, not converted"


# ---------------------------------------------------------------- choosing the medium

def _media_of(info) -> dict[int, tuple[str, list]]:
    """{medium position: (format, [TrackInfo])} of an AlbumInfo."""
    out: dict[int, tuple[str, list]] = {}
    for t in info.tracks:
        pos = t.medium or 1
        out.setdefault(pos, (t.media or "", []))[1].append(t)
    return out


def is_sacd_layer(fmt: str) -> bool:
    """A MusicBrainz medium format of an SACD layer: "SACD", "Hybrid SACD (SACD layer, ...)",
    but not "Hybrid SACD (CD layer)". ("SACD layer" itself contains "CD layer".)"""
    return "SACD" in fmt and "(CD layer" not in fmt


def vet_match(match) -> tuple[bool, bool]:
    """Whether to use pysacd's MusicBrainz match: (its release, its medium).

    A catalogue number or barcode can lead to an edition in another format: a vinyl, CD or
    digital medium is a different release, so neither is used and beets matches the area the
    normal way. A hybrid disc's CD layer is the right release but not the area's medium: some
    releases list only the CD layer, and on others MusicBrainz's CD-layer track lengths fit the
    disc better than the SACD layer's. The release is kept and the medium is left to
    choose_medium, which takes the SACD layer with the area's track count and channels.
    """
    fmt = match.medium.get("format") or ""
    if is_sacd_layer(fmt):
        return True, True
    if "(CD layer" in fmt:
        return True, False
    return False, False


def choose_medium(info, pin: Pin) -> int | None:
    """The medium of `info` that holds this area, or None to leave the candidate alone.

    pysacd's match decides when it is this release. Otherwise the area's medium is the only
    SACD-layer medium (not the CD layer) with the area's track count and channel type.
    """
    media = _media_of(info)
    if len(media) < 2:
        return None
    if pin.release_id and info.album_id == pin.release_id and pin.medium in media:
        return pin.medium
    fits = [pos for pos, (fmt, tracks) in media.items()
            if len(tracks) == pin.tracks and is_sacd_layer(fmt)]
    if len(fits) > 1:
        fits = [pos for pos in fits if ("multichannel" in media[pos][0].lower()) == (pin.area == "multichannel")]
    return fits[0] if len(fits) == 1 else None


def restrict(info, medium: int) -> None:
    """Cut an AlbumInfo down to one medium; album `media` becomes that medium's format."""
    fmt, tracks = _media_of(info)[medium]
    info.tracks = tracks
    info.media = fmt


def pin_candidate(info, pin: Pin) -> None:
    """Cut a candidate looked up for one of our tasks down to the area's medium. Each lookup
    builds a new AlbumInfo, so nothing shared with other tasks changes."""
    medium = choose_medium(info, pin)
    if medium is not None:
        restrict(info, medium)


# ---------------------------------------------------------------- the plugin

class SacdPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__("sacd")
        self.config.add({
            "areas": "stereo",          # stereo | multichannel | both
            "format": "dsf",            # dsf | flac
            "pcm_rate": 88200,          # flac: 88200 | 176400
            "pauses": False,            # include the pauses between tracks (pysacd-extract -b)
            "auto": True,               # convert ISOs found by plain `beet import`
            "remove_iso": False,        # delete an ISO once every area's import is verified
            "staging": "",              # default: a hidden directory in the library directory
            "musicbrainz": True,        # let pysacd match the release
            "contact": "",              # contact for pysacd's MusicBrainz User-Agent
            "threads": 0,               # engine threads, 0 = CPU count
        })
        self._pins: dict[bytes, Pin] = {}           # staging dir -> pin
        self._jobs: list[Job] = []
        self._staging_roots: list[Path] = []
        self._pending_auto = False
        self.register_listener("import_begin", self.import_begin)
        self.register_listener("import_task_start", self.task_start)
        self.register_listener("albuminfo_received", self.albuminfo_received)
        self.register_listener("import_task_choice", self.task_choice)
        self.register_listener("import_task_files", self.task_files)
        self.register_listener("import", self.import_done)
        self.register_listener("cli_exit", self.cli_exit)

    # ------------------------------------------------------------ commands

    def commands(self) -> list[ui.Subcommand]:
        imp = ui.Subcommand("sacd-import", help="convert SACD ISO images with pysacd and import them")
        imp.parser.add_option("-a", "--areas", choices=("stereo", "multichannel", "both"),
                              help="areas to import (default: config `areas`)")
        imp.parser.add_option("-f", "--format", choices=FORMATS, help="dsf or flac (default: config `format`)")
        imp.parser.add_option("--pcm-rate", type="int", help="FLAC sample rate: 88200 or 176400")
        imp.parser.add_option("--pauses", action="store_true", default=None,
                              help="include the pauses between tracks, as pysacd-extract -b")
        imp.parser.add_option("--release", metavar="MBID", help="MusicBrainz release to use (one ISO)")
        imp.parser.add_option("--remove-iso", action="store_true", default=None,
                              help="delete each ISO once its import is verified")
        imp.parser.usage = "%prog [options] ISO|DIRECTORY..."
        imp.func = self.sacd_import

        info = ui.Subcommand("sacd-info", help="print the TOC of SACD ISO images; catalogue DVD and Blu-ray images")
        info.parser.usage = "%prog [options] ISO|DIRECTORY..."
        info.func = self.sacd_info

        mig = ui.Subcommand("sacd-migrate", help="match library items to the SACD ISOs they were extracted "
                                                 "from; record where the ISO and sacdfs hold each track")
        mig.parser.add_option("--apply", action="store_true", default=False,
                              help="write the attributes (default: only report)")
        mig.parser.add_option("--source", metavar="DIR",
                              help="sacdfs SOURCE directory, to work out sacdfs paths (default: the ISO's folder)")
        mig.parser.add_option("--flatten", action="store_true", default=False,
                              help="sacdfs is mounted with --flatten")
        mig.parser.add_option("--verify", metavar="REPORT",
                              help="a `sacdfs verify -o REPORT` report: with --apply, only albums whose every "
                                   "extract is IDENTICAL or IDENTICAL-PAUSE in it are recorded")
        mig.parser.add_option("--catalogue", action="store_true", default=False,
                              help="with --apply: add an album for each ISO area that has no extracts "
                                   "in the library (needs --mount)")
        mig.parser.add_option("--mount", metavar="DIR",
                              help="where sacdfs is mounted: the paths of catalogued items")
        mig.parser.usage = "%prog [options] ISO|DIRECTORY..."
        mig.func = self.sacd_migrate

        exp = ui.Subcommand("sacd-tags-export", help="write sacdfs tag-layer files (genre, MusicBrainz IDs, art) "
                                                     "from the library's SACD albums")
        exp.parser.add_option("--tags", metavar="DIR", help="sacdfs's tags directory (--tags / SACDFS_TAGS)")
        exp.parser.add_option("-n", "--dry-run", action="store_true", default=False,
                              help="report what would be written; write nothing")
        exp.parser.usage = "%prog --tags DIR [QUERY]"
        exp.func = self.sacd_tags_export
        return [imp, info, mig, exp]

    def sacd_info(self, lib, opts, args) -> None:
        from pysacd import safetext
        from pysacd.toc import SACDError, read_toc
        if not args:
            raise ui.UserError("give one or more ISO images or directories")
        isos = [iso for a in args for iso in find_isos(a)]
        if not isos:
            raise ui.UserError("no ISO images found")
        failed = 0
        for path in isos:
            ui.print_(safetext.for_terminal(f"== {displayable_path(str(path))}"))
            try:
                disc = read_toc(str(path))             # read-only
            except SACDError:
                ui.print_(safetext.for_terminal(describe_other(path)))
                continue
            except OSError as e:
                ui.print_(safetext.for_terminal(f"  error: {e}"))
                failed += 1
                continue
            ui.print_(safetext.for_terminal(f"Disc:  {disc.artist or '?'} - {disc.title or '?'}"))
            catalog = disc.disc_catalog_number or disc.album_catalog_number or "-"
            ui.print_(safetext.for_terminal(f"  catalogue {catalog}  disc {disc.album_sequence_number}/"
                                            f"{disc.album_set_size}  hybrid={disc.hybrid}"))
            for area in disc.areas:
                ui.print_(f"Area {area.kind}: {area.speaker_config}, {area.frame_format_name}, "
                          f"{len(area.tracks)} tracks, {area.total_playtime}")
                for t in area.tracks:
                    who = f" [{t.performer}]" if t.performer else ""
                    ui.print_(safetext.for_terminal(f"  {t.number:2d}. {t.duration}  {t.title or ''}{who}"))
            for w in disc.warnings + [w for a in disc.areas for w in a.warnings]:
                ui.print_(safetext.for_terminal(f"  warning: {w}"))
        if failed:
            raise ui.UserError(f"{failed} image(s) could not be read")

    def sacd_import(self, lib, opts, args) -> None:
        if not args:
            raise ui.UserError("give one or more ISO images or directories")
        isos = [iso for a in args for iso in find_isos(a)]
        if not isos:
            raise ui.UserError("no ISO images found")
        if opts.release and len(isos) > 1:
            raise ui.UserError("--release needs exactly one ISO")
        for key in ("areas", "format", "pcm_rate", "pauses", "remove_iso"):
            if getattr(opts, key, None) is not None:
                self.config[key] = getattr(opts, key)
        try:
            paths = self.prepare(lib, isos, release=opts.release)
            if paths:
                import_files(lib, paths, None)
            self.finish(lib)
        finally:
            self.cleanup()

    def sacd_migrate(self, lib, opts, args) -> None:
        """Report, and with --apply record, which library albums are extracts of which ISO area.

        Albums are matched by the `sacd_iso_sha` and `sacd_area` that `sacd-import` wrote or,
        for extracts imported some other way, by living under the ISO's folder with the area's
        track count and lengths. Matched items get `sacd_iso`, `sacd_track` and `sacdfs_path`
        (flexible attributes: beets' own data, never the files). Nothing is deleted or moved."""
        from pysacd import safetext
        from pysacd.toc import SACDError, SACDImage
        if not args:
            raise ui.UserError("give one or more ISO images or directories")
        isos = [iso for a in args for iso in find_isos(a)]
        if not isos:
            raise ui.UserError("no ISO images found")
        source = Path(os.path.abspath(opts.source)) if opts.source else None
        if opts.catalogue and not opts.mount:
            raise ui.UserError("--catalogue needs --mount DIR, where sacdfs is mounted")
        verified = None
        if opts.verify:
            try:
                with open(opts.verify, "rb") as f:
                    verified = parse_verify_report(f.read())
            except (OSError, ValueError) as e:
                raise ui.UserError(f"cannot use the verify report: {e}") from e
        claimed: set[int] = set()
        n_cat = n_held = 0
        n_albums = 0
        for iso in isos:
            shown = safetext.for_terminal(displayable_path(str(iso)))
            iso = Path(os.path.abspath(iso))
            try:
                with SACDImage(str(iso)) as img:       # read-only
                    disc = img.read_toc()
                    fp = fingerprint(img, disc)
            except (SACDError, OSError):
                ui.print_(f"{shown}: not a readable SACD image, skipped")
                continue
            root = source or iso.parent
            for kind in AREAS:
                area = disc.stereo if kind == "stereo" else disc.multichannel
                if area is None:
                    continue
                tracks = sorted(area.tracks, key=lambda t: t.number)
                secs = [t.duration.seconds_float for t in tracks]
                found = self._extracts(lib, iso, fp, kind, secs, claimed)
                if not found:
                    ui.print_(f"{shown}: {kind}: no extracts in the library")
                    if opts.catalogue and not self._has_extracts(lib, iso, fp, kind, len(tracks)):
                        n_cat += 1
                        ui.print_(f"{shown}: {kind}: {'catalogued' if opts.apply else 'would catalogue'} "
                                  f"as an album of {len(tracks)} tracks")
                        if opts.apply:
                            self._catalogue(lib, iso, fp, kind, disc, area, tracks, root, opts)
                    continue
                for album, items in found:
                    claimed.add(album.id)
                    n_albums += 1
                    bad = [] if verified is None else [i for i in items if not verified.get(i.path, False)]
                    if bad:
                        n_held += 1
                        ui.print_(safetext.for_terminal(
                            f"{shown}: {kind}: album {album.id} {album.albumartist} - {album.album}: "
                            f"{len(items)} tracks match, but {len(bad)} are not IDENTICAL or "
                            f"IDENTICAL-PAUSE in the verify report; not recorded"))
                        continue
                    ui.print_(safetext.for_terminal(
                        f"{shown}: {kind}: album {album.id} {album.albumartist} - {album.album}: "
                        f"{len(items)} tracks match; {'recorded' if opts.apply else 'would record'}"))
                    for item, t in zip(items, tracks, strict=True):
                        item["sacd_iso"] = os.fsdecode(iso)
                        item["sacd_track"] = t.number
                        item["sacd_area"] = kind
                        item["sacdfs_path"] = sacdfs_path(iso, root, opts.flatten, kind, t.number, t.title)
                        if opts.apply:
                            item.store()
        ui.print_(f"{n_albums} album(s) matched" + (f", {n_held} held back by the verify report" if n_held else "")
                  + (f"; {n_cat} catalogued" if opts.catalogue else "")
                  + ". Nothing was deleted: check them with sacdfs verify before removing any extract.")

    def _has_extracts(self, lib, iso: Path, fp: str, kind: str, n_tracks: int) -> bool:
        """Does the library hold anything that could be extracts of this ISO area: an album it
        imported from it, or one under the ISO's folder with the area's number of tracks?"""
        if any(True for _ in lib.albums(f"sacd_iso_sha:{fp} sacd_area:{kind}")):
            return True
        folder = os.fsencode(str(iso.parent)).rstrip(os.sep.encode()) + os.sep.encode()
        return any(len(items := a.items()) == n_tracks and all(i.path.startswith(folder) for i in items)
                   for a in lib.albums())

    def _catalogue(self, lib, iso: Path, fp: str, kind: str, disc, area, tracks, root: Path, opts) -> None:
        """Add the area as an album whose items are the files sacdfs shows: no extracts, no tags
        written. Items carry the disc's text, track order, lengths and channels."""
        from beets.library import Item
        mount = Path(os.path.abspath(opts.mount))
        items = []
        for t in tracks:
            rel = sacdfs_path(iso, root, opts.flatten, kind, t.number, t.title)
            item = Item(path=os.fsencode(mount / rel), title=t.title or f"Track {t.number}",
                        artist=t.performer or disc.artist or "", albumartist=disc.artist or "",
                        album=disc.title or "", track=t.number, tracktotal=len(tracks),
                        disc=disc.album_sequence_number or 1, disctotal=disc.album_set_size or 1,
                        length=t.duration.seconds_float, channels=area.channel_count, format="DSF",
                        sacd_iso=os.fsdecode(iso), sacd_track=t.number, sacd_area=kind,
                        sacd_iso_sha=fp, sacdfs_path=rel, sacd_catalogued=1)
            items.append(item)
        album = lib.add_album(items)
        album["sacd_iso_sha"] = fp
        album["sacd_area"] = kind
        album["sacd_catalogued"] = 1
        album.store()

    def sacd_tags_export(self, lib, opts, args) -> None:
        """Write the sacdfs tags file of every SACD disc the library has albums for.

        Albums are those whose items carry `sacd_iso` and `sacd_area` (sacd-import, sacd-migrate).
        The file is named by the disc's TOC key, worked out as sacdfs does. Per area, the genre,
        label and MusicBrainz IDs of the album and its tracks, and the album's cover, are written
        to `[<area>.album]` and `[<area>.track.N]`; every other field already in the file stays."""
        from pysacd import safetext
        from pysacd.toc import SACDError, SACDImage
        if not opts.tags:
            raise ui.UserError("give the tags directory: --tags DIR")
        tags_dir = Path(os.path.abspath(opts.tags))
        if not tags_dir.is_dir():
            raise ui.UserError("the tags directory does not exist")
        discs: dict[str, dict[str, list]] = {}              # iso -> area -> items
        for item in lib.items(list(args)):
            iso, area = item.get("sacd_iso"), item.get("sacd_area")
            if iso and area in AREAS and item.get("sacd_track"):
                discs.setdefault(str(iso), {}).setdefault(area, []).append(item)
        if not discs:
            ui.print_("no albums with an SACD image in the library (see sacd-migrate)")
            return
        written = 0
        for iso, areas in sorted(discs.items()):
            shown = safetext.for_terminal(displayable_path(iso))
            try:
                with SACDImage(iso) as img:                 # read-only
                    key = _sacd_tags.disc_key(img, img.read_toc())
            except (SACDError, OSError):
                ui.print_(f"{shown}: not a readable SACD image, skipped")
                continue
            path = tags_dir / f"{key}.toml"
            try:
                existing = _sacd_tags.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            except (OSError, ValueError):
                ui.print_(f"{shown}: {key}.toml exists but is not readable TOML, left alone")
                continue
            ours: dict = {}
            for area, items in areas.items():
                section = self._tag_section(items, tags_dir, key, area, opts.dry_run)
                if section:
                    ours[area] = section
            data = _sacd_tags.dumps(_sacd_tags.merge(existing, ours)).encode()
            if opts.dry_run:
                changed = not path.exists() or path.read_bytes() != data
            else:
                changed = _sacd_tags.write_atomic(path, data)
            written += changed
            state = ("would be written" if opts.dry_run else "written") if changed else "unchanged"
            ui.print_(f"{shown}: {key}.toml {state}")
        ui.print_(f"{written} tags file(s) {'would change' if opts.dry_run else 'written'}.")

    def _tag_section(self, items: list, tags_dir: Path, key: str, area: str, dry: bool) -> dict:
        """{"album": {...}, "track": {"N": {...}}} for one area's items."""
        first = items[0]
        album = first.get_album()
        src = album if album is not None else first
        fields = {"genre": src.get("genre"), "publisher": src.get("label"),
                  "TXXX:MusicBrainz Album Id": src.get("mb_albumid"),
                  "TXXX:MusicBrainz Release Group Id": src.get("mb_releasegroupid"),
                  "TXXX:MusicBrainz Album Artist Id": src.get("mb_albumartistid")}
        alb = {k: str(v) for k, v in fields.items() if v}
        artpath = album.get("artpath") if album is not None else None
        if artpath:
            name = self._export_art(os.fsdecode(artpath), tags_dir, f"{key}-{area}", dry)
            if name:
                alb["art"] = name
        tracks: dict[str, dict[str, str]] = {}
        for it in items:
            f = {"UFID:http://musicbrainz.org": it.get("mb_trackid"),
                 "TXXX:MusicBrainz Release Track Id": it.get("mb_releasetrackid"),
                 "TXXX:MusicBrainz Artist Id": it.get("mb_artistid")}
            f = {k: str(v) for k, v in f.items() if v}
            if f:
                tracks[str(int(it["sacd_track"]))] = f
        out: dict = {}
        if alb:
            out["album"] = alb
        if tracks:
            out["track"] = tracks
        return out

    def _export_art(self, artpath: str, tags_dir: Path, stem: str, dry: bool) -> str | None:
        """Copy the album cover into the tags directory; its name there, or None if it can't be used."""
        try:
            data = Path(artpath).read_bytes()
        except OSError:
            return None
        ext = _sacd_tags.picture_ext(data)
        if ext is None or len(data) > _sacd_tags.ART_MAX_BYTES:
            self._log.warning("cover art is not a JPEG or PNG of at most 960 KiB; not exported")
            return None
        name = f"{stem}.{ext}"
        if not dry:
            _sacd_tags.write_atomic(tags_dir / name, data)
        return name

    def _extracts(self, lib, iso: Path, fp: str, kind: str, secs: list[float], claimed: set[int]):
        """[(album, items in track order)] of the library's extracts of this ISO area."""
        out = []
        seen: set[int] = set()
        candidates = list(lib.albums(f"sacd_iso_sha:{fp} sacd_area:{kind}"))
        folder = os.fsencode(str(iso.parent)).rstrip(os.sep.encode()) + os.sep.encode()
        for a in lib.albums():
            if a.id not in {c.id for c in candidates} and all(i.path.startswith(folder) for i in a.items()):
                candidates.append(a)
        for a in candidates:
            if a.id in seen or a.id in claimed:
                continue
            seen.add(a.id)
            items = sorted(a.items(), key=lambda i: (i.disc or 1, i.track or 0))
            if items and durations_match([i.length for i in items], secs):
                out.append((a, items))
        return out

    # ------------------------------------------------------------ converting

    def _staging_root(self, lib) -> Path:
        base = self.config["staging"].as_str() or syspath(lib.directory)
        os.makedirs(base, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix=".sacd-staging-", dir=base))
        self._staging_roots.append(root)
        return root

    def _areas(self) -> list[str]:
        a = self.config["areas"].as_str()
        if a not in ("stereo", "multichannel", "both"):
            raise ui.UserError(f"sacd: areas must be stereo, multichannel or both, not {a!r}")
        return list(AREAS) if a == "both" else [a]

    def prepare(self, lib, isos: list[Path], release: str | None = None) -> list[bytes]:
        """Convert every wanted area of every ISO that isn't in the library yet. Returns the
        staging directories to import."""
        fmt = self.config["format"].as_str()
        if fmt not in FORMATS:
            raise ui.UserError(f"sacd: format must be dsf or flac, not {fmt!r}")
        if self.config["pauses"].get(bool) and not pysacd_has_pauses():
            raise ui.UserError("sacd: pauses needs pysacd 0.2.1 or later (convert --pauses)")
        paths = []
        for iso in isos:
            job = self.convert(lib, iso, fmt, release)
            if job is not None:
                self._jobs.append(job)
                paths += [bytestring_path(str(p.staging)) for p in job.pins]
        return paths

    def convert(self, lib, iso: Path, fmt: str, release: str | None) -> Job | None:
        from pysacd import musicbrainz, safetext
        from pysacd.convert import Options
        from pysacd.convert import convert as pysacd_convert
        from pysacd.toc import SACDError, SACDImage

        shown = safetext.for_terminal(displayable_path(str(iso)))
        try:
            with SACDImage(str(iso)) as img:       # read-only
                disc = img.read_toc()
                fp = fingerprint(img, disc)
        except SACDError:
            self._log.info("{}: {}", shown, safetext.for_terminal(describe_other(iso)))
            return None
        except OSError as e:
            self._log.warning("{}: not readable ({})", shown, safetext.for_terminal(e))
            return None
        job = Job(iso)
        root = None
        for kind in self._areas():
            area = disc.stereo if kind == "stereo" else disc.multichannel
            if area is None:
                self._log.info("{}: no {} area", shown, kind)
                continue
            if any(True for _ in lib.albums(f"sacd_iso_sha:{fp} sacd_area:{kind}")):
                self._log.info("{}: {} area already imported, skipped", shown, kind)
                job.skipped.append(kind)
                continue
            match = None
            contact = self.config["contact"].as_str() or None
            if self.config["musicbrainz"].get(bool):
                try:
                    match = musicbrainz.find_release(disc, area, contact, release)
                except musicbrainz.MBError as e:
                    self._log.warning("{}: MusicBrainz lookup failed: {}", shown, safetext.for_terminal(e))
            use_medium = False
            if match is not None:
                use_release, use_medium = vet_match(match)
                use_release = use_release or release is not None     # --release: the user's choice
                fmt_shown = safetext.for_terminal(match.medium.get("format") or "unknown format")
                if not use_release:
                    self._log.info("{}: {} area: MusicBrainz match {} is a {} medium, not SACD; not used",
                                   shown, kind, match.release_id, fmt_shown)
                    match = None
                elif not use_medium:
                    self._log.info("{}: {} area: matched the CD layer of release {}; its SACD layer is "
                                   "chosen by track count and channels", shown, kind, match.release_id)
            root = root or self._staging_root(lib)
            out = root / f"{len(self._pins):03d}-{kind}"
            opts = Options(format=fmt, output_dir=str(out), dir_template="album", areas=kind,
                           pcm_rate=self.config["pcm_rate"].get(int), jobs=self.config["threads"].get(int),
                           musicbrainz=match is not None, mb_release=match.release_id if match else None,
                           mb_contact=contact, cover=False, cover_file="")
            if self.config["pauses"].get(bool):
                opts.pauses = True
            self._log.info("{}: converting the {} area ({} tracks) to {}", shown, kind, len(area.tracks), fmt)
            if pysacd_convert(str(iso), opts) != 0:
                self._log.error("{}: converting the {} area failed; it is not imported", shown, kind)
                continue
            pin = Pin(iso, fp, kind, len(area.tracks), out / "album")
            if match is not None:
                pin.release_id = match.release_id
                if use_medium:
                    pin.medium, pin.media = match.medium.get("position"), match.medium.get("format")
                if use_medium:
                    self._log.info("{}: {} area is medium {} ({}) of release {}", shown, kind, pin.medium,
                                   safetext.for_terminal(pin.media or ""), pin.release_id)
            self._pins[bytestring_path(str(pin.staging))] = pin
            job.pins.append(pin)
        return job

    # ------------------------------------------------------------ plain `beet import`

    def import_begin(self, session) -> None:
        """Replace ISO images among the paths being imported by their converted areas."""
        if not self.config["auto"].get(bool) or not session.paths:
            return
        found: list[Path] = []
        keep = []
        for p in session.paths:
            isos = find_isos(syspath(p))
            if is_iso(syspath(p)):
                found += isos               # the ISO itself is replaced by its areas
                continue
            keep.append(p)
            if bytestring_path(syspath(p)) not in self._pins:
                found += isos               # ISOs inside a directory being imported
        if not found:
            return
        self._pending_auto = True
        session.paths = keep + self.prepare(session.lib, found)

    # ------------------------------------------------------------ the medium pin

    def _pin_of(self, task) -> Pin | None:
        top = getattr(task, "toppath", None)
        return self._pins.get(top) if top else None

    def task_start(self, session, task) -> None:
        pin = self._pin_of(task)
        if pin is None:
            return
        # pysacd tags the physical disc (disc 1/1, "Hybrid SACD"); MusicBrainz counts each layer
        # as a medium (2/3, "Hybrid SACD (SACD layer, 2 channels)"). Those tags would count
        # against the right candidate, so beets doesn't see them; it writes the medium's own
        # values when it applies the match.
        for item in task.items:
            item.disc = item.disctotal = 0
            item.media = ""

        # Candidates for this task are cut to its medium while they are looked up, and an SACD
        # edition is preferred over the same release in another format (#9): without pysacd's
        # release, beets would otherwise take whichever edition scores best. The user's own
        # preferred media still apply, after SACD, and only this task's lookup sees the change
        # (beets looks up one task at a time).
        lookup = task.lookup_candidates

        def lookup_pinned(*args, **kwargs):
            token = _current.set(pin)
            preferred = config["match"]["preferred"]["media"]
            saved = preferred.as_str_seq()
            preferred.set([SACD_MEDIA, *saved])
            try:
                return lookup(*args, **kwargs)
            finally:
                preferred.set(saved)
                _current.reset(token)
        task.lookup_candidates = lookup_pinned

        # Staged files always move into the library, whatever the session does with other
        # files (copy, or import in place): the staging directory is deleted afterwards
        manipulate = task.manipulate_files
        signature = inspect.signature(manipulate)

        def manipulate_move(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.arguments["operation"] = MoveOperation.MOVE
            return manipulate(*bound.args, **bound.kwargs)
        task.manipulate_files = manipulate_move

        # The other layer of the same release (the other area, or the CD layer) has the same
        # artist and album, which beets' default duplicate keys would call a duplicate. Only an
        # album on the same medium is one.
        find_duplicates = task.find_duplicates

        def same_medium_duplicates(lib):
            media = getattr(getattr(task, "match", None), "info", None)
            media = getattr(media, "media", None)
            found = find_duplicates(lib)
            return [a for a in found if not media or a.get("media") == media]
        task.find_duplicates = same_medium_duplicates

    def albuminfo_received(self, info) -> None:
        pin = _current.get()
        if pin is not None:
            pin_candidate(info, pin)

    def task_choice(self, session, task) -> None:
        """Guard: the chosen match must use the area's medium (beets 2.14 maps hybrid SACD
        files to the CD layer otherwise)."""
        pin = self._pin_of(task)
        match = getattr(task, "match", None)
        if pin is None or match is None or not hasattr(match, "mapping"):
            return
        info = match.info
        medium = choose_medium(info, pin)
        if medium is None:
            return
        fmt, tracks = _media_of(info)[medium]
        mapped = set(match.mapping.values())
        if all(t.medium == medium for t in mapped) and info.media == fmt:
            return
        items = sorted(match.mapping, key=lambda i: (i.disc or 0, i.track or 0))
        if len(items) != len(tracks):
            self._log.warning("release {}: {} files but medium {} has {} tracks; mapping left as is",
                              info.album_id, len(items), medium, len(tracks))
            return
        tracks = sorted(tracks, key=lambda t: t.medium_index or t.index or 0)
        self._log.info("release {}: remapped {} tracks to medium {} ({})", info.album_id, len(tracks), medium, fmt)
        restrict(info, medium)
        match.mapping = dict(zip(items, tracks, strict=True))
        match.extra_tracks = []

    # ------------------------------------------------------------ bookkeeping

    def task_files(self, session, task) -> None:
        pin = self._pin_of(task)
        album = getattr(task, "album", None)
        if pin is None or album is None:
            return
        album.sacd_iso_sha = pin.fingerprint
        album.sacd_area = pin.area
        album.store()

    def _verified(self, lib, job: Job) -> bool:
        """Every wanted area is an album in the library with all its tracks on disk."""
        if not job.pins and not job.skipped:
            return False
        for pin in job.pins:
            albums = list(lib.albums(f"sacd_iso_sha:{pin.fingerprint} sacd_area:{pin.area}"))
            if not any(len(items := list(a.items())) == pin.tracks
                       and all(os.path.exists(syspath(i.path)) for i in items) for a in albums):
                return False
        return True

    def finish(self, lib) -> None:
        if not self.config["remove_iso"].get(bool):
            return
        from pysacd import safetext
        for job in self._jobs:
            shown = safetext.for_terminal(displayable_path(str(job.iso)))
            if self._verified(lib, job):
                os.remove(job.iso)
                self._log.info("{}: imported and verified; ISO removed", shown)
            else:
                self._log.warning("{}: not every area was imported; ISO kept", shown)

    def import_done(self, lib, paths) -> None:
        if self._pending_auto:
            try:
                self.finish(lib)
            finally:
                self.cleanup()

    def cli_exit(self, lib) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        for root in self._staging_roots:
            shutil.rmtree(root, ignore_errors=True)
        self._staging_roots.clear()
        self._pins.clear()
        self._jobs.clear()
        self._pending_auto = False

