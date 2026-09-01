"""Andamio temporal de estilo: prohibe emojis y guiones largos en el repo.

Se borra cuando la limpieza del bloque 1 quede consolidada (ver plan).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCANNED_SUFFIXES = {
    ".py", ".md", ".ts", ".tsx", ".rs", ".g4", ".json", ".sh", ".css",
    ".html", ".txt", ".yal", ".yalp", ".yapar", ".cps", ".tex", ".toml",
    ".yml", ".yaml", ".mjs",
}

SKIPPED_DIRS = {
    "node_modules", ".git", "target", "__pycache__", "dist", ".venv",
    "venv", "generated", "output", "artifacts",
}

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE0F"
    "\u2705\u274C]"
)

LONG_DASH = re.compile("[\u2014\u2013]")


def _scanned_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        if any(part in SKIPPED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        yield path


def _hits(pattern):
    found = []
    for path in _scanned_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in pattern.findall(line):
                found.append(f"{path.relative_to(ROOT)}:{number}: {match!r}")
    return found


class TestRepoStyle(unittest.TestCase):
    def test_sin_emojis(self):
        found = _hits(EMOJI)
        self.assertEqual(found, [], "Emojis encontrados:\n" + "\n".join(found))

    def test_sin_guiones_largos(self):
        found = _hits(LONG_DASH)
        self.assertEqual(found, [], "Guiones largos encontrados:\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
