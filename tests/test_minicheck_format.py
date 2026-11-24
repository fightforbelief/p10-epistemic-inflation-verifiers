import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import minicheck_format_check as M  # noqa: E402


class TestPack(unittest.TestCase):
    def test_pack(self):
        self.assertEqual(M.pack([100, 100, 250, 10], 300), [[0, 1], [2, 3]])
        self.assertEqual(M.pack([500, 10], 400), [[0], [1]])  # oversize first sentence: no empty chunk


if __name__ == "__main__":
    unittest.main()
