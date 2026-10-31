import json

from PySide6.QtCore import QSettings

from core.settlement_sync import exchange, materialize, record_changes


class SettlementStore:
    def __init__(self, configuration_store):
        account_id = configuration_store.active_account_id()
        if not account_id:
            raise ValueError("Najpierw skonfiguruj konto NIFC.")
        self.settings = configuration_store.settings
        self.key = f"accounts/{account_id}/statistics/settlements"
        self.snapshot = None
        self.configuration_store = configuration_store
        self.events = {}
        self.sync_error = ""
        self.loaded = False

    @property
    def sync_folder(self):
        return str(self.settings.value(f"{self.key}/sync_folder", "") or "")

    def set_sync_folder(self, folder):
        self.settings.setValue(f"{self.key}/sync_folder", str(folder))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError("Nie udało się zapisać folderu synchronizacji.")

    def load(self):
        raw = self.settings.value(self.key, "")
        if not raw:
            data = {"version": 1, "settlements": {}, "approved_matches": []}
        else:
            data = json.loads(str(raw))

        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Nieobsługiwany format zapisanych rozliczeń.")

        settlements = data["settlements"]
        approvals = data["approved_matches"]
        if not isinstance(settlements, dict) or not isinstance(approvals, list):
            raise TypeError("Nieprawidłowy zapis rozliczeń.")

        for settlement in settlements.values():
            if not isinstance(settlement, dict):
                raise TypeError("Nieprawidłowy dokument rozliczenia.")
            if not isinstance(settlement.get("entries"), list):
                raise TypeError("Nieprawidłowa lista pozycji rozliczenia.")

        approved = set()
        for identity in approvals:
            if not isinstance(identity, list) or len(identity) != 7:
                raise ValueError("Nieprawidłowe zapisane zatwierdzenie.")
            approved.add(tuple(identity))

        snapshot = data.get("snapshot")
        if snapshot is not None:
            if not isinstance(snapshot, dict):
                raise TypeError("Nieprawidłowy zapis statystyk.")
            if not isinstance(snapshot.get("entries"), list):
                raise TypeError("Nieprawidłowa lista zapisanych statystyk.")
            if not isinstance(snapshot.get("start_date"), str):
                raise TypeError("Nieprawidłowa data początku statystyk.")
            if not isinstance(snapshot.get("refreshed_at"), str):
                raise TypeError("Nieprawidłowy czas odświeżenia.")
        self.snapshot = snapshot
        self.events = data.get("sync_events")
        if self.events is None:
            self.events = record_changes({}, settlements, approved)
            backup_key = f"{self.key}/before_sync"
            if raw and not self.settings.contains(backup_key):
                self.settings.setValue(backup_key, raw)
        if not isinstance(self.events, dict):
            raise TypeError("Nieprawidłowy dziennik synchronizacji.")
        materialize(self.events)
        self.loaded = True
        self._persist()  # Durable local migration before attempting exchange.
        self._exchange()
        return self._values()

    def save(self, settlements, approved_matches):
        if not self.loaded:
            self.load()
        self.events = record_changes(self.events, settlements, approved_matches)
        self._persist()
        self._exchange()

    def _values(self):
        values, _ = materialize(self.events)
        return values["settlement"], {tuple(x) for x in values["approval"].values()}

    def synchronize(self, settlements, approved_matches):
        self.save(settlements, approved_matches)
        return self._values()

    def _exchange(self):
        self.sync_error = ""
        if not self.sync_folder:
            return
        try:
            self.events = exchange(
                self.sync_folder,
                self.configuration_store.load().nifc_username,
                self.events,
            )
            self._persist()
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.sync_error = str(error)

    def _persist(self):
        settlements, approved_matches = self._values()
        payload = json.dumps(
            {
                "version": 1,
                "settlements": settlements,
                "approved_matches": sorted(approved_matches),
                "snapshot": self.snapshot,
                "sync_events": self.events,
            },
            ensure_ascii=False,
        )
        self.settings.setValue(self.key, payload)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError("Nie udało się zapisać rozliczeń na dysku.")
