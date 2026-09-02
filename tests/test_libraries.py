import unittest

from core.libraries import (
    detect_library_id,
    library_display_name,
    library_scans_path_key,
    library_transcriptions_path_key,
    list_known_libraries,
)


class LibrariesTest(unittest.TestCase):
    def test_detects_known_library_prefixes(self):
        examples = {
            "pl-wtm--r-2017_utwor.krn": "pl-wtm",
            "pl-sa--227-a-vi-31--001.krn": "pl-sa",
            "pl-cz--123_utwor.krn": "pl-cz",
            "pl-kk--kk-i-10--018.musicxml": "pl-kk",
        }

        for filename, expected in examples.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    detect_library_id(filename),
                    expected,
                )

    def test_detects_future_library_prefix(self):
        self.assertEqual(
            detect_library_id("/tmp/PL-XYZ--nowa-biblioteka.krn"),
            "pl-xyz",
        )

    def test_rejects_filename_without_library_prefix(self):
        self.assertIsNone(detect_library_id("utwor-bez-prefiksu.krn"))

    def test_returns_library_display_names(self):
        self.assertEqual(
            library_display_name("pl-wtm"),
            "WTM",
        )
        self.assertEqual(
            library_display_name("PL-SA"),
            "Sandomierz",
        )
        self.assertEqual(
            library_display_name("pl-cz"),
            "Częstochowa",
        )
        self.assertEqual(
            library_display_name("pl-kk"),
            "Kraków",
        )
        self.assertEqual(
            library_display_name("pl-xyz"),
            "PL-XYZ",
        )

    def test_builds_library_organization_path_keys(self):
        self.assertEqual(
            library_transcriptions_path_key("PL-SA"),
            "libraries/pl-sa/transcriptions",
        )
        self.assertEqual(
            library_scans_path_key("PL-SA"),
            "libraries/pl-sa/scans",
        )

    def test_lists_known_libraries_for_configuration(self):
        self.assertEqual(
            list_known_libraries(),
            (
                ("pl-wtm", "WTM"),
                ("pl-sa", "Sandomierz"),
                ("pl-cz", "Częstochowa"),
                ("pl-kk", "Kraków"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
