# Configuration

```yaml
sacd:
    areas: stereo        # stereo | multichannel | both
    format: dsf          # dsf | flac (24-bit PCM)
    pcm_rate: 88200      # flac: 88200 | 176400
    pauses: no           # include the pauses between tracks (pysacd 0.2.1 or later)
    auto: yes            # convert ISOs found by plain `beet import`
    remove_iso: no       # delete an ISO once every area is imported in this run and verified
    staging: ''          # where to convert; default: a hidden directory in the library directory
    musicbrainz: yes     # let pysacd find the release (barcode, catalogue number, ISRCs)
    contact: ''          # contact (e.g. an e-mail address) for pysacd's MusicBrainz User-Agent
    threads: 0           # conversion threads; 0 = one per CPU
```

`sacd-import` options override `areas`, `format`, `pcm_rate`, `pauses` and
`remove_iso` for one run.

Tracks are cut at their timecodes, without the pauses between them, like
`pysacd convert`. With `pauses: yes` (or `--pauses`) each pause goes with the
track before it, exactly as `pysacd-extract -b` and `sacd_extract -b` cut them:
use it when your library already holds extracts made that way, so the same
disc gives the same tracks. It needs pysacd 0.2.1 or later.

## Keeping or removing ISO images

ISO images are kept by default, and never written to. With `remove_iso: yes`
(or `--remove-iso`) an image is deleted only when every selected area was
imported from it in this run and verified: the album beets made from that
image is in the library with all of the area's tracks, and every file exists.
An import you skip, or one that fails, keeps the image. So does an import
beets skips as a duplicate: if you import a good and a bad rip of one disc
together, one becomes the album and the other is kept, with a line in the log.

An image with an area that is already in the library is kept too, and the log
says which area and that the ISO was kept. The fingerprint that says "already
imported" is the disc's TOCs and the image size, not its audio, so it doesn't
prove that this image holds the same audio as the album in the library: a good
rip and a damaged rip of one disc, or an image that copies another's TOC, have
the same fingerprint. Delete such an image yourself once you have compared it.

## Files and staging

Converted files always move from the staging directory into your library,
whatever `copy`, `move` or in-place settings you use for other files: the
staging directory is temporary and is deleted afterwards, also after an error.
By default it is created inside the library directory, so the move is a
rename on the same filesystem; set `staging` to put it elsewhere.
