"""scripts/lock.py: every run moves pysacd to its newest release (#90)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import lock  # noqa: E402


class LockCommands(unittest.TestCase):
    def compile_commands(self) -> dict[str, list[str]]:
        """The uv command for each lock, without running uv or touching the repository's locks."""
        commands: dict[str, list[str]] = {}

        def run(cmd, **kwargs):
            out = Path(cmd[cmd.index("-o") + 1])
            commands[out.parent.name] = cmd
            out.write_text("")

        with tempfile.TemporaryDirectory() as d:
            shutil.copy(ROOT / "pyproject.toml", d)
            for name in ("latest", "oldest", "fuzz"):
                Path(d, "locks", name).mkdir(parents=True)
            with (mock.patch.object(lock, "ROOT", Path(d)),
                  mock.patch.object(lock.shutil, "which", return_value="uv"),
                  mock.patch.object(lock.subprocess, "run", side_effect=run),
                  mock.patch("builtins.print")):
                self.assertEqual(lock.main(), 0)
        return commands

    def test_pysacd_moves_to_its_newest_release_in_every_lock(self):
        # uv keeps a version already in the output file unless told to upgrade it, so without
        # this a rerun left the "pysacd release" legs on an old pysacd
        commands = self.compile_commands()
        self.assertEqual(set(commands), {"latest", "oldest", "fuzz"})
        for name, cmd in commands.items():
            self.assertIn("--upgrade-package=pysacd", cmd, name)

    def test_nothing_else_is_upgraded(self):
        for name, cmd in self.compile_commands().items():
            upgrades = [a for a in cmd if a.startswith("--upgrade")]
            self.assertEqual(upgrades, ["--upgrade-package=pysacd"], name)


if __name__ == "__main__":
    unittest.main()
