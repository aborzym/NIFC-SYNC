# NIFC-SYNC

Narzędzie do synchronizacji transkrypcji z serwisem NIFC
oraz pobierania skanów źródłowych.

## Wersja stabilna

Aktualna stabilna wersja `3.0.0` udostępnia graficzny
interfejs programu na Linuksie. Wcześniejsza wersja
terminalowa pozostaje dostępna jako wydanie `2.0.0`.

## Rozwój wersji 4.0

Wersja 4.0 jest rozwijana jako uniwersalna aplikacja
obsługująca wiele kont i różne sposoby organizowania plików.

Obecnie obsługuje:

- konta użytkowników z osobnymi ustawieniami;
- dane logowania przechowywane w systemowym magazynie haseł;
- ręczne łączenie z serwisem NIFC;
- workflowy `XML`, `KRN-diplomatic` i `KRN-modern`;
- katalogi lokalne oraz udziały SMB;
- wykrywanie komputerów i montowanie udziałów SMB na Linuksie;
- pobieranie skanów z Biblioteki Diecezjalnej w Sandomierzu;
- pobieranie skanów z Polish Music Sources;
- kontrolę kompletności pobranych pakietów;
- osobne profile organizacji plików.

## Profile organizacji plików

### Andrzej Borzym

Osobny katalog dla każdego utworu. Transkrypcja znajduje się
w katalogu utworu, a skany w jego podkatalogu `skany`.

### Marta Lawrence

Transkrypcje są zapisywane luzem w osobnych katalogach
bibliotek. Skany trafiają do niezależnych katalogów bibliotek,
a każdy pakiet otrzymuje własny folder bez końcówki `.zip`.

Program rozpoznaje również starsze foldery pakietów, których
nazwy kończą się na `.zip`, i nie zmienia ich automatycznie.

### Andrzej Kubiczek

Profil jest przygotowany w konfiguracji. Szczegółowa obsługa
jego układu katalogów zostanie dodana po ustaleniu pełnego
przebiegu pracy.

## Uruchomienie wersji rozwojowej

Wymagany jest Python 3.12 lub nowszy.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```
