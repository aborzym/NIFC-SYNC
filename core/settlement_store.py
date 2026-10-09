import json

from PySide6.QtCore import QSettings


class SettlementStore:
    def __init__(self, configuration_store):
        account_id = configuration_store.active_account_id()
        if not account_id:
            raise ValueError("Najpierw skonfiguruj konto NIFC.")
        self.settings = configuration_store.settings
        self.key = f"accounts/{account_id}/statistics/settlements"
        self.snapshot = None

    def load(self):
        raw = self.settings.value(self.key, "")
        if not raw:
            return {}, set()

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

        return settlements, approved

    def save(self, settlements, approved_matches):
        payload = json.dumps(
            {
                "version": 1,
                "settlements": settlements,
                "approved_matches": sorted(approved_matches),
                "snapshot": self.snapshot,
            },
            ensure_ascii=False,
        )
        self.settings.setValue(self.key, payload)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError("Nie udało się zapisać rozliczeń na dysku.")
