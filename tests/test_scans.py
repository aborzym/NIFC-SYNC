import base64
import unittest

from core.scans import (
    ScanSourceMetadata,
    extract_scan_source_metadata,
    normalize_scan_url,
)


class ExtractScanSourceMetadataTests(unittest.TestCase):
    def test_extracts_krn_source_metadata(self):
        content = (
            "!!!COM: Śmietański, Emil Władysław\n"
            "!!!OTL: Na Wawelu\n"
            "!!!SMS-siglum: PL-Wtm\n"
            "!!!SMS-shelfmark: R 2017\n"
            "!!!NIFC-rismSourceID: 1001112891\n"
            "**kern\n"
            "*-\n"
        )
        api_file = {
            "name": ("pl-wtm--r-2017_smietanski-emil-wladyslaw-na-wawelu.krn"),
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }

        result = extract_scan_source_metadata(api_file)

        self.assertEqual(
            result,
            ScanSourceMetadata(
                rism_id="1001112891",
                siglum="PL-Wtm",
                shelfmark="R 2017",
                composer=("Śmietański, Emil Władysław"),
                title="Na Wawelu",
            ),
        )

    def test_uses_filename_siglum_when_metadata_is_missing(
        self,
    ):
        content = "!!!OTL: Missa\n!!!SMS-shelfmark: Kk.I.3\n**kern\n*-\n"
        api_file = {
            "name": ("pl-kk--kk-i-3--052-003_anonim--missa-agnus-dei.krn"),
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }

        result = extract_scan_source_metadata(api_file)

        self.assertEqual(
            result.siglum,
            "PL-KK",
        )
        self.assertEqual(
            result.shelfmark,
            "Kk.I.3",
        )


class NormalizeScanUrlTests(unittest.TestCase):
    def test_polona_pages_identify_the_same_scan_source(self):
        base = "https://polona.pl/item-view/7b369fcb-3d2d-4fe7-920a-c05f46eb8643"

        self.assertEqual(
            normalize_scan_url(base + "?page=4"),
            normalize_scan_url(base + "?page=59"),
        )


if __name__ == "__main__":
    unittest.main()
