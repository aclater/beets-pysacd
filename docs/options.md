[beets-pysacd](../README.md) › [Documentation](README.md) › Options and configuration

# Options and configuration

Every command's options and every setting in the `sacd:` section of the beets config, with their
defaults. How to use them is in the [user guide](user-guide.md).

## Commands

`beet sacd-import [options] ISO|DIRECTORY...` converts SACD images and imports them.

| Option | What it does |
|---|---|
| `-a`, `--areas` | `stereo`, `multichannel` or `both` (default: config `areas`) |
| `-f`, `--format` | `dsf` or `flac` (default: config `format`) |
| `--pcm-rate` | FLAC sample rate: `88200` or `176400` |
| `--pauses` | include the pauses between tracks, as `pysacd-extract -b` |
| `--release MBID` | the MusicBrainz release to use (one image only) |
| `--remove-iso` | delete each image once its import is verified |

`beet sacd-info ISO|DIRECTORY...` prints the TOC of SACD images and catalogues DVD and Blu-ray
images. It has no options and changes nothing.

`beet sacd-migrate [options] ISO|DIRECTORY...` matches library items to the SACD images they
were extracted from.

| Option | What it does |
|---|---|
| `--apply` | write the attributes (default: only report) |
| `--source DIR` | sacdfs' SOURCE directory, to work out sacdfs paths (default: the image's folder) |
| `--flatten` | sacdfs is mounted with `--flatten` |
| `--verify REPORT` | a `sacdfs verify -o` report: with `--apply`, only albums whose every extract is `IDENTICAL` or `IDENTICAL-PAUSE` in it are recorded |
| `--catalogue` | add an album for each image area that has no extracts in the library (needs `--mount`; only reports without `--apply`) |
| `--mount DIR` | where sacdfs is mounted: the paths of catalogued items. With `--apply`, catalogued items with sacdfs 0.4.0 names the mount no longer shows move to its 0.4.1 names, and those with no recorded mtime get their file's |

`beet sacd-tags-export --tags DIR [QUERY]` writes sacdfs tags files from the library's SACD
albums.

| Option | What it does |
|---|---|
| `--tags DIR` | sacdfs' tags directory (sacdfs `--tags`, `SACDFS_TAGS`); required |
| `-n`, `--dry-run` | report what would be written; write nothing |

## Settings

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

## Pauses between tracks

Tracks are cut at their timecodes, without the pauses between them, like
`pysacd convert`. With `pauses: yes` (or `--pauses`) each pause goes with the
track before it, exactly as `pysacd-extract -b` and `sacd_extract -b` cut them:
use it when your library already holds extracts made that way, so the same
disc gives the same tracks. It needs pysacd 0.2.1 or later.

## Keeping or removing SACD images

SACD images are kept by default, and never written to. With `remove_iso: yes`
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

## See also

- [User guide](user-guide.md)
- [Design](design.md)
- [Install](install/README.md)

Part of the [DSD Toolbox](https://github.com/aclater/dsd-toolbox).
