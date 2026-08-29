from pathlib import Path

import requests

from core.client import NifcClient, load_credentials
from core.catalog import (
    build_scan_indexes,
    get_available_workflows,
)
from core.filesystem import (
    format_file_size,
)
from core.inventory import build_storage_inventory
from core.scans import (
    find_scan_provider,
    get_part_number,
    get_scan_group_key,
)
from core.storage import is_mounted, mount_cifs
from core.sync import sync_transcriptions


def ask_yes_no(question):
    while True:
        answer = input(f"{question} [t/n]: ").strip().lower()

        if answer in {"t", "tak"}:
            return True

        if answer in {"n", "nie"}:
            return False

        print("Wpisz t albo n.")


def show_download_progress(
    downloaded_size,
    total_size,
):
    if total_size:
        percentage = downloaded_size / total_size * 100
        message = (
            f"\rPobieranie: {percentage:6.2f}% "
            f"({format_file_size(downloaded_size)}"
            f" / {format_file_size(total_size)})"
        )
    else:
        message = f"\rPobieranie: {format_file_size(downloaded_size)}"

    print(
        f"{message}\033[K",
        end="",
        flush=True,
    )


def main():
    credentials_file = Path.home() / ".nifccredentials"
    credentials = load_credentials(credentials_file)
    
    login = credentials["login"]
    password = credentials["password"]
    
    client = NifcClient()
    session = client.session
    
    response = client.login(login, password)
    
    if response.ok:
        user = response.json()
        print(f"\n✓ Zalogowano jako: {user['name']}")
    else:
        print("\n✗ Błąd logowania.")
        raise SystemExit
    
    
    files_response = client.get_files()
    
    if not files_response.ok:
        print(f"\n✗ Nie udało się pobrać plików z NIFC. Kod: {files_response.status_code}")
        raise SystemExit
    
    print("✓ Pobrano listę plików z NIFC.")
    
    data = files_response.json()
    
    
    available_workflows = get_available_workflows(data)
    scan_urls_by_group, scan_sources_by_url = build_scan_indexes(
        available_workflows
    )
    
    print("\nWybierz workflow:")
    
    for i, workflow in enumerate(available_workflows, start=1):
        print(f"{i}. {workflow['name']} ({len(workflow['files'])} plików)")
    
    while True:
        try:
            choice = int(input("\nNumer: "))
    
            if 1 <= choice <= len(available_workflows):
                selected = available_workflows[choice - 1]
                break
    
            print("Podaj numer z listy.")
    
        except ValueError:
            print("Podaj numer, nie tekst.")
    
    print(f"\nPliki w {selected['name']}:")
    
    for file in selected["files"]:
        print(file["name"])
    
    
    base_dir = Path.home() / "mac_transkrypcje"
    
    if not is_mounted(base_dir):
        print("\nMac nie jest zamontowany. Próbuję połączyć...")
    
        result = mount_cifs(
            base_dir,
            Path.home() / ".smbcredentials",
        )
    
        if result.returncode != 0:
            print("✗ Nie udało się zamontować folderu z Maca.")
            raise SystemExit
    
    print("✓ Folder z Maca jest dostępny.")
    
    inventory = build_storage_inventory(
        base_dir,
        scan_urls_by_group,
    )
    folder_names = inventory.folder_names
    existing_scans_by_url = inventory.existing_scans_by_url
    next_number = inventory.next_number

    downloaded_scan_packages = 0
    transcription_result = sync_transcriptions(
        selected,
        base_dir,
        folder_names,
        next_number,
    )
    target_folders = transcription_result.target_folders
    
    print("\nKontrola skanów:")
    
    selected_scan_groups = {}
    
    for api_file in selected["files"]:
        group_key = get_scan_group_key(api_file["name"])
    
        selected_scan_groups.setdefault(
            group_key,
            [],
        ).append(api_file)
    
    for group_key, group_files in selected_scan_groups.items():
        normalized_urls = scan_urls_by_group.get(
            group_key,
            set(),
        )
    
        print(f"\nGRUPA: {group_key}")
    
        if not normalized_urls:
            print("BRAK URL-scan — pomijam")
            continue
    
        if len(normalized_urls) > 1:
            print("NIEJEDNOZNACZNY URL-scan:")
    
            for normalized_url in sorted(normalized_urls):
                print(f"  {normalized_url}")
    
            print("POMIJAM — wymaga ręcznego sprawdzenia")
            continue
    
        normalized_url = next(iter(normalized_urls))
        source = scan_sources_by_url[normalized_url]
        existing_locations = existing_scans_by_url.get(
            normalized_url,
            {},
        )
    
        if existing_locations:
            print("SKANY JUŻ ISTNIEJĄ:")
    
            for folder, score_files in sorted(
                existing_locations.items(),
                key=lambda item: item[0].name,
            ):
                print(f"  FOLDER: {folder.name}")
                print(f"  LICZBA PLIKÓW: {len(score_files)}")
    
            continue
    
        primary_file = min(
            group_files,
            key=lambda api_file: (
                get_part_number(api_file["name"]),
                api_file["name"],
            ),
        )
        destination_folder = target_folders[primary_file["name"]]
    
        print("BRAK SKANÓW")
        print(f"FOLDER DOCELOWY: {destination_folder.name}")
        print(f"URL-scan: {source['url']}")
    
        provider = find_scan_provider(source["url"])
    
        if provider is None:
            print("BRAK OBSŁUGI AUTOMATYCZNEGO POBIERANIA DLA TEJ BIBLIOTEKI")
            continue
    
        try:
            download_info = provider.get_download_info(
                session,
                source["url"],
            )
        except requests.RequestException as error:
            print(f"NIE UDAŁO SIĘ POBRAĆ INFORMACJI O PAKIECIE: {error}")
            continue
        except ValueError as error:
            print(f"NIEPRAWIDŁOWY URL-scan: {error}")
            continue
    
        print(f"PAKIET: {download_info.filename}")
        print(f"FORMAT: {download_info.content_type or 'nieznany'}")
        print(f"ROZMIAR: {format_file_size(download_info.size)}")
    
        if not ask_yes_no("Pobrać teraz?"):
            print("POMIJAM POBIERANIE")
            continue
    
        try:
            scans_folder = provider.download_and_extract(
                session,
                download_info,
                destination_folder,
                show_download_progress,
            )
        except (
            requests.RequestException,
            OSError,
            ValueError,
        ) as error:
            print()
            print(f"NIE UDAŁO SIĘ POBRAĆ SKANÓW: {error}")
            continue
    
        downloaded_scan_packages += 1
    
        print()
        print(f"ZAPISANO SKANY: {scans_folder}")
    
    
    print("\n" + "─" * 32)
    print("GOTOWE")
    print(
        "Utworzono folderów:          "
        f"{transcription_result.created_count}"
    )
    print(
        "Pobrano transkrypcji:        "
        f"{transcription_result.downloaded_count}"
    )
    print(f"Pobrano pakietów skanów:     {downloaded_scan_packages}")
    print(
        "Pominięto transkrypcji:      "
        f"{transcription_result.skipped_count}"
    )
    print("─" * 32)


if __name__ == "__main__":
    main()
