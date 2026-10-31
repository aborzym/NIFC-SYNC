"""Single-authority folder numbering; replicas submit requests, never numbers."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QLockFile

CODES = {"KRN-diplomatic": "D", "KRN-modern": "M", "XML": "XML"}
FOLDER = re.compile(r"^(\d{3,}|TMP) - (D|M|XML) - (.+)$")


def identity(code, stem):
    if code not in CODES.values() or not stem or any(c in stem for c in "/\\\0"):
        raise ValueError("Nieprawidłowa nazwa projektu w indeksie.")
    return f"{code} - {stem}"


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_catalog(path):
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Nieobsługiwany indeks folderów.")
    if not isinstance(data.get("owner"), str) or not data["owner"]:
        raise ValueError("Brak identyfikatora głównego katalogu.")
    entries = data.get("entries")
    if not isinstance(entries, dict):
        raise TypeError("Nieprawidłowa lista folderów.")
    numbers = set()
    for key, name in entries.items():
        match = FOLDER.fullmatch(name) if isinstance(name, str) else None
        if not match or match[1] == "TMP" or identity(match[2], match[3]) != key:
            raise ValueError("Nieprawidłowy przydział numeru folderu.")
        number = int(match[1])
        if number in numbers:
            raise ValueError("Powtórzony numer folderu w indeksie.")
        numbers.add(number)
    return data


def merge_catalogs(local, remote):
    if local and remote and local["owner"] != remote["owner"]:
        raise ValueError("Wybrano indeks innego katalogu głównego.")
    result = json.loads(
        json.dumps(
            local or remote or {"version": 1, "owner": uuid4().hex, "entries": {}}
        )
    )
    for key, name in (remote or {}).get("entries", {}).items():
        old = result["entries"].get(key)
        if old is not None and old != name:
            raise ValueError(f"Sprzeczne przydziały numeru: {key}")
        result["entries"][key] = name
    return result


class FolderIndex:
    def __init__(self, configuration, base_dir, log=print):
        self.configuration = configuration
        self.base = Path(base_dir)
        self.role = configuration.folder_index_role
        self.log = log
        self.catalog = None
        self.entries = {}
        self.folders = {}
        self.used_numbers = set()
        self.local_numbers = {}
        self.shared = None

    def __enter__(self):
        if self.role not in ("master", "replica"):
            raise ValueError("Nieznany tryb numeracji folderów.")
        if self.configuration.naming_profile != "andrzej-borzym":
            raise ValueError("Wspólna numeracja wymaga profilu Andrzej Borzym.")
        if not self.base.is_dir():
            raise OSError("Katalog projektów jest niedostępny.")
        username = self.configuration.nifc_username.strip().casefold()
        if not username:
            raise ValueError("Wspólna numeracja wymaga loginu NIFC.")
        account = hashlib.sha256(username.encode()).hexdigest()
        self.cache = self.base / ".nifc-folder-index" / account / "catalog.json"
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(self.cache.with_suffix(".lock")))
        if not self.lock.tryLock(0):
            raise OSError("Inna operacja korzysta z indeksu folderów.")
        try:
            self._load()
        except Exception:
            self.lock.unlock()
            raise
        return self

    def __exit__(self, *_args):
        self.lock.unlock()

    def _load(self):
        local = read_catalog(self.cache)
        root_text = self.configuration.folder_index_directory
        root = Path(root_text) if root_text else None
        remote = None
        if root is not None and root.is_dir():
            self.shared = root / "folders-v1" / self.cache.parent.name
            self.shared.mkdir(parents=True, exist_ok=True)
            remote = read_catalog(self.shared / "catalog.json")
        elif self.role == "master":
            raise OSError(
                "Folder wspólnej listy jest niedostępny. Numeracja wstrzymana."
            )
        else:
            self.log(
                "Lista Maca niedostępna — używam zapisanych przydziałów i nazw TMP."
            )
        if self.role == "master":
            owner_path = self.cache.with_name("owner.json")
            if owner_path.exists():
                owner = json.loads(owner_path.read_text(encoding="utf-8"))
            elif local or remote:
                raise ValueError(
                    "Ten indeks ma już katalog główny. Nie można ustanowić drugiego."
                )
            else:
                owner = uuid4().hex
                atomic_json(owner_path, owner)
            if any(data and data["owner"] != owner for data in (local, remote)):
                raise ValueError("Ten komputer nie jest właścicielem głównego indeksu.")
            if local is None:
                local = {"version": 1, "owner": owner, "entries": {}}
        if self.role == "master" or local or remote:
            self.catalog = merge_catalogs(local, remote)
            self.entries = self.catalog["entries"]
        self._scan_local()
        if self.role == "master":
            self._reserve_requests()
        self._validate_numbers()
        if self.catalog is not None:
            atomic_json(self.cache, self.catalog)
        if self.role == "master":
            atomic_json(self.shared / "catalog.json", self.catalog)
        self._rename_assigned()
        for key in self.folders:
            if key not in self.entries:
                self._request(key)

    def _scan_local(self):
        for path in sorted(self.base.iterdir()):
            if not path.is_dir() or path.is_symlink():
                continue
            # Reserve even numbers of folders with an unrecognized naming format.
            number = re.match(r"^(\d+)\s*-", path.name)
            if number:
                parsed_number = int(number[1])
                if parsed_number in self.local_numbers:
                    raise ValueError(
                        f"Powtórzony lokalny numer folderu: {parsed_number}"
                    )
                self.local_numbers[parsed_number] = path.name
                self.used_numbers.add(parsed_number)
            match = FOLDER.fullmatch(path.name)
            if not match:
                continue
            key = identity(match[2], match[3])
            if key in self.folders:
                raise ValueError(f"Dwa lokalne foldery tego samego projektu: {key}")
            self.folders[key] = path.name
            if self.role == "master" and match[1] != "TMP":
                old = self.entries.get(key)
                if old is not None and old != path.name:
                    raise ValueError(f"Numer na Macu różni się od indeksu: {path.name}")
                self.entries[key] = path.name

    def _validate_numbers(self):
        assigned = {}
        for key, name in self.entries.items():
            number = int(name.split(" - ", 1)[0])
            if number in assigned and assigned[number] != key:
                raise ValueError(f"Kolizja numeru {number} w katalogu głównym.")
            assigned[number] = key
            self.used_numbers.add(number)
            local_name = self.local_numbers.get(number)
            if local_name is not None and local_name != name:
                raise ValueError(
                    f"Numer {number} zajmuje inny lokalny folder: {local_name}"
                )

    def _reserve_requests(self):
        requests = set(self.folders)
        for path in (self.shared / "requests").glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("Nieprawidłowe zgłoszenie nowego folderu.")
            requests.add(identity(data["code"], data["stem"]))
        self._validate_numbers()
        for key in sorted(requests):
            if key not in self.entries:
                self._allocate(key)

    def _allocate(self, key):
        number = max(self.used_numbers, default=0) + 1
        self.entries[key] = f"{number:03d} - {key}"
        self.used_numbers.add(number)

    def _request(self, key):
        if self.shared is None:
            return  # The TMP folder itself is the durable pending request.
        code, stem = key.split(" - ", 1)
        digest = hashlib.sha256(key.encode()).hexdigest()
        try:
            atomic_json(
                self.shared / "requests" / f"{digest}.json",
                {"version": 1, "code": code, "stem": stem},
            )
        except OSError as error:
            self.log(f"Zgłoszenie numeru czeka lokalnie: {error}")

    def _rename_assigned(self):
        changes = []
        for key, old in self.folders.items():
            new = self.entries.get(key)
            if new and old != new:
                if not old.startswith("TMP - "):
                    raise ValueError(f"Lokalny numer jest inny niż na Macu: {old}")
                target = self.base / new
                if target.exists() or target.is_symlink():
                    raise FileExistsError(
                        f"Nie nadpisuję istniejącego folderu: {target}"
                    )
                changes.append((key, old, new))
        for key, old, new in changes:
            (self.base / old).rename(self.base / new)
            self.folders[key] = new
            self.log(f"NADANO NUMER: {old} → {new}")

    def folder_for(self, workflow, stem):
        key = identity(CODES[workflow], stem)
        if key in self.folders:
            return self.folders[key]
        if key not in self.entries and self.role == "master":
            self._allocate(key)
            atomic_json(self.cache, self.catalog)
            atomic_json(self.shared / "catalog.json", self.catalog)
        name = self.entries.get(key, f"TMP - {key}")
        if key not in self.entries:
            self._request(key)
            self.log(f"NUMER TYMCZASOWY: {name} — czekam na przydział Maca.")
        target = self.base / name
        if target.is_symlink():
            raise ValueError(f"Folder projektu jest dowiązaniem: {target}")
        if target.exists() and not target.is_dir():
            raise FileExistsError(f"Nazwę folderu zajmuje plik: {target}")
        return name


def refresh_folder_index(configuration, log=print):
    if not configuration.folder_index_role:
        return
    if configuration.destination is None:
        raise ValueError("Najpierw wybierz katalog projektów.")
    with FolderIndex(configuration, configuration.destination, log) as index:
        log(f"Lista folderów: {len(index.entries)} przydziałów numerów.")
