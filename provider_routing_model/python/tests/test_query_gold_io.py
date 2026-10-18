"""Path guards for portable, non-following private artifact I/O."""

from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from query_gold.io import ensure_safe_path


class QueryGoldIoTests(unittest.TestCase):
    def test_safe_paths_allow_normal_parent_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "subdirectory" / ".." / "artifact.json"
            self.assertEqual(ensure_safe_path(target), root / "artifact.json")

    def test_rejects_windows_alternate_streams_and_reserved_components_before_stat(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for target in (
                root / "source::$DATA",
                root / ".env::$DATA",
                root / "CON.txt",
                root / "trailing.",
                root / "bad?.json",
            ):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    ensure_safe_path(target)

    def test_reparse_point_components_are_rejected_without_following_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            reparse = root / "junction"
            reparse.mkdir(parents=True)
            target = reparse / "source.json"
            original_lstat = Path.lstat
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

            def fake_lstat(path: Path) -> Any:
                if path == reparse:
                    return SimpleNamespace(
                        st_mode=stat.S_IFDIR,
                        st_file_attributes=reparse_flag,
                    )
                return original_lstat(path)

            with (
                patch.object(Path, "lstat", fake_lstat),
                self.assertRaisesRegex(ValueError, "reparse-point"),
            ):
                ensure_safe_path(target)


if __name__ == "__main__":
    unittest.main()
