import tempfile
import unittest
from pathlib import Path

from core.configuration import (
    AppConfiguration,
    OrganizationPath,
)
from core.destinations import (
    find_legacy_scan_package_folder,
    resolve_asset_root,
    scan_package_folder_name,
)


class DestinationResolverTest(unittest.TestCase):
    def test_resolves_kubiczek_workflow_folders(self):
        configuration = AppConfiguration(
            destination=Path("/tmp/Kubiczek"),
            naming_profile="andrzej-kubiczek",
        )

        cases = (
            (
                "KRN-diplomatic",
                Path("/tmp/Kubiczek/2026/in progress/diplomatic"),
            ),
            (
                "KRN-modern",
                Path("/tmp/Kubiczek/2026/in progress/modern"),
            ),
            (
                "XML",
                Path("/tmp/Kubiczek/2026/in progress/XML"),
            ),
        )

        for workflow_name, expected in cases:
            with self.subTest(workflow_name=workflow_name):
                result = resolve_asset_root(
                    configuration,
                    "pl-sa--227_msza.krn",
                    "transcriptions",
                    workflow_name=workflow_name,
                    year=2026,
                )

                self.assertEqual(result, expected)

    def test_finds_legacy_scan_package_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination_folder = Path(temporary_directory)
            legacy_folder = destination_folder / "1483_Missa_in_D_DjVu.zip"
            legacy_folder.mkdir()

            self.assertEqual(
                find_legacy_scan_package_folder(
                    destination_folder,
                    "1483_Missa_in_D_DjVu.zip",
                ),
                legacy_folder,
            )
            self.assertIsNone(
                find_legacy_scan_package_folder(
                    destination_folder,
                    "nie-istnieje.zip",
                )
            )
            self.assertIsNone(
                find_legacy_scan_package_folder(
                    destination_folder,
                    "pakiet-bez-rozszerzenia",
                )
            )

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

    def test_resolves_relative_path_from_parent_directory(
        self,
    ):
        parent = Path("/home/marta/Pulpit")
        configuration = AppConfiguration(
            destination=parent,
            naming_profile="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-sa/transcriptions",
                    path=Path("Sandomierz.krn"),
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
            parent / "Sandomierz.krn",
        )

    def test_rejects_relative_path_without_parent_directory(
        self,
    ):
        configuration = AppConfiguration(
            naming_profile="marta-lawrence",
            organization_paths=(
                OrganizationPath(
                    key="libraries/pl-sa/scans",
                    path=Path("Sandomierz.źródła"),
                ),
            ),
        )

        result = resolve_asset_root(
            configuration,
            "pl-sa--227_msza.krn",
            "scans",
        )

        self.assertIsNone(result)

    def test_builds_scan_package_folder_name(self):
        self.assertEqual(
            scan_package_folder_name("1483_Missa_in_D_DjVu.zip"),
            "1483_Missa_in_D_DjVu",
        )
        self.assertEqual(
            scan_package_folder_name("pakiet.ZIP"),
            "pakiet",
        )
        self.assertEqual(
            scan_package_folder_name("WTM-r2017"),
            "WTM-r2017",
        )

    def test_rejects_unsafe_scan_package_folder_name(self):
        for filename in (
            "",
            "../pakiet.zip",
        ):
            with (
                self.subTest(filename=filename),
                self.assertRaisesRegex(
                    ValueError,
                    "Nieprawidłowa nazwa",
                ),
            ):
                scan_package_folder_name(filename)


if __name__ == "__main__":
    unittest.main()
