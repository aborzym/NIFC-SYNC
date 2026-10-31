# Wspólna numeracja Mac/Linux

Funkcja jest domyślnie wyłączona. Dotyczy profilu Andrzej Borzym i jednej
wspólnej numeracji w głównym katalogu projektów, niezależnie od workflow.

W głównym oknie wybierz „Numeracja Mac/Linux…”. Na Linuksie wybierz rolę
„Linux”, na Macu „Mac”. Na obu komputerach wskaż ten sam synchronizowany
folder, np. Dropbox/NIFC-SYNC, i używaj tego samego loginu NIFC.
Katalog projektów pozostaje oddzielny od folderu zawierającego wspólną listę.

Tylko Mac nadaje ostateczne numery. Istniejące foldery zachowują swoje numery.
Linux odtwarza znane nazwy; nowy projekt bez przydziału dostaje nazwę
„TMP - D/M/XML - nazwa”. Zgłoszenie trafia do wspólnego folderu. Mac rezerwuje
numer przy następnym odświeżeniu listy. Linux po odebraniu przydziału zmienia
nazwę całego folderu TMP, zachowując jego zawartość.

Odświeżanie następuje przy uruchomieniu i zamknięciu aplikacji, przed
synchronizacją transkrypcji oraz po kliknięciu „Odśwież listę folderów”.
Przydziały nowych projektów Mac zapisuje przed utworzeniem folderów.
Gdy Mac jest offline, Linux nadal może pracować w folderach TMP.
Nie ma gwarancji natychmiastowego przesłania listy: odpowiada za to Dropbox.

Lista zawiera nazwy i przydziały numerów oraz zgłoszenia nowych projektów.
Nie zawiera nut, skanów, haseł ani lokalnych ścieżek. Konto identyfikuje skrót
loginu. W katalogu projektów powstaje lokalny katalog .nifc-folder-index:
zawiera zapamiętane przydziały, blokadę operacji i identyfikator właściciela
na Macu. Zachowaj go przy przenoszeniu katalogu głównego. Nie kopiuj jego
identyfikatora właściciela na drugi aktywny katalog główny.

Sprzeczne numery, podwójne foldery i zajęte nazwy docelowe blokują operację
z komunikatem. Program nie scala ani nie nadpisuje takich folderów.
Nie usuwa rezerwacji numerów po ręcznym usunięciu folderu.
Zmiana istniejącego numeru ręcznie wymaga osobnego uzgodnienia indeksu.

Ta poprawka synchronizuje listę i numerację. Przesyłanie zawartości projektów
Linux → Mac przez udział sieciowy jest osobnym, jeszcze niewdrożonym etapem.

Weryfikacja: 210 testów unittest, w tym 18 testów indeksu i jego integracji.
Testy symulują dwa katalogi i opóźnioną dostępność danych; nie zastępują próby
na rzeczywistym Macu z Dropboxem.
