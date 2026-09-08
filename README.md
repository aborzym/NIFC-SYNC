# NIFC-SYNC

Narzędzie do synchronizacji transkrypcji z serwisem NIFC
oraz pobierania skanów źródłowych.

## Wersja stabilna

Aktualna stabilna wersja `4.0.0` udostępnia uniwersalny
interfejs graficzny, obsługę wielu kont oraz różne sposoby
organizowania transkrypcji i skanów. Wcześniejsze wydania
`3.0.0` i terminalowe `2.0.0` pozostają dostępne.

## Funkcje wersji 4.0

Wersja 4.0 obsługuje:

- konta użytkowników z osobnymi ustawieniami;
- dane logowania przechowywane w systemowym magazynie haseł;
- ręczne łączenie z serwisem NIFC;
- workflowy `XML`, `KRN-diplomatic` i `KRN-modern`;
- katalogi lokalne oraz udziały SMB;
- wykrywanie, montowanie i ponowne łączenie udziałów SMB na Linuksie;
- pobieranie skanów z Biblioteki Diecezjalnej w Sandomierzu;
- wyszukiwanie w Polish Music Sources skanów spod nieaktualnych adresów;
- pobieranie gotowych plików PDF z Polish Music Sources;
- kontrolę kompletności pobranych pakietów;
- osobne profile organizacji plików.

## Profile organizacji plików

### Andrzej Borzym

Osobny katalog dla każdego utworu. Transkrypcja znajduje się
w katalogu utworu, a skany w jego podkatalogu `skany`.

### Marta Lawrence

Transkrypcje są zapisywane luzem w osobnych katalogach
bibliotek. Skany trafiają do niezależnych katalogów bibliotek,
a każdy pakiet otrzymuje własny folder bez końcówki `.zip`
lub `.pdf`.

Program rozpoznaje również starsze foldery pakietów, których
nazwy kończą się na `.zip`, i nie zmienia ich automatycznie.

Pliki z nierozpoznanych lub nieskonfigurowanych bibliotek
trafiają do katalogów `INNE.krn` oraz `INNE.źródła`, dzięki
czemu żaden materiał nie zostaje pominięty.

### Andrzej Kubiczek

Transkrypcje i skany trafiają do katalogu `<rok>/in progress`
wewnątrz wybranego folderu nadrzędnego. Pliki są rozdzielane
między katalogi `diplomatic`, `modern` i `XML`. Transkrypcje
są zapisywane luzem, a pakiety skanów otrzymują własne foldery.

## Uruchomienie ze źródeł

Wymagany jest Python 3.12 lub nowszy.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```
