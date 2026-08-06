# Metodologia analizy

Date: 2026-08-05
Status: accepted
Author: Piotr Cząstkiewicz
Related to: `notebooks/raport.ipynb`, `docs/zmiany-w-analizie.md`

---

Dokument zbiera decyzje metodologiczne przyjęte w analizie wraz z uzasadnieniem.
Opisuje **dlaczego** wybrano dane rozwiązanie — samo *co* zostało zrobione widać
w kodzie i w raporcie.

## 1. Dobór testów statystycznych

Wszystkie kluczowe zmienne zależne są porządkowe: pięciostopniowe skale ocen
(satysfakcja, stres, poczucie kontroli, wsparcie) albo przedziały przekodowane
na wartości reprezentatywne. Nie spełniają założeń o skali ilościowej ani
o rozkładzie normalnym, dlatego podstawą są **metody nieparametryczne**:

| Zagadnienie | Test | Wielkość efektu |
|---|---|---|
| Związek dwóch zmiennych porządkowych | korelacja rang Spearmana | ρ |
| Porównanie dwóch grup | U Manna-Whitneya | korelacja rangowo-dwuseryjna |
| Porównanie 3+ grup | Kruskala-Wallisa | η²_H = (H − k + 1) / (n − k) |
| Post hoc po Kruskalu-Wallisie | Dunna | — |
| Dwie zmienne kategoryczne | chi-kwadrat niezależności | V Craméra |

**Wyjątek — regresja liniowa.** W rozdziałach 6.3, 7.3.2 i 10 zastosowano modele
regresji liniowej mimo porządkowego charakteru zmiennych zależnych. Przy skalach
pięciostopniowych i próbie tej wielkości jest to rozwiązanie powszechnie
stosowane, a alternatywa (regresja porządkowa) utrudniłaby interpretację
współczynników bez wyraźnej korzyści. Wyniki traktujemy jako przybliżenie
kierunku i względnej siły zależności, nie jako precyzyjne oszacowania punktowe.
Zastrzeżenie to jest powtórzone w treści raportu.

**Decyzja zmieniona w toku prac.** W rozdziale 7.2.2 pierwotnie użyto
jednoczynnikowej analizy wariancji z testem Tukeya. Zastąpiono ją testem
Kruskala-Wallisa z testem Dunna dla spójności z resztą raportu — była to jedyna
procedura parametryczna zastosowana do porównania grup i jako jedyna nie była
wymieniona w rozdziale metodologicznym. Wnioski merytoryczne pozostały bez zmian.

## 2. Korekta na wielokrotne testowanie

Stosujemy korektę **Benjaminiego-Hochberga** (kontrola odsetka fałszywych
odkryć), nie Bonferroniego. Badanie ma charakter eksploracyjny — celem jest
wskazanie obszarów wartych dalszego badania, a nie potwierdzenie pojedynczej
hipotezy. Kontrola FDR jest w tym zastosowaniu odpowiedniejsza niż kontrola
błędu rodzinowego, która przy trzydziestu porównaniach byłaby nadmiernie
zachowawcza.

**Korekta obejmuje pełną rodzinę wykonanych porównań.** To rozstrzygnięcie
wymaga podkreślenia, bo pierwsza wersja raportu robiła inaczej: ranking korelacji
był najpierw obcinany do dziesięciu najsilniejszych, a korekta liczona dopiero
na tej dziesiątce. Zaniżało to liczbę porównań i czyniło korektę zbyt łagodną.
Obecnie `stats.spearman_ranking` liczy korektę na wszystkich testach i dopiero
potem obcina wynik, a liczba objętych porównań jest wypisywana nad każdym
rankingiem.

Zmienne, które nie przeszły korekty, są na wykresach wyszarzone i oznaczone
gwiazdką — wynik nieistotny nie powinien wyglądać tak samo jak istotny.

## 2a. Wynik nieistotny a brak różnicy

Nieistotny wynik w kilkunastoosobowej grupie i nieistotny wynik w grupie
dwustuosobowej znaczą co innego, a wyglądają tak samo. Dlatego przy porównaniach
opartych na małych grupach raport podaje **najmniejszą wielkość efektu, jaką
test jest w stanie wykryć** przy mocy 0,80 (`stats.min_detectable_rb`).

Rozstrzyga to konkretny przypadek: w rozdziale 7.2.2 porównanie kategorii „6-9"
i „10 i więcej" bliskich znajomych obejmuje 45 i 11 osób i wykrywa dopiero
efekty rzędu |r_rb| ≥ 0,55. Jego nieistotność nie jest więc dowodem, że grupy
się nie różnią. Wcześniejsza wersja raportu wyciągała z niej wniosek
o „punkcie nasycenia" relacji; wniosek ten usunięto.

## 2b. Które zmienne wchodzą do rankingów

Rankingi z rozdziału 3 obejmują zmienne liczbowe oraz te jakościowe, których
kolejność kategorii jest **realną wielkością rosnącą** — w schemacie oznaczone
flagą `rankable` (grupa wiekowa, etap studiów).

Rozróżnienie jest potrzebne, bo pole `order` w schemacie pełni rolę
prezentacyjną: ustala kolejność słupków na wykresie. „Inne / brak odpowiedzi"
stoi pierwsze w stanie cywilnym, a „Z rodziną" leży pomiędzy mieszkaniem
samodzielnym a współlokatorami — korelacja rangowa z takiego porządku byłaby
liczbą bez interpretacji.

