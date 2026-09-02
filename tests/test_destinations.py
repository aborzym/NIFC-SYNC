import tempfile
import unittest
from pathlib import Path

from core.configuration import (
    AppConfiguration,
    OrganizationPath,
)
from core.destinations import resolve_asset_root


class DestinationResolverTest(unittest.TestCase):
    def test_resolves_marta_transcription_folder(self):
        configuration = AppConfiguration(
            naming_profile="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-sa/transcriptions",
                    path=Path("/tmp/Sandomierz.krn"),
                ),
            ),
        )

        result = resolve_asset_root(
            configuration,
            "pl-sa--227_msza.krn",
            "transcriptions",
        )

        self.assertEqual(
            result,
            Path("/tmp/Sandomierz.krn"),
        )

    def test_resolves_marta_scans_folder(self):
        configuration = AppConfiguration(
            naming_profile="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-wtm/scans",
                    path=Path("/tmp/WTM.źródła"),
                ),
            ),
        )

        result = resolve_asset_root(
            configuration,
            "pl-wtm--r-2017_utwor.krn",
            "scans",
        )

        self.assertEqual(
            result,
            Path("/tmp/WTM.źródła"),
        )

    def test_returns_none_for_unconfigured_library(self):
        configuration = AppConfiguration(
            naming_profile="marta-lawrence",
        )

        result = resolve_asset_root(
            configuration,
            "pl-cz--123_utwor.krn",
            "transcriptions",
        )

        self.assertIsNone(result)

    def test_returns_none_for_unknown_filename(self):
        configuration = AppConfiguration(
            naming_profile="marta-lawrence",
        )

        result = resolve_asset_root(
            configuration,
            "utwor-bez-prefiksu.krn",
            "scans",
        )

        self.assertIsNone(result)

    def test_uses_general_root_for_andrzej_profile(self):
        destination = Path("/tmp/transkrypcje")
        configuration = AppConfiguration(
            destination=destination,
            naming_profile="andrzej-borzym",
        )

        result = resolve_asset_root(
            configuration,
            "pl-sa--227_msza.krn",
            "transcriptions",
        )

        self.assertEqual(result, destination)

    def test_does_not_create_configured_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            future_path = Path(temporary) / "Sandomierz.źródła"
            configuration = AppConfiguration(
                naming_profile="marta-lawrence",
                organization_paths=(
                    OrganizationPath(
                        key="libraries/pl-sa/scans",
                        path=future_path,
                    ),
                ),
            )

            result = resolve_asset_root(
                configuration,
                "pl-sa--227_msza.krn",
                "scans",
            )

            self.assertEqual(result, future_path)
            self.assertFalse(future_path.exists())

    def test_rejects_unknown_asset_kind(self):
        configuration = AppConfiguration(
            naming_profile="marta-lawrence",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Nieznany rodzaj danych",
        ):
            resolve_asset_root(
                configuration,
                "pl-sa--227_msza.krn",
                "partytury",
            )


if __name__ == "__main__":
    unittest.main()
