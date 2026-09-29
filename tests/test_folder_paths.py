import tempfile
import unittest
from pathlib import Path

from folder_paths import localized_folder


class LocalizedFolderTests(unittest.TestCase):
    def test_moves_legacy_folder_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'old'
            legacy.mkdir()
            (legacy / 'record.txt').write_text('保留', encoding='utf-8')
            result = localized_folder('中文資料', 'old', root=root)
            self.assertEqual(result, root / '中文資料')
            self.assertEqual((result / 'record.txt').read_text(encoding='utf-8'), '保留')
            self.assertFalse(legacy.exists())

    def test_merges_without_overwriting_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'old'
            current = root / '中文資料'
            legacy.mkdir()
            current.mkdir()
            (legacy / 'old-only.txt').write_text('舊', encoding='utf-8')
            (legacy / 'same.txt').write_text('舊值', encoding='utf-8')
            (current / 'same.txt').write_text('新值', encoding='utf-8')
            localized_folder('中文資料', 'old', root=root)
            self.assertEqual((current / 'old-only.txt').read_text(encoding='utf-8'), '舊')
            self.assertEqual((current / 'same.txt').read_text(encoding='utf-8'), '新值')

