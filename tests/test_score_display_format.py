import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ScoreDisplayFormatTests(unittest.TestCase):
    def test_browser_score_outputs_use_three_decimals(self):
        source = (PROJECT_ROOT / "static" / "main.js").read_text(encoding="utf-8")

        for expression in ("chungR1", "hongR1", "chungR2", "hongR2"):
            self.assertIn(f"{expression}.toFixed(3)", source)
            self.assertNotIn(f"{expression}.toFixed(2)", source)

        self.assertNotIn("displayScore === '10.000'", source)

    def test_controller_judge_totals_use_three_decimals(self):
        source = (PROJECT_ROOT / "gui_main.py").read_text(encoding="utf-8")

        self.assertIn("data.get('total', 0.0):.3f", source)
        self.assertIn("data.get('hong_total', 0.0):.3f", source)
        self.assertNotIn("data.get('total', 0.0):.2f", source)
        self.assertNotIn("data.get('hong_total', 0.0):.2f", source)


if __name__ == "__main__":
    unittest.main()
