[beets-pysacd](../../README.md) › [Documentation](../README.md) › Install on Windows

# Install on Windows

How to install beets and the plugin on Windows 11, turn the plugin on in beets' configuration,
and import a first SACD image (ISO), step by step.

**What was tested.** A stock Windows 11 Pro 25H2 (standard user account, long paths off) ran, on
2026-11-25: installing Python from python.org, `py -m pip install beets beets-pysacd`
(beets-pysacd 0.2.2, beets 2.14.1, pysacd 0.5.5), pipx, finding and editing `config.yaml` with
`beet config -p` and Notepad, and `beet sacd-info` and `beet sacd-import` on a real disc image
with Windows paths. A Music folder redirected to OneDrive was not tried.

## 1. Install Python

The plugin needs Python <!-- facts:python-min -->3.11<!-- /facts --> to 3.14, 64-bit: pysacd, which reads the discs, has its
Windows wheel for x86-64 only.

1. Download the Windows installer (64-bit) from
   [python.org](https://www.python.org/downloads/windows/) and run it.
2. On its first screen, tick **Add python.exe to PATH**, then choose **Install Now**.
3. Open a new PowerShell window (Start menu, type `PowerShell`) and check it:

   <!-- docs-run: skip="Windows: the py launcher exists only on Windows" -->
   ```powershell
   py --version
   ```

   *You should see* `Python 3.` and the version you installed.

## 2. Install beets and the plugin

In PowerShell:

<!-- docs-run: skip="Windows: PowerShell and the py launcher; the same pip install runs on Linux in the README's Quick start" -->
```powershell
py -m pip install beets beets-pysacd
beet version
```

*You should see* `beets version` and its number, your Python version and `plugins: musicbrainz`.
The first beets command also creates the library database, and may print a number of `Created
database backup` lines; that happens once.

Or, to keep beets apart from your other Python packages, install it with
[pipx](https://pipx.pypa.io/), with the plugin injected into beets' environment. Close and
reopen PowerShell after `ensurepath`:

<!-- docs-run: skip="Windows: PowerShell and the py launcher" -->
```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

<!-- docs-run: skip="Windows: run in a new PowerShell window after pipx ensurepath" -->
```powershell
pipx install beets
pipx inject beets beets-pysacd
```

## 3. Find beets' configuration file

On Windows, beets reads its configuration from `config.yaml` in the `beets` folder of your
roaming application data: `%APPDATA%\beets\config.yaml`, where `%APPDATA%` is the
`AppData\Roaming` folder in your user folder. The library database, `library.db`, is kept in the
same folder. Ask beets where the file is:

<!-- docs-run: skip="Windows: PowerShell; on Linux the path is ~/.config/beets/config.yaml" -->
```powershell
beet config -p
```

*You should see* the full path of `config.yaml`. beets creates the folder if it is missing, but
not the file.

## 4. Turn the plugin on

Open the file in Notepad:

<!-- docs-run: skip="Windows: Notepad and PowerShell" -->
```powershell
notepad (beet config -p)
```

If Notepad asks whether to create the file, choose **Yes**. That works the same from a path you
type yourself:

<!-- docs-run: skip="Windows: Notepad and PowerShell" -->
```powershell
notepad "$env:APPDATA\beets\config.yaml"
```

`beet config -e` is beets' own way to open the file, but on a stock Windows it shows the "Select an
app to open this .yaml file" window, because no program is set for `.yaml` files.

Type this into the file, then save it. It turns on the plugin, with beets' MusicBrainz plugin,
keeps the library in the Music folder of your user folder, and converts the stereo area to DSF:

```yaml
directory: ~/Music
plugins: musicbrainz sacd
sacd:
    areas: stereo
    format: dsf
```

YAML indents with spaces, never tabs. [Options and configuration](../options.md#settings) has
every `sacd:` setting.

## 5. Import a first SACD image

The commands use an SACD image at `C:\SACD\album.iso`; type your image's path instead. Check
that the plugin reads the disc:

<!-- docs-run: skip="Windows: PowerShell and Windows paths; the same command runs on Linux in the README's Quick start" -->
```powershell
beet sacd-info C:\SACD\album.iso
```

*You should see* the album, then each area with its tracks.

Import it:

<!-- docs-run: skip="Windows: PowerShell and Windows paths; interactive, as the importer asks to accept the MusicBrainz match" -->
```powershell
beet sacd-import C:\SACD\album.iso
```

The plugin converts the stereo area to DSF and hands it to the beets importer, which shows the
MusicBrainz release it found. Accept it, or pick another, as in any beets import. The tracks land
in the Music folder of your user folder; `beet ls -a` lists the album. The
[user guide](../user-guide.md) has the other commands.

## Windows paths

- **In the configuration file**, write paths with forward slashes (`D:/Music`) or `~` for your
  user folder (`~/Music`). Backslashes work unquoted or in single quotes (`'D:\Music'`), but not
  in double quotes, where YAML reads a backslash as the start of an escape.
- **On the command line**, quote a path with spaces: `beet sacd-import "C:\SACD\Kind of Blue.iso"`.
  A folder imports every image under it: `beet sacd-import C:\SACD`.
- **File names:** beets replaces the characters Windows can't use in a name (`<>:"?*|`), and
  pysacd writes Windows-safe names when it converts.
- **Long paths:** Windows limits a path to 260 characters unless long paths are turned on, and
  they are off by default. The plugin converts in a staging folder inside the library folder,
  and with pysacd 0.5.5 a track whose path there is longer than 260 characters fails; 0.5.5 gave
  `[WinError 206] The filename or extension is too long` from `pysacd convert`. pysacd 0.6.0 fixes this; until then keep the library folder short, such as
  `C:/Music`. pysacd's
  [install page](https://github.com/dsd-toolbox/pysacd/blob/master/docs/install/README.md)
  has the details.

## See also

- [Install](README.md): requirements and checking a download
- [User guide](../user-guide.md): `sacd-import`, `sacd-info` and the other commands
- [Options and configuration](../options.md): every option and setting
- [beets' configuration documentation](https://beets.readthedocs.io/en/stable/reference/config.html)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
