# Ręczne testy NIFC-SYNC 4.0

## Do wykonania na Linuksie

- [ ] Wykrywanie serwera SMB przez `gio`.
- [ ] Interaktywne logowanie SMB przez `pexpect`.
- [ ] Pobranie listy udziałów SMB.
- [ ] Zamontowanie wybranego udziału.
- [ ] Wybór katalogu z `/run/user/<uid>/gvfs`.
- [ ] Sprawdzenie, że istniejące montowanie CIFS pozostaje aktywne.
- [ ] Odmontowanie wyłącznie testowego udziału GIO.
- [ ] Usunięcie hardkodowanego `~/mac_transkrypcje` z `nifc_sync.py`.
- [ ] Pobieranie katalogu terminalowego z aktywnej konfiguracji konta.
- [ ] Zastąpienie `DEFAULT_SHARE` w `core/storage.py` adresem `network_url` aktywnego konta.
- [ ] Usunięcie komunikatów zakładających Maca z `gui/workers.py`.
- [ ] Zastąpienie komunikatu „Obudź Maca” ogólną informacją o niedostępnym katalogu lub udziale sieciowym.
- [ ] Rzeczywisty test terminala z montowaniem CIFS po zmianie konfiguracji.

## Do wykonania przed wydaniem

- [ ] Pełna synchronizacja profilu Marta Lawrence do katalogów lokalnych.
- [ ] Zapis transkrypcji luzem we właściwych folderach bibliotek.
- [ ] Pobranie skanów do folderu pakietu bez końcówki `.zip`.
- [ ] Rozpoznanie istniejącego starego folderu pakietu z końcówką `.zip`.
- [ ] Ponowne pobranie i naprawa pakietu z uszkodzonym manifestem.
- [ ] Dodanie drugiego konta i usunięcie go z listy kont.
- [ ] Przełączenie na pozostałe konto po usunięciu aktywnego.
- [x] Zablokowanie utworzenia dwóch kont o tej samej nazwie.
- [x] Zablokowanie zapisu konta bez własnej nazwy.
- [x] Natychmiastowe zablokowanie loginu NIFC używanego przez inne konto, przed próbą połączenia z NIFC.
- [x] Powrót selektora do aktywnego konta po anulowaniu dodawania.
- [ ] Sprawdzenie, że konflikt loginu nie nadpisuje hasła w keyringu.
- [ ] Usunięcie poprzedniego hasła z keyringu po zmianie loginu NIFC.
- [ ] Wyświetlenie ostrzeżenia, gdy nie można usunąć poprzedniego hasła.
- [ ] Usunięcie hasła z keyringu, gdy login nie jest używany przez inne konto.
- [ ] Zachowanie hasła dla starszej konfiguracji, gdy login jest współdzielony przez inne konto.
- [ ] Wyświetlenie folderu docelowego w oknie wyboru skanów.
- [ ] Dopasowanie wszystkich kolumn do szerokości okna bez poziomego przewijania.
- [ ] Ręczna zmiana szerokości kolumn bez wypychania pozostałych poza tabelę.

## Wykonane na macOS

- [x] Pełny zestaw testów automatycznych na Pythonie 3.14.
- [x] Uruchomienie konfiguratora pierwszego startu.
- [x] Migracja dotychczasowych ustawień bez zapisywania hasła.
- [x] Wczytanie loginu i hasła z pliku `.nifccredentials` do konfiguratora.
- [x] Wymuszenie własnej nazwy konta zamiast nazwy „Dotychczasowe konto”.
- [x] Wyświetlenie profili Andrzej Borzym, Marta Lawrence i Andrzej Kubiczek.

## Uwagi

Rzeczywistych testów SMB nie wykonujemy na macOS. Obecna implementacja
korzysta na Linuksie z `gio`, GVfs i katalogu montowań użytkownika.
