# Ręczne testy NIFC-SYNC 4.0

## Do wykonania na Linuksie

- [x] Wykrywanie serwera SMB przez `gio`.
- [x] Interaktywne logowanie SMB przez `pexpect`.
- [x] Pobranie listy udziałów SMB.
- [x] Zamontowanie wybranego udziału.
- [x] Automatyczne odnalezienie udziału w `/run/user/<uid>/gvfs`.
- [x] Otwarcie wyboru katalogu bezpośrednio wewnątrz zamontowanego udziału.
- [x] Wykrycie brakującego montowania przy próbie połączenia z NIFC.
- [x] Ponowne zamontowanie udziału SMB i automatyczne kontynuowanie połączenia.
- [x] Odmontowanie wyłącznie testowego udziału GIO.
- [x] Usunięcie hardkodowanego `~/mac_transkrypcje` z `nifc_sync.py`.
- [x] Pobieranie katalogu terminalowego z aktywnej konfiguracji konta.
- [x] Usunięcie nieużywanej obsługi CIFS i stałej `DEFAULT_SHARE`.
- [x] Usunięcie komunikatów zakładających Maca z `gui/workers.py`.
- [x] Zastąpienie komunikatu „Obudź Maca” ogólną informacją o niedostępnym katalogu lub udziale sieciowym.
- [x] Zbudowanie pakietu `nifc-sync_4.0.0_amd64.deb`.
- [x] Instalacja pakietu 4.0.0 wraz z zależnościami GIO, GVfs i keyringu.
- [x] Uruchomienie aplikacji zainstalowanej w `/opt/nifc-sync`.
- [x] Wczytanie aktywnego konta i ustawień przez zainstalowaną aplikację.
- [x] Synchronizacja GUI z katalogiem zamontowanym przez GIO.
- [x] Porównanie szybkiego i dokładnego sprawdzania skanów przez SMB.
- [x] Rzeczywisty test terminala z aktywnym kontem i katalogiem lokalnym.
- [ ] Rzeczywisty test terminala z katalogiem zamontowanym przez GIO.

## Do wykonania przed wydaniem

- [x] Pełna synchronizacja profilu Marta Lawrence do katalogów lokalnych.
- [x] Zapis transkrypcji luzem we właściwych folderach bibliotek.
- [x] Pobranie skanów do folderu pakietu bez końcówki `.zip`.
- [x] Rozpoznanie istniejącego starego folderu pakietu z końcówką `.zip`.
- [x] Ponowne pobranie i naprawa pakietu z uszkodzonym manifestem.
- [x] Wyszukanie w Polish Music Sources skanów spod nieaktualnego adresu.
- [x] Dopasowanie źródła po siglum i sygnaturze przy innym identyfikatorze RISM.
- [x] Uzupełnienie brakującego siglum na podstawie nazwy transkrypcji.
- [x] Pobranie gotowego PDF z Polish Music Sources zamiast osobnych plików JPEG.
- [x] Zapis PDF w folderze `skany` wraz z manifestem.
- [x] Wyświetlenie tytułu, formatu i rzeczywistego rozmiaru znalezionego PDF.
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
- [x] Wyświetlenie folderu docelowego w oknie wyboru skanów.
- [x] Dopasowanie wszystkich kolumn do szerokości okna bez poziomego przewijania.
- [x] Ręczna zmiana szerokości kolumn bez wypychania pozostałych poza tabelę.

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
