"""A synthetic hybrid SACD release in MusicBrainz ws/2 JSON, and fake MusicBrainz servers.

Like a real hybrid SACD on MusicBrainz, the release lists the CD layer, the SACD stereo layer
and the SACD multichannel layer as three media with the same recordings. That is what makes
beets 2.14 map SACD files to the CD layer (README, "Hybrid SACDs")."""
ALBUM = "pysacd sacd plugin test"
RID = "11111111-2222-3333-4444-555555555555"
CD_RID = "11111111-2222-3333-4444-666666666666"     # the same album's CD edition (#9)
EDITIONS = False                                      # tests set it: search finds the CD edition too
ARTIST = {"id": "aaaaaaaa-0000-0000-0000-000000000001", "name": "Test Artist", "sort-name": "Artist, Test",
          "disambiguation": "", "type": "Person", "aliases": [], "genres": [], "tags": []}
CREDIT = [{"name": "Test Artist", "joinphrase": "", "artist": ARTIST}]
TITLES = ["One", "Two", "Three"]
LEN_MS = 1000                   # tracks of 75 frames
# The release's media: tests replace this to play other editions (vinyl only, CD layer only)
MEDIA = [(1, "Hybrid SACD (CD layer)"), (2, "Hybrid SACD (SACD layer, 2 channels)"),
         (3, "Hybrid SACD (SACD layer, multichannel)")]


def _rec(i):
    return {"id": f"bbbbbbbb-0000-0000-0000-00000000000{i + 1}", "title": TITLES[i], "length": LEN_MS,
            "artist-credit": CREDIT, "isrcs": [f"XXPYS26{i + 1:05d}"], "disambiguation": "", "video": False,
            "relations": [], "aliases": [], "genres": [], "tags": [], "first-release-date": "2026-01-01"}


def _medium(pos, fmt):
    return {"position": pos, "format": fmt, "title": "", "track-count": 3, "track-offset": 0,
            "tracks": [{"id": f"cccccccc-0000-0000-000{pos}-00000000000{i + 1}", "position": i + 1,
                        "number": str(i + 1), "title": TITLES[i], "length": LEN_MS,
                        "artist-credit": CREDIT, "recording": _rec(i)} for i in range(3)]}


def release():
    return {
        "id": RID, "title": ALBUM, "status": "Official", "quality": "normal",
        "disambiguation": "", "barcode": "0000000000017", "country": "XW", "date": "2026-10-28",
        "packaging": None, "asin": None,
        "text-representation": {"language": "eng", "script": "Latn"},
        "artist-credit": CREDIT,
        "release-group": {"id": "dddddddd-0000-0000-0000-000000000001", "title": ALBUM,
                          "primary-type": "Album", "secondary-types": [], "first-release-date": "2026-10-28",
                          "artist-credit": CREDIT, "disambiguation": "", "genres": [], "tags": [], "aliases": []},
        "label-info": [{"catalog-number": "PYSACD-TEST", "label": {"id": "eeeeeeee-0000-0000-0000-000000000001",
                                                                   "name": "Test Label", "aliases": []}}],
        "release-events": [{"date": "2026-10-28", "area": None}],
        "media": [_medium(pos, fmt) for pos, fmt in MEDIA],
        "relations": [], "aliases": [], "genres": [], "tags": [],
        "cover-art-archive": {"artwork": False, "front": False, "back": False, "count": 0, "darkened": False},
    }


def cd_release():
    """The CD edition: the same tracks on one CD medium, with its own barcode."""
    rel = release()
    rel.update(id=CD_RID, barcode="0000000000024", media=[_medium(1, "CD")])
    return rel


def pysacd_json(path: str, contact, **params) -> dict:
    """Stands in for pysacd.musicbrainz._json: every search finds the fixture release."""
    if path.startswith("release/"):
        return release()
    return {"releases": [{"id": RID}], "count": 1}


def beets_get_json(self, url, *args, **kwargs):
    """Stands in for beets' RequestHandler.get_json (the MusicBrainz plugin's HTTP layer)."""
    url = str(url)
    if f"/release/{RID}" in url:
        return release()
    if f"/release/{CD_RID}" in url:
        return cd_release()
    if "/release" in url and "query" in str(kwargs) + url:
        found = [cd_release(), release()] if EDITIONS else [release()]     # the CD edition first
        return {"releases": found, "count": len(found), "release-count": len(found)}
    return {"releases": [], "count": 0, "release-count": 0}