Zmienne nominalne pozostają poza rankingiem, ale **ich lista jest wypisywana
pod każdym rankingiem**. Zestawienie „najsilniejszych zależności", które milczy
o tym, czego nie sprawdzało, sugeruje przegląd pełniejszy, niż był w istocie.

## 3. Kodowanie skal przedziałowych

Odpowiedzi podane w przedziałach („3 - 5 godzin", „1 000 - 2 000 zł") wymagają
reprezentacji liczbowej. Przyjęto **środek przedziału**, co zachowuje porządek
kategorii i pozwala liczyć korelacje rangowe.

**Kategorie otwarte otrzymują wartość brzegową**, nie środek — „10 i więcej"
koduje się jako 10, „powyżej 4 000 zł" jako 4000. Nie znamy górnej granicy tych
kategorii, więc każdy wybór byłby arbitralny; wartość brzegowa jest
najostrożniejsza, ale **ścieśnia kraniec skali i może osłabiać obserwowane
korelacje**. Kategorie te są oznaczone flagą `kategoria_otwarta` w tabeli
mapowań (aneks raportu, rozdział 15.1) i wymienione wśród ograniczeń.

Kodowanie żyje w jednym miejscu — `schema.py`. Z tej samej deklaracji generowane
jest mapowanie odpowiedzi na liczby oraz opis wartości na osiach wykresów, więc
nie mogą się rozjechać. Poprzednio były to trzy niezależne słowniki i już się
różniły (np. „powyżej 20 godzin" wobec „więcej niż 20").

## 4. Ogólny wskaźnik satysfakcji

`sat_srednia` to średnia arytmetyczna siedmiu wymiarów satysfakcji: z życia,
studiów, finansów, zdrowia fizycznego, zdrowia psychicznego, relacji i czasu
wolnego. Wszystkie mają tę samą skalę 1-5 i żaden respondent nie ma w nich braku,
więc średnia jest liczona na komplecie odpowiedzi.

**Wskaźnik zawiera swoje składowe**, dlatego jego korelacja z którąkolwiek z nich
jest zależnością część-całość i jest zawyżona z konstrukcji. Dotyczy to również
sytuacji, w której wskaźnik pojawia się w jednej tabeli obok składowych — jest
wtedy zagregowaną powtórką pozostałych wierszy, a nie odrębnym ustaleniem.
`stats.correlation_table` wykrywa oba przypadki i oznacza je kolumną
`czesc_calosci`, którą raport wyświetla jako „zależność część-całość".

Wskaźnik jest wyłączony z rankingów w rozdziale 3, gdzie konkurowałby ze swoimi
składowymi o miejsca w pierwszej dziesiątce.

## 5. Wyłączanie kategorii o małej liczebności

Kategorie liczące poniżej kilkunastu obserwacji są wyłączane **z wykresów
rozkładu**, ale nie z obliczeń korelacji. Uzasadnienie: udział procentowy
policzony na trzech osobach sugeruje precyzję, której nie ma, natomiast korelacja
rangowa korzysta z uporządkowania wszystkich obserwacji i nie wymaga
porównywania licznych grup.

Każde takie wyłączenie jest odnotowane w treści raportu wraz z liczebnością
pominiętej grupy. Dotyczy to: skrajnych kategorii długości snu (N = 3 i N = 6),
różnicy snu 6,5 h (N = 12) oraz wydziałów spoza trzech najliczniejszych.

## 6. Odtwarzalność

- Losowość występuje wyłącznie w rozrzucie punktów na wykresach pudełkowych
  i jest ustalona ziarnem `plots.JITTER_SEED`.
- Kolejność grup w teście U Manna-Whitneya wyznacza porządek kategorii albo
  sortowanie alfabetyczne — nigdy kolejność wierszy w pliku. Wcześniej znak
  wielkości efektu zależał od tego, kto pierwszy wypełnił ankietę.
- Wersje bibliotek zapisane są w `requirements-lock.txt`.

## 7. Paleta wykresów

Barwy pochodzą z palety zwalidowanej pod kątem rozróżnialności przy zaburzeniach
widzenia barw (ΔE w przestrzeni OKLab, symulacja Machado-Oliveira-Fernandes 2009,
severity 1.0):

- **porównania grup** — trzy barwy, najgorsza para wszystkich kombinacji:
  ΔE 9,2 przy protanopii i deuteranopii, ΔE 24,0 przy widzeniu normalnym;
- **skale 1-5** — skala rozbieżna czerwony-szary-niebieski, najgorsza para
  sąsiednia: ΔE 13,7 przy CVD, ΔE 17,0 przy widzeniu normalnym.

Na skali Likerta kolor koduje **pozycję na skali odpowiedzi (1→5), nie ocenę
zjawiska**. Dla satysfakcji 5 oznacza stan pożądany, dla stresu przeciwnie;
kierunek interpretacji podaje opis wykresu. Odwracanie skali barw zależnie od
wydźwięku zmiennej byłoby mylące przy porównywaniu wykresów obok siebie.

Wartości liczbowe są podpisane wprost na każdym słupku, więc identyfikacja nigdy
nie opiera się wyłącznie na kolorze.
