# Zmiany względem pierwszej wersji raportu

Date: 2026-08-05
Status: accepted
Author: Piotr Cząstkiewicz
Related to: `docs/metodologia.md`

---

Wykaz poprawek naniesionych podczas porządkowania projektu, z rozróżnieniem na
te, które **zmieniają wyniki**, i te, które ich nie zmieniają. Dokument służy do
odtworzenia toku rozumowania i wyjaśnia, dlaczego poszczególne rozwiązania
zastąpiono innymi. Wersja wyjściowa raportu nie jest publikowana w tym
repozytorium — jego historia zaczyna się od stanu po przebudowie.

## A. Zmiany wpływające na wyniki

### A1. Kolumny liczbowe pozostawały tekstowe — 21 zmiennych wypadało z analiz

**Najpoważniejsza usterka.** Przekodowanie odpowiedzi na liczby opierało się na
`Series.replace`. Do pandas 2.1 metoda ta sama rzutowała kolumnę na typ liczbowy;
od 2.2 zachowanie jest wycofane, a w 3.0 usunięte. Kolumny zostawały typu
`object`, mimo że zawierały wyłącznie liczby.

Skutek: wszystkie funkcje sprawdzające `is_numeric_dtype` — w tym rankingi
korelacji z rozdziału 3 — po cichu je pomijały. Rodzina testów kurczyła się
z 31 zmiennych do 9. Znikały m.in. aktywność fizyczna, częstość spotkań, długość
snu, social jetlag i liczba godzin pracy — czyli zmienne, o których mówi
narracja raportu.

Awaria była cicha: kod nie zgłaszał błędu, tylko zwracał uboższy wynik. Raport
w wersji wyjściowej powstał na starszym pandas i zawierał poprawne rankingi,
ale przy ponownym uruchomieniu dawał inne.

**Poprawka:** jawna konwersja typów w `prepare.recode_scales` plus walidacja
`prepare.validate_output`, która przerywa przetwarzanie, gdy kolumna ze
zdefiniowaną skalą pozostała nieliczbowa albo gdy kolumna tekstowa zawiera same
liczby.

### A2. Korekta FDR liczona po obcięciu rankingu

`run_spearman_ranking` obcinała wynik do dziesięciu najsilniejszych korelacji,
a notebook dopiero potem wywoływał korektę. Obejmowała ona zatem 10 wartości p
zamiast pełnej rodziny ~31 wykonanych testów, przez co była zbyt łagodna.
Dodatkowo wynik korekty nie był nigdzie pokazywany — wykres rysował samo ρ.

**Poprawka:** korekta liczona na pełnej rodzinie przed obcięciem; liczba objętych
porównań wypisywana nad rankingiem; zmienne nieistotne wyszarzone na wykresie
i opatrzone gwiazdką.

**Wpływ na wyniki:** jedna zmiana konkluzji. W rozdziale 4.8 korelacja social
jetlag z liczbą godzin pracy (ρ = 0,197) traci istotność — p po korekcie rośnie
z 0,021 do 0,060 przy rodzinie 33 testów. Pozostałe wnioski rozdziałów 3 i 4.8
się nie zmieniają.

### A3. Rozdział 9.4 mieszał dwie próby

Tabela korelacji była liczona na całej próbie (N = 396), a wykres pod nią na
podpróbie osób pracujących (N = 136). Narracja opisywała ogół respondentów.
Podana w tekście liczebność najniższej oceny sytuacji finansowej (N = 2)
pochodziła z podpróby — w całej próbie jest to 18 osób.

**Poprawka:** wykres liczony na pełnej próbie, spójnie z tabelą; narracja
zaktualizowana.

### A4. Znak wielkości efektu zależał od kolejności wierszy

`run_mannwhitney` wyznaczała grupy przez `data[group].unique()`, czyli w
kolejności wystąpienia w pliku. Znak korelacji rangowo-dwuseryjnej zależał więc
od tego, kto pierwszy wypełnił ankietę. Sprawdzone empirycznie: dziesięć losowych
permutacji wierszy dawało dwie różne wartości `r_rb` (±0,293).

**Poprawka:** kolejność grup wyznacza porządek kategorii (dla zmiennych
porządkowych) albo sortowanie alfabetyczne. Przyjęto też standardową konwencję
znaku — wartość dodatnia oznacza przewagę pierwszej grupy; poprzedni wzór dawał
znak odwrotny do przyjętego w literaturze. Wartości bezwzględne, w tej postaci
raport podawał większość wyników, pozostają bez zmian.

### A5. Zależności część-całość nie były oznaczane

Ogólny wskaźnik satysfakcji `sat_srednia` jest średnią z siedmiu wymiarów
satysfakcji. W rozdziałach 7.5, 8.2, 8.3 i 9.4 był zestawiany w jednej tabeli ze
swoimi składowymi i konsekwentnie wypadał najsilniej — co wynika z konstrukcji
wskaźnika, a nie z danych.

**Poprawka:** `stats.correlation_table` wykrywa takie wiersze i oznacza je jako
zależność część-całość; narracja rozdziałów 7.5 i 9.4 wprost wyjaśnia, że nie
jest to odrębne ustalenie.

### A6. Test parametryczny niezgodny z deklarowaną metodyką

Rozdział 7.2.2 używał jednoczynnikowej ANOVA z testem Tukeya — jedynej procedury
parametrycznej w raporcie, niewymienionej w rozdziale metodologicznym, zastosowanej
do zmiennej porządkowej 1-5.

