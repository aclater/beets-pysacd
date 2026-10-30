# Security policy

## Supported versions

Security fixes go into the latest release and `main`. There are no maintained release
branches: if you're on an older release, the fix is to upgrade.

| Version | Supported |
| --- | --- |
| latest release ([releases](https://github.com/aclater/beets-pysacd/releases)) | yes |
| `main` | yes |
| anything older | no |

A problem in pysacd itself (reading SACD images, extracting, its MusicBrainz client) belongs
to [pysacd's security policy](https://github.com/aclater/pysacd/security/policy); if you're
not sure which project it is, report it here.

## Reporting a vulnerability

Please don't open a public issue, pull request or discussion for a vulnerability. Report it
privately through GitHub's private vulnerability reporting:

**<https://github.com/aclater/beets-pysacd/security/advisories/new>**

(or the **Report a vulnerability** button on the repository's
[Security tab](https://github.com/aclater/beets-pysacd/security)). Only the maintainer sees
the report.

Please include:

- the beets-pysacd, beets and pysacd versions (`pip show beets-pysacd pysacd`,
  `beet version`), your OS and Python version;
- the command you ran and your plugin settings (the `sacd:` section of the beets config);
- the input that triggers it: a disc image, a MusicBrainz response, or best of all a script
  that builds a hostile image with `tests/discgen.py` or pysacd's `tests/sacdgen.py`. Don't
  send copyrighted disc contents or your library; a synthetic image is enough;
- what happens (crash, hang, a file written, moved or deleted where it shouldn't be) and, if
  you know, why.

## What to expect

beets-pysacd is maintained by one person, so these are targets, not guarantees:

- **acknowledgement** within 7 days;
- **assessment** (confirmed or not, and how severe) within 14 days;
- **a fix** for a confirmed issue within 90 days, usually much sooner, released as a new
  version with the fix noted in the [changelog](CHANGELOG.md) and the release notes.

## Coordinated disclosure

Please keep the details private until a fixed release is out, or until 90 days after your
report, whichever comes first; if a fix needs longer, we'll agree a date with you. Once it's
fixed, the issue is published as a GitHub security advisory (with a CVE when it warrants one),
crediting you unless you'd rather not be named.

## Scope

beets-pysacd treats these as attacker-controlled:

- SACD, DVD and Blu-ray disc images, including their file systems, volume labels and disc
  text;
- MusicBrainz data and anything else received from the network.

Any of the following in the plugin's handling of those inputs is in scope:

- a crash, a hang or unbounded memory or disk use;
- an ISO deleted (`remove_iso: yes`) before its albums are verified in the library, or any
  other loss of the user's files;
- a file written, moved or deleted outside the staging directory and the beets library;
- disc or MusicBrainz text that reaches a shell, `subprocess` or `eval`, or drives the
  terminal;
- one disc's files or tags ending up in another's album.

How SACD images, PS3 network data and untrusted text are contained is pysacd's threat model,
[docs/security.md](https://github.com/aclater/pysacd/blob/master/docs/security.md). The
plugin's own DVD and Blu-ray reader, `beetsplug/_sacd_discimage.py`, bounds every read and
answers "unknown" for anything it can't parse.

Out of scope: beets itself and its other plugins (report those to
[beets](https://github.com/beetbox/beets/security)), and anything that needs an attacker who
can already change your beets configuration or library.
