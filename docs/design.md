[beets-pysacd](../README.md) › [Documentation](README.md) › Design

# Design

How the plugin imports an SACD image, and why it keeps each SACD layer on its own medium of the
MusicBrainz release.

## Hybrid SACDs

MusicBrainz lists a hybrid SACD as one release with several media: the CD
layer, the SACD stereo layer and sometimes the SACD multichannel layer, all
with the same recordings. beets puts the tracks of every medium into one
candidate and then matches files to tracks. With the same recordings on every
layer, it maps the SACD files to the CD layer (medium 1), overwrites their
release track IDs, and writes the album-level `media` as "Media". See the
[beets discussion](https://github.com/beetbox/beets/discussions/6614).

This plugin keeps each area on its own medium:

- When pysacd matched the release, it knows the medium: that release's
  candidates are cut down to that medium before beets compares them, and the
  album's `media` is that medium's format, e.g. "Hybrid SACD (SACD layer,
  2 channels)".
- Without pysacd's match, the medium is the one SACD-layer medium of the
  candidate with the area's track count and channel type. If that is
  ambiguous (a set of two SACDs, say), the candidate is left as beets made it.
- A final check after you choose a match maps the files to the medium if
  they still point elsewhere, and logs it.

## Importing an SACD image

For each SACD image, and each selected area of it:

1. pysacd reads the TOC (read-only), and the plugin fingerprints the disc from its TOCs and
   the image size.
   An area whose fingerprint and area are already in the library is skipped.
2. pysacd matches the MusicBrainz release and medium, and converts the area
   into the staging directory, writing the release's IDs into the files.
   A match on a medium that isn't an SACD layer (a vinyl, CD or digital
   edition sharing the catalogue number or barcode) isn't used: the area is
   converted without IDs and beets matches it the normal way, preferring
   an SACD edition (see below). A match on the
   CD layer of a hybrid release keeps the release; the area goes to that
   release's SACD layer with its track count and channels.
3. beets imports the staging directory. Because the files agree on the
   release ID, beets looks that release up directly. For this one import task
   only, the plugin then:
   - **hides the physical-disc tags from matching.** pysacd tags the physical
     disc ("disc 1 of 1", media "Hybrid SACD"), but MusicBrainz counts each
     layer as a medium ("disc 2 of 3", "Hybrid SACD (SACD layer, 2
     channels)"). beets would count those tags against the right candidate,
     enough to keep a correct match from being applied automatically. beets
     writes the medium's own values when it applies the match;
   - **cuts the release's candidates down to the area's medium** (see
     [Hybrid SACDs](#hybrid-sacds));
   - **prefers SACD editions.** Without pysacd's release, beets would take
     whichever edition of the album scores best, often the CD. For this task
     only, an SACD medium goes first in `match.preferred.media`; your own
     preferred media follow it, and other imports don't see the change;
   - **counts only an album on the same medium as a duplicate.** beets' default
     duplicate keys are album artist and album, which both areas of a disc
     (and a CD rip of the same release) share: without this, importing the
     multichannel area after the stereo one would be skipped as a duplicate.
     With no medium to compare (an as-is import, or no match), an album of the
     other area is still never one: it is known by its `sacd_area` or, while
     that isn't set yet, by its channel count. Another copy of the same layer
     is still a duplicate;
   - **moves the files** into the library (see [Files and staging](options.md#files-and-staging)).
4. The album gets `sacd_iso_sha` and `sacd_area`; with `remove_iso`, the ISO is
   deleted once every area is imported in this run and verified. The staging directory is removed.

Nothing here changes how beets treats your other files in the same import.

## See also

- [User guide](user-guide.md)
- [Options and configuration](options.md)
- [Development](development.md)

Part of the [DSD Toolbox](https://github.com/aclater/dsd-toolbox).