**Poprawka:** zastąpiono testem Kruskala-Wallisa z testem post hoc Dunna.
**Wpływ na wyniki:** brak zmiany wniosków. Test omnibus pozostaje istotny
(H = 40,42; p < 0,001), a jedynym istotnym przejściem między sąsiednimi
kategoriami nadal jest zmiana z 1-2 na 3-5 bliskich znajomych.

## B. Zmiany niewpływające na wyniki

### B1. Trzy źródła prawdy o kwestionariuszu zastąpione jednym

Kodowanie odpowiedzi żyło w trzech niezależnych miejscach: mapach `replace`
w `prepare_data`, słowniku `mapping_tables` oraz `VARIABLE_LABELS`
w `constants.py`. Były już rozjechane — np. „powyżej 20 godzin" wobec
„więcej niż 20".

`constants.py` zawierał 7 zduplikowanych kluczy w `VARIABLE_LABELS` (30 wpisów,
23 unikalne) i 3 w `VARIABLE_LABELS_LONG`. Dwa duplikaty miały różne wartości,
więc jedna definicja po cichu nadpisywała drugą.

Zastąpione przez `schema.py` z walidacją spójności wykonywaną przy imporcie.

### B2. Funkcja 570-linijkowa rozbita na etapy

`prepare_data` łączyła sześć odpowiedzialności w jednej funkcji. Obecnie każdy
etap jest osobną funkcją poniżej 50 linii, możliwą do uruchomienia niezależnie.

### B3. Usterki w warstwie wykresów

- `plot_stacked_bar` przy `normalize=False` nie dopisywała etykiet w gałęzi
  `else`, co przy domyślnym `show_values=True` kończyło się wyjątkiem. Usterka
  nie ujawniała się, bo notebook zawsze wywoływał funkcję z `normalize=True`.
- Dwa wywołania `ax.legend()` — drugie kasowało pierwsze, gubiąc parametr
  `legend_description`.
- Dwa wywołania `imshow` w heatmapie przejść, drugie z inną orientacją.
- Rozrzut punktów na wykresach pudełkowych bez ustalonego ziarna generatora.
- Zahardkodowany zakres osi `(0.8, 5.2)` w `plot_mean_ci`.
- Usunięto trzy nieużywane funkcje rysujące (`plot_bar`, `plot_hist`,
  `plot_corr_heatmap`) oraz dwie nieużywane funkcje opisowe.

### B4. Etykiety oddzielone od układu graficznego

Nazwy zmiennych zawierały wpisane na stałe znaki nowej linii (`"Zdrowie\npsych."`),
przez co ta sama etykieta wymagała odwracania funkcją `unwrap_label` w tabelach.
Łamanie tekstu przeniesiono do warstwy wykresów (`plots.wrap_label`);
`unwrap_label` została usunięta jako zbędna.

### B5. Ujednolicone formatowanie liczb

W notebooku dwukrotnie definiowano lokalną funkcję `format_p` obok istniejącej
`format_p_value`, z różnym separatorem dziesiętnym. Część tabel raportu podawała
„0,003", część „0.003". Formatowanie skupiono w module `report.py`.

### B6. Ukryty stan w notebooku

Nazwa `df_sleep` oznaczała dwie różne podpróby w miejscach oddalonych o 28
komórek; `df_pracujacy` i `df_zwiazek` były redefiniowane. Komórka rozdziału 8.4
dopisywała kolumnę do globalnej ramki `df` w połowie raportu. Wykonanie komórek
poza kolejnością dawało ciche błędne wyniki.

Nazwy podprób są teraz jednoznaczne (`df_sen_typowy`, `df_sen_problemy`,
`df_wydzialy`, `df_organizacje`), a przygotowana ramka nie jest modyfikowana.

### B7. Redakcja

- Usunięto notatki robocze z nagłówków i treści („TO SIĘ JESZCZE ZMIENI PEWNIE",
  „Jeżeli taki był w ogóle xD", „1 strona max.").
- Poprawiono etykietę osi na wykresie satysfakcji z życia (była „Grupa wiekowa").
- Poprawiono literówki: „wykazałaa", „w badanej próbce", „częśtości",
  „Liczba orgarnizacji", „Ocena z życia".

## C. Rozdziały napisane od nowa

Rozdziały 10-15 istniały wyłącznie jako nagłówki z notatkami roboczymi. Napisano:

- **10. Modele wieloczynnikowe** — trzy modele regresji ze wspólnym zestawem
  predyktorów, diagnostyka współliniowości (VIF poniżej 2,2).
- **11. Synteza wyników** — zestawienie najsilniejszego wyniku w każdym obszarze
  wraz z informacją, czy przetrwał kontrolę pozostałych czynników.
- **12. Najważniejsze wyniki** — dziesięć najsilniejszych zależności.
- **13. Ograniczenia badania** — w tym udokumentowanie ścieśnienia krańców skal
  przez kategorie otwarte oraz nachodzących przedziałów czasu nauki.
- **14. Wnioski** — odpowiedzi na cztery pytania badawcze.
- **15. Aneks** — tabela kodowania, rozkłady zmiennych pominiętych w części
  głównej, przeglądowa macierz korelacji, instrukcja odtworzenia analizy.

Najważniejsze ustalenie z rozdziału 10: **długość snu traci istotność w modelach
dobrostanu psychicznego, gdy uwzględni się problemy ze snem**. Potwierdza to
wniosek z rozdziału 4, że liczy się jakość snu, nie liczba godzin. Istotność
w modelu pełnym zachowują cztery czynniki: problemy ze snem, aktywność fizyczna,
wsparcie społeczne i ocena sytuacji finansowej. Tracą ją: ocena diety oraz social
jetlag.
