"""Keep tag fields set by hand on catalogued items through `beet update` (#68).

A catalogued item's file is on the read-only sacdfs mount, so beets can't write a tag edited in
the library to it. beets then leaves the item's mtime at 0, and the next `beet update` reads the
file's tags back over the edit. The listener here records the file's mtime instead, as beets does
after writing tags: `beet update` skips the item until the file's mtime changes on the mount.

It is a plugin object of its own because beets doesn't let one plugin's listeners nest: the
`sacd` plugin's own listeners store albums and items, which sends `database_change`."""

from __future__ import annotations

import os

from beets.plugins import BeetsPlugin
from beets.util import syspath


def file_mtime(path: bytes) -> int | None:
    """A file's mtime as beets records it (`Item.current_mtime`: whole seconds), or None when
    the file can't be found."""
    try:
        return int(os.path.getmtime(syspath(path)))
    except OSError:
        return None


def keep_catalogued_edits(lib, model) -> None:
    """Give a catalogued item whose mtime is 0 and whose file exists that file's mtime. Only the
    item's `mtime` column is written."""
    from beets.library import Item
    if not isinstance(model, Item) or model.id is None or model.mtime or not model.get("sacd_catalogued"):
        return
    mtime = file_mtime(model.path)
    if not mtime:
        return
    with lib.transaction() as tx:      # not store(): that would forget fields a caller left unstored
        tx.mutate("UPDATE items SET mtime = ? WHERE id = ? AND mtime = 0", (mtime, model.id))
    model.mtime = mtime


class CatalogueEdits(BeetsPlugin):
    """Registered by the `sacd` plugin; not a plugin users enable."""

    def __init__(self) -> None:
        super().__init__("sacd_edits")
        self.register_listener("database_change", keep_catalogued_edits)
