import base64
import unittest

from core.scans import (
    ScanSourceMetadata,
    extract_scan_source_metadata,
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


if __name__ == "__main__":
    unittest.main()
