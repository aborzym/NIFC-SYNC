# Ręczne testy NIFC-SYNC 4.0

## Do wykonania na Linuksie

- [ ] Wykrywanie serwera SMB przez `gio`.
- [ ] Interaktywne logowanie SMB przez `pexpect`.
- [ ] Pobranie listy udziałów SMB.
- [ ] Zamontowanie wybranego udziału.
- [ ] Wybór katalogu z `/run/user/<uid>/gvfs`.
- [ ] Sprawdzenie, że istniejące montowanie CIFS pozostaje aktywne.
- [ ] Odmontowanie wyłącznie testowego udziału GIO.

## Do wykonania przed wydaniem

- [ ] Pełna synchronizacja profilu Marta Lawrence do katalogów lokalnych.
- [ ] Zapis transkrypcji luzem we właściwych folderach bibliotek.
- [ ] Pobranie skanów do folderu pakietu bez końcówki `.zip`.
- [ ] Rozpoznanie istniejącego starego folderu pakietu z końcówką `.zip`.
- [ ] Ponowne pobranie i naprawa pakietu z uszkodzonym manifestem.
- [ ] Dodanie drugiego konta i usunięcie go z listy kont.
- [ ] Przełączenie na pozostałe konto po usunięciu aktywnego.
- [ ] Zablokowanie utworzenia dwóch kont o tej samej nazwie.
- [ ] Natychmiastowe zablokowanie loginu NIFC używanego przez inne konto, przed próbą połączenia z NIFC.
- [ ] Sprawdzenie, że konflikt loginu nie nadpisuje hasła w keyringu.
- [ ] Usunięcie hasła z keyringu, gdy login nie jest używany przez inne konto.
- [ ] Zachowanie hasła dla starszej konfiguracji, gdy login jest współdzielony przez inne konto.
- [ ] Wyświetlenie folderu docelowego w oknie wyboru skanów.
- [ ] Dopasowanie wszystkich kolumn do szerokości okna bez poziomego przewijania.
- [ ] Ręczna zmiana szerokości kolumn bez wypychania pozostałych poza tabelę.

## Wykonane na macOS

- [x] Pełny zestaw testów automatycznych na Pythonie 3.14.
- [x] Uruchomienie konfiguratora pierwszego startu.
- [x] Migracja dotychczasowych ustawień bez zapisywania hasła.
- [x] Wyświetlenie profili Andrzej Borzym, Marta Lawrence i Andrzej Kubiczek.

## Uwagi

Rzeczywistych testów SMB nie wykonujemy na macOS. Obecna implementacja
korzysta na Linuksie z `gio`, GVfs i katalogu montowań użytkownika.
