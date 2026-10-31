"""Immutable changes shared through a locally synchronized directory."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4


def validate_event(event):
    if not isinstance(event, dict) or event.get("version") != 1:
        raise ValueError("Nieobsługiwany zapis synchronizacji rozliczeń.")
    if event.get("kind") not in ("settlement", "approval"):
        raise ValueError("Nieprawidłowy rodzaj zmiany rozliczeń.")
    if not isinstance(event.get("key"), str):
        raise TypeError("Nieprawidłowy identyfikator rozliczenia.")
    removed = event.get("removed")
    if not isinstance(removed, list) or not all(isinstance(x, str) for x in removed):
        raise ValueError("Nieprawidłowy zapis usunięcia rozliczenia.")
    value = event.get("value")
    if value is not None:
        if event["kind"] == "settlement":
            if not isinstance(value, dict) or not isinstance(
                value.get("entries"), list
            ):
                raise ValueError("Nieprawidłowe pozycje rozliczenia.")
            if not isinstance(value.get("performer"), str) or not isinstance(
                value.get("total"), int
            ):
                raise ValueError("Nieprawidłowy dokument rozliczenia.")
            for item in value["entries"]:
                if (
                    not isinstance(item, dict)
                    or not all(
                        isinstance(item.get(k), str) for k in ("scheme", "file_name")
                    )
                    or not all(
                        type(item.get(k)) is int for k in ("tranche", "note_count")
                    )
                ):
                    raise ValueError("Nieprawidłowa pozycja rozliczenia.")
        elif (
            not isinstance(value, list)
            or len(value) != 7
            or not all(isinstance(value[i], str) for i in (0, 1, 2, 4, 5))
            or not all(type(value[i]) is int for i in (3, 6))
        ):
            raise ValueError("Nieprawidłowe zatwierdzenie dopasowania.")


def materialize(events):
    removed = set()
    for event in events.values():
        validate_event(event)
        removed.update(event["removed"])
    values = {"settlement": {}, "approval": {}}
    tags = {}
    for tag, event in sorted(events.items()):
        if tag in removed or event["value"] is None:
            continue
        kind, key, value = event["kind"], event["key"], event["value"]
        previous = values[kind].get(key)
        if previous is not None and previous != value:
            raise ValueError(
                "Sprzeczne wersje tego samego rozliczenia. Zachowano oba zapisy."
            )
        values[kind][key] = value
        tags.setdefault((kind, key), []).append(tag)
    return values, tags


def approval_key(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def record_changes(events, settlements, approvals):
    values, tags = materialize(events)
    wanted = {
        "settlement": settlements,
        "approval": {approval_key(x): list(x) for x in approvals},
    }
    result = dict(events)
    for kind, wanted_values in wanted.items():
        for key in values[kind].keys() | wanted_values.keys():
            old, new = values[kind].get(key), wanted_values.get(key)
            if old != new:
                event = {
                    "version": 1,
                    "kind": kind,
                    "key": key,
                    "value": new,
                    "removed": tags.get((kind, key), []),
                }
                validate_event(event)
                result[uuid4().hex] = json.loads(json.dumps(event))
    return result


def exchange(folder, username, events):
    root = Path(folder)
    if not root.is_dir():
        raise OSError("Folder synchronizacji jest niedostępny.")
    if not username.strip():
        raise ValueError("Brak loginu NIFC dla synchronizacji.")
    account = hashlib.sha256(username.strip().casefold().encode()).hexdigest()
    directory = root / "settlements-v1" / account
    directory.mkdir(parents=True, exist_ok=True)
    merged = dict(events)
    # Read every JSON, including conflict copies produced by sync clients.
    for path in directory.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        tag, event = record["id"], record["event"]
        if (
            not isinstance(tag, str)
            or len(tag) != 32
            or any(c not in "0123456789abcdef" for c in tag)
        ):
            raise ValueError("Nieprawidłowy identyfikator zmiany.")
        validate_event(event)
        if tag in merged and merged[tag] != event:
            raise ValueError("Sprzeczna kopia zmiany rozliczeń.")
        merged[tag] = event
    materialize(merged)  # Validate before publishing anything.
    for tag, event in merged.items():
        target = directory / f"{tag}.json"
        if target.exists():
            continue
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"id": tag, "event": event}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return merged
