[beets-pysacd](../../README.md) › [Documentation](../README.md) › Beets from a distribution package

# Beets from a distribution package

How to make the plugin importable when beets comes from a Linux distribution's package.

## Why the plugin may not load

The plugin must be importable by the Python that runs `beet`. With beets from a Linux
distribution's package, that is the system Python, and it may not look where `pip` installed
the plugin. Fedora's `/usr/bin/beet`, for example, runs `python3 -sP`, which leaves out both
`~/.local` and `/usr/local`, so beets reports that it can't load the `sacd` plugin.

## One environment for beets and the plugin

Install beets and the plugin into one environment of their own:

```sh
pipx install beets
pipx inject beets beets-pysacd
```

## Keeping the packaged beets

Or keep the packaged beets and add the directories pip installed the plugin into to its path,
for example on Fedora 44 (Python 3.14):

```sh
PYTHONPATH=/usr/local/lib/python3.14/site-packages:/usr/local/lib64/python3.14/site-packages beet version
```

pysacd's engine is under `lib64`. `beet version` lists `sacd` among the plugins when it loads.

## See also

- [Install](README.md)
- [User guide](../user-guide.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
