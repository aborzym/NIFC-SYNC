import base64
import os
import re
import subprocess
from pathlib import Path

import requests

from core.client import NifcClient, load_credentials
from core.filesystem import (
    find_existing_scores,
    find_existing_transcriptions,
    format_file_size,
)
from core.scans import (
    extract_scan_url,
    find_scan_provider,
    folder_matches_scan_group,
    get_part_number,
    get_scan_group_key,
    normalize_scan_url,
)


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


allowed_workflows = [
    "XML",
    "KRN-diplomatic",
    "KRN-modern",
]

available_workflows = [
    workflow for workflow in data["workflows"] if workflow["name"] in allowed_workflows
]

scan_urls_by_group = {}
scan_sources_by_url = {}

for workflow in available_workflows:
    for api_file in workflow["files"]:
        scan_url = extract_scan_url(api_file)

        if not scan_url:
            continue

        group_key = get_scan_group_key(api_file["name"])
        normalized_url = normalize_scan_url(scan_url)

        scan_urls_by_group.setdefault(
            group_key,
            set(),
        ).add(normalized_url)

        source = scan_sources_by_url.setdefault(
            normalized_url,
            {
                "url": scan_url,
                "groups": set(),
            },
        )

        source["groups"].add(group_key)

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

if not os.path.ismount(base_dir):
    print("\nMac nie jest zamontowany. Próbuję połączyć...")

    result = subprocess.run(
        [
            "sudo",
            "mount.cifs",
            "//Mac-Studio-Andrzej.local/TRANSKRYPCJE 2026",
            str(base_dir),
            "-o",
            f"credentials={Path.home() / '.smbcredentials'},vers=3.0,uid={os.getuid()},gid={os.getgid()}",
        ],
        check=False,
    )

    if result.returncode != 0:
        print("✗ Nie udało się zamontować folderu z Maca.")
        raise SystemExit

print("✓ Folder z Maca jest dostępny.")

folder_names = [p.name for p in base_dir.iterdir() if p.is_dir()]

scan_folders_by_url = {}

for folder_name in folder_names:
    for group_key, normalized_urls in scan_urls_by_group.items():
        if not folder_matches_scan_group(
            folder_name,
            group_key,
        ):
            continue

        for normalized_url in normalized_urls:
            scan_folders_by_url.setdefault(
                normalized_url,
                set(),
            ).add(base_dir / folder_name)

existing_scans_by_url = {}

for normalized_url, folders in scan_folders_by_url.items():
    for folder in folders:
        existing_scores = find_existing_scores(folder)

        if not existing_scores:
            continue

        existing_scans_by_url.setdefault(
            normalized_url,
            {},
        )[folder] = existing_scores


missing = []

number_pattern = re.compile(r"(?<!\d)(\d{3})\s*-\s*")

numbers = []

for folder in folder_names:
    match = number_pattern.search(folder)
    if match:
        numbers.append(int(match.group(1)))

next_number = max(numbers, default=0) + 1

workflow_codes = {
    "XML": "XML",
    "KRN-modern": "M",
    "KRN-diplomatic": "D",
}

workflow_code = workflow_codes.get(selected["name"])

created_count = 0
downloaded_count = 0
skipped_count = 0
downloaded_scan_packages = 0

target_folders = {}

print("\nPorównanie:")

for file in selected["files"]:
    api_name = file["name"]
    api_stem = Path(api_name).stem

    match = next((folder for folder in folder_names if api_stem in folder), None)

    if match:
        print(f"ISTNIEJE: {api_name}")
        print(f"        -> {match}")

        existing_folder = base_dir / match

        target_folder = existing_folder

        existing_transcriptions = find_existing_transcriptions(
            target_folder,
            selected["name"],
        )

        if existing_transcriptions:
            skipped_count += 1
            names = ", ".join(path.name for path in existing_transcriptions)
            print(f"POMIJAM: transkrypcja już istnieje: {names}")
        else:
            file_content = base64.b64decode(file["content"])
            file_path = target_folder / api_name
            file_path.write_bytes(file_content)
            downloaded_count += 1
            print(f"ZAPISANO TRANSKRYPCJĘ: {file_path.name}")

    else:
        print(f"BRAK:    {api_name}")
        missing.append(file)

        folder_name = f"{next_number:03d} - {workflow_code} - {Path(api_name).stem}"

        new_folder = base_dir / folder_name

        target_folder = new_folder

        if not new_folder.exists():
            new_folder.mkdir()
            created_count += 1
            print(f"UTWORZONO FOLDER: {new_folder.name}")

        existing_transcriptions = find_existing_transcriptions(
            target_folder,
            selected["name"],
        )

        if existing_transcriptions:
            skipped_count += 1
            names = ", ".join(path.name for path in existing_transcriptions)
            print(f"POMIJAM: transkrypcja już istnieje: {names}")
        else:
            file_content = base64.b64decode(file["content"])
            file_path = target_folder / api_name
            file_path.write_bytes(file_content)
            downloaded_count += 1
            print(f"ZAPISANO TRANSKRYPCJĘ: {file_path.name}")

        next_number += 1
    target_folders[api_name] = target_folder

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
print(f"Utworzono folderów:          {created_count}")
print(f"Pobrano transkrypcji:        {downloaded_count}")
print(f"Pobrano pakietów skanów:     {downloaded_scan_packages}")
print(f"Pominięto transkrypcji:      {skipped_count}")
print("─" * 32)
