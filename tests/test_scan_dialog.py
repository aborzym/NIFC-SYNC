import unittest

from gui.scan_dialog import ScanSelectionDialog


class ScaleColumnWidthsTest(unittest.TestCase):
    def test_fills_available_width_exactly(self):
        result = ScanSelectionDialog._scale_widths_to_total(
            [280, 170, 130, 220, 90, 80],
            1200,
        )

        self.assertEqual(sum(result), 1200)
        self.assertEqual(len(result), 6)
        self.assertTrue(all(width >= 50 for width in result))

    def test_preserves_minimum_width_for_other_columns(
        self,
    ):
        result = ScanSelectionDialog._scale_widths_to_total(
            [900, 20, 20, 20, 20, 20],
            700,
        )

        self.assertEqual(sum(result), 700)
        self.assertTrue(all(width >= 50 for width in result))
        self.assertGreater(
            result[0],
            max(result[1:]),
        )


if __name__ == "__main__":
    unittest.main()
