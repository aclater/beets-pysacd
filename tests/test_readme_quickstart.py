"""scripts/readme_quickstart.py: the Quick start's sh blocks are the steps; a non-sh block another
platform runs (marked `docs-run: skip=`, the Windows PowerShell commands) is skipped with a note;
any other non-sh block still stops the run, and a marked sh block is still a step."""

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import readme_quickstart as qs  # noqa: E402

README = """# T

## Quick start

1. Install.

   ```sh
   pip install beets beets-pysacd
   ```

   On Windows:

   {marker}
   ```powershell
   py -m pip install beets beets-pysacd
   ```

2. Import.

   <!-- docs-run: skip="interactive" -->
   ```sh
   beet sacd-import album.iso
   ```

## Next
"""
MARKER = '<!-- docs-run: skip="Windows: PowerShell" -->'


class SkipMarkedBlocks(unittest.TestCase):
    def steps(self, text):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            return qs.steps(text), out.getvalue()

    def test_marked_powershell_block_is_skipped_with_a_note(self):
        (blocks, _), note = self.steps(README.format(marker=MARKER))
        self.assertEqual(blocks, [["pip install beets beets-pysacd"], ["beet sacd-import album.iso"]])
        self.assertIn("skipping a ```powershell block", note)

    def test_unmarked_powershell_block_still_stops_the_run(self):
        with self.assertRaises(SystemExit) as stop:
            self.steps(README.format(marker=""))
        self.assertIn("```powershell block", str(stop.exception))

    def test_marker_must_be_the_line_before_the_block(self):
        with self.assertRaises(SystemExit):
            self.steps(README.format(marker=MARKER + "\n\n   Some prose in between."))

    def test_a_marker_without_skip_does_not_skip(self):
        with self.assertRaises(SystemExit):
            self.steps(README.format(marker="<!-- docs-run: packages=python3 -->"))

    def test_the_repository_readme_parses(self):
        (blocks, _), _ = self.steps((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertTrue(blocks)


if __name__ == "__main__":
    unittest.main()
