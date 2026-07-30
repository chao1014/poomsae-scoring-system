import unittest

from scoring import excluded_extreme_ids, format_score, trimmed_average


class ScoringTests(unittest.TestCase):
    def test_supported_judge_counts(self):
        accuracy = [2.8, 3.2, 3.4, 3.6, 3.8, 4.0, 3.0]
        presentation = [5.8, 4.8, 5.0, 5.2, 5.4, 5.6, 6.0]
        expected = {
            1: (2.800, 5.800, 8.300),
            3: (3.133, 5.200, 8.033),
            5: (3.400, 5.200, 8.300),
            7: (3.400, 5.400, 8.500),
        }

        for judge_count, (expected_acc, expected_pres, expected_final) in expected.items():
            with self.subTest(judge_count=judge_count):
                avg_acc = trimmed_average(accuracy[:judge_count])
                avg_pres = trimmed_average(presentation[:judge_count])
                final_score = avg_acc + avg_pres - 0.3
                self.assertAlmostEqual(avg_acc, expected_acc, places=3)
                self.assertAlmostEqual(avg_pres, expected_pres, places=3)
                self.assertAlmostEqual(final_score, expected_final, places=3)

    def test_extreme_ids_match_trimmed_total_presentation(self):
        presentation_by_judge = {
            1: 5.8,
            2: 4.8,
            3: 5.0,
            4: 5.2,
            5: 5.4,
        }
        self.assertEqual(excluded_extreme_ids(presentation_by_judge), {1, 2})

    def test_tied_extremes_remove_one_judge_at_each_end(self):
        tied_scores = {1: 5.0, 2: 5.0, 3: 5.0, 4: 5.0, 5: 5.0}
        self.assertEqual(excluded_extreme_ids(tied_scores), {1, 2})

    def test_score_format_is_always_three_decimals(self):
        self.assertEqual(format_score(8.5), "8.500")
        self.assertEqual(format_score(10), "10.000")


if __name__ == "__main__":
    unittest.main()
