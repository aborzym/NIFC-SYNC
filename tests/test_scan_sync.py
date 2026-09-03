import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.configuration import (
    AppConfiguration,
    OrganizationPath,
)
from core.libraries import (
    library_scans_path_key,
)
from core.scan_manifest import write_scan_manifest
from core.scan_sync import (
    ScanDownloadRequest,
    download_scan_plans,
    plan_scans,
)
from core.scans import get_scan_group_key


class DownloadScanPlansTest(unittest.TestCase):
    @patch("core.scan_sync.find_scan_provider")
    def test_skips_completed_marta_package_folder(
        self,
        find_provider,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent_folder = Path(temporary_directory)
            scans_root = parent_folder / "Sandomierz.źródła"
            package_folder = scans_root / "1483_Missa_in_D_DjVu"
            package_folder.mkdir(parents=True)
            (package_folder / "page.djvu").write_bytes(b"djvu-content")

            filename = "pl-sa--227-a-vi-31--001-005_anonim--msza-agnus-dei.krn"
            group_key = get_scan_group_key(filename)
            normalized_url = "sandomierz-1551"
            source_url = (
                "https://bc.bdsandomierz.pl/publication/1583/edition/1551/content"
            )
            archive_name = "1483_Missa_in_D_DjVu.zip"
            write_scan_manifest(
                package_folder,
                source_url,
                archive_name,
            )

            provider = Mock()
            provider.get_download_info.return_value = Mock(
                filename=archive_name,
                content_type="application/zip",
                size=1234,
            )
            find_provider.return_value = provider
            configuration = AppConfiguration(
                destination=parent_folder,
                naming_profile="marta-lawrence",
                organization_paths=(
                    OrganizationPath(
                        key=library_scans_path_key("pl-sa"),
                        path=Path("Sandomierz.źródła"),
                    ),
                ),
            )

            plans = plan_scans(
                selected_workflow={
                    "files": [
                        {
                            "name": filename,
                        }
                    ],
                },
                scan_urls_by_group={
                    group_key: {
                        normalized_url,
                    },
                },
                scan_sources_by_url={
                    normalized_url: {
                        "url": source_url,
                    },
                },
                existing_scans_by_url={},
                target_folders={},
                session=Mock(),
                configuration=configuration,
                log=Mock(),
            )

            self.assertEqual(plans, ())

    @patch("core.scan_sync.find_scan_provider")
    def test_plans_repair_for_incomplete_marta_package(
        self,
        find_provider,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent_folder = Path(temporary_directory)
            scans_root = parent_folder / "Sandomierz.źródła"
            package_folder = scans_root / "1483_Missa_in_D_DjVu"
            package_folder.mkdir(parents=True)
            (package_folder / "page.djvu").write_bytes(b"djvu-content")

            filename = "pl-sa--227-a-vi-31--001-005_anonim--msza-agnus-dei.krn"
            group_key = get_scan_group_key(filename)
            normalized_url = "sandomierz-1551"
            source_url = (
                "https://bc.bdsandomierz.pl/publication/1583/edition/1551/content"
            )
            archive_name = "1483_Missa_in_D_DjVu.zip"
            write_scan_manifest(
                package_folder,
                source_url,
                archive_name,
            )
            (package_folder / "page.djvu").write_bytes(b"changed-djvu-content")

            provider = Mock()
            provider.get_download_info.return_value = Mock(
                filename=archive_name,
                content_type="application/zip",
                size=1234,
            )
            find_provider.return_value = provider
            configuration = AppConfiguration(
                destination=parent_folder,
                naming_profile="marta-lawrence",
                organization_paths=(
                    OrganizationPath(
                        key=library_scans_path_key("pl-sa"),
                        path=Path("Sandomierz.źródła"),
                    ),
                ),
            )

            plans = plan_scans(
                selected_workflow={
                    "files": [
                        {
                            "name": filename,
                        }
                    ],
                },
                scan_urls_by_group={
                    group_key: {
                        normalized_url,
                    },
                },
                scan_sources_by_url={
                    normalized_url: {
                        "url": source_url,
                    },
                },
                existing_scans_by_url={},
                target_folders={},
                session=Mock(),
                configuration=configuration,
                log=Mock(),
            )

            self.assertEqual(len(plans), 1)
            self.assertTrue(plans[0].is_incomplete)

    @patch("core.scan_sync.write_scan_manifest")
    def test_creates_scans_root_only_when_downloading(
        self,
        write_manifest,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent_folder = Path(temporary_directory)
            destination_folder = parent_folder / "Sandomierz.źródła"
            output_folder = destination_folder / "1483_Missa_in_D_DjVu"
            session = Mock()
            download_info = Mock(
                filename="1483_Missa_in_D_DjVu.zip",
            )
            provider = Mock()

            def download_and_extract(
                _session,
                _download_info,
                received_destination,
                _progress,
                output_folder_name,
            ):
                self.assertTrue(received_destination.is_dir())
                target = received_destination / output_folder_name
                target.mkdir()
                return target

            provider.download_and_extract.side_effect = download_and_extract
            request = ScanDownloadRequest(
                group_key="pl-sa--227-a-vi-31",
                transcription_name="pl-sa--utwor.krn",
                source_url="https://example.test/skany",
                destination_folder=destination_folder,
                download_info=download_info,
                provider=provider,
                is_incomplete=False,
                output_folder_name=("1483_Missa_in_D_DjVu"),
            )

            self.assertFalse(destination_folder.exists())

            result = download_scan_plans(
                session,
                (request,),
                log=Mock(),
            )

            self.assertTrue(output_folder.is_dir())
            self.assertEqual(
                result.downloaded_packages,
                1,
            )
            write_manifest.assert_called_once_with(
                output_folder,
                request.source_url,
                download_info.filename,
            )

    @patch("core.scan_sync.find_scan_provider")
    def test_skips_legacy_marta_package_folder(
        self,
        find_provider,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent_folder = Path(temporary_directory)
            scans_root = parent_folder / "Sandomierz.źródła"
            legacy_folder = scans_root / "1483_Missa_in_D_DjVu.zip"
            legacy_folder.mkdir(parents=True)

            filename = "pl-sa--227-a-vi-31--001-005_anonim--msza-agnus-dei.krn"
            group_key = get_scan_group_key(filename)
            normalized_url = "sandomierz-1551"
            source_url = (
                "https://bc.bdsandomierz.pl/publication/1583/edition/1551/content"
            )
            provider = Mock()
            provider.get_download_info.return_value = Mock(
                filename="1483_Missa_in_D_DjVu.zip",
                content_type="application/zip",
                size=1234,
            )
            find_provider.return_value = provider
            log = Mock()
            configuration = AppConfiguration(
                destination=parent_folder,
                naming_profile="marta-lawrence",
                organization_paths=(
                    OrganizationPath(
                        key=library_scans_path_key("pl-sa"),
                        path=Path("Sandomierz.źródła"),
                    ),
                ),
            )

            plans = plan_scans(
                selected_workflow={
                    "files": [
                        {
                            "name": filename,
                        }
                    ],
                },
                scan_urls_by_group={
                    group_key: {
                        normalized_url,
                    },
                },
                scan_sources_by_url={
                    normalized_url: {
                        "url": source_url,
                    },
                },
                existing_scans_by_url={},
                target_folders={},
                session=Mock(),
                configuration=configuration,
                log=log,
            )

            self.assertEqual(plans, ())
            log.assert_any_call(
                f"SKANY JUŻ ISTNIEJĄ W STARYM FOLDERZE: {legacy_folder}"
            )

    def test_skips_marta_library_without_scans_folder(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            filename = "pl-sa--227-a-vi-31--001-005_anonim--msza-agnus-dei.krn"
            group_key = get_scan_group_key(filename)
            normalized_url = "sandomierz-1551"
            log = Mock()
            configuration = AppConfiguration(
                destination=Path(temporary_directory),
                naming_profile="marta-lawrence",
            )

            plans = plan_scans(
                selected_workflow={
                    "files": [
                        {
                            "name": filename,
                        }
                    ],
                },
                scan_urls_by_group={
                    group_key: {
                        normalized_url,
                    },
                },
                scan_sources_by_url={
                    normalized_url: {
                        "url": (
                            "https://bc.bdsandomierz.pl/"
                            "publication/1583/edition/"
                            "1551/content"
                        ),
                    },
                },
                existing_scans_by_url={},
                target_folders={},
                session=Mock(),
                configuration=configuration,
                log=log,
            )

            self.assertEqual(plans, ())
            log.assert_any_call(
                "BRAK SKONFIGUROWANEGO FOLDERU SKANÓW DLA BIBLIOTEKI — POMIJAM"
            )

    @patch("core.scan_sync.write_scan_manifest")
    def test_uses_named_output_folder(
        self,
        write_manifest,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination_folder = Path(temporary_directory)
            output_folder = destination_folder / "1483_Missa_in_D_DjVu"
            session = Mock()
            provider = Mock()
            download_info = Mock(
                filename="1483_Missa_in_D_DjVu.zip",
            )
            provider.download_and_extract.return_value = output_folder
            request = ScanDownloadRequest(
                group_key="pl-sa--227-a-vi-31",
                transcription_name="pl-sa--utwor.krn",
                source_url="https://example.test/skany",
                destination_folder=destination_folder,
                download_info=download_info,
                provider=provider,
                is_incomplete=False,
                output_folder_name=("1483_Missa_in_D_DjVu"),
            )

            result = download_scan_plans(
                session,
                (request,),
            )

            provider.download_and_extract.assert_called_once_with(
                session,
                download_info,
                destination_folder,
                None,
                output_folder_name=("1483_Missa_in_D_DjVu"),
            )
            write_manifest.assert_called_once_with(
                output_folder,
                request.source_url,
                download_info.filename,
            )
            self.assertEqual(result.downloaded_packages, 1)

    @patch("core.scan_sync.find_scan_provider")
    def test_plans_marta_package_in_library_scans_folder(
        self,
        find_provider,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent_folder = Path(temporary_directory)
            filename = "pl-sa--227-a-vi-31--001-005_anonim--msza-agnus-dei.krn"
            group_key = get_scan_group_key(filename)
            normalized_url = "sandomierz-1551"
            source_url = (
                "https://bc.bdsandomierz.pl/publication/1583/edition/1551/content"
            )
            provider = Mock()
            provider.get_download_info.return_value = Mock(
                filename="1483_Missa_in_D_DjVu.zip",
                content_type="application/zip",
                size=1234,
            )
            find_provider.return_value = provider
            configuration = AppConfiguration(
                destination=parent_folder,
                naming_profile="marta-lawrence",
                organization_paths=(
                    OrganizationPath(
                        key=library_scans_path_key("pl-sa"),
                        path=Path("Sandomierz.źródła"),
                    ),
                ),
            )

            plans = plan_scans(
                selected_workflow={
                    "files": [
                        {
                            "name": filename,
                        }
                    ],
                },
                scan_urls_by_group={
                    group_key: {
                        normalized_url,
                    },
                },
                scan_sources_by_url={
                    normalized_url: {
                        "url": source_url,
                    },
                },
                existing_scans_by_url={},
                target_folders={},
                session=Mock(),
                configuration=configuration,
                log=Mock(),
            )

            self.assertEqual(len(plans), 1)
            self.assertEqual(
                plans[0].destination_folder,
                parent_folder / "Sandomierz.źródła",
            )
            self.assertEqual(
                plans[0].output_folder_name,
                "1483_Missa_in_D_DjVu",
            )


if __name__ == "__main__":
    unittest.main()
