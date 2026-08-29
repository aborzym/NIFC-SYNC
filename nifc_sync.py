from pathlib import Path

from core.client import NifcClient, load_credentials
from core.catalog import (
    build_scan_indexes,
    get_available_workflows,
)
from core.filesystem import (
    format_file_size,
)
from core.inventory import build_storage_inventory
from core.scan_sync import sync_scans
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

    transcription_result = sync_transcriptions(
        selected,
        base_dir,
        folder_names,
        next_number,
    )
    target_folders = transcription_result.target_folders
    
    scan_result = sync_scans(
        selected,
        scan_urls_by_group,
        scan_sources_by_url,
        existing_scans_by_url,
        target_folders,
        session,
        should_download=lambda request: ask_yes_no("Pobrać teraz?"),
        progress_callback=show_download_progress,
    )
    
    
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
    print(
        "Pobrano pakietów skanów:     "
        f"{scan_result.downloaded_packages}"
    )
    print(
        "Pominięto transkrypcji:      "
        f"{transcription_result.skipped_count}"
    )
    print("─" * 32)


if __name__ == "__main__":
    main()
