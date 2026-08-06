# Dobrostan studentów Politechniki Wrocławskiej

Analiza badania ankietowego dotyczącego satysfakcji z życia, zdrowia psychicznego
i fizycznego oraz stylu życia studentów Politechniki Wrocławskiej.

**Próba:** 396 respondentów, 46 zmiennych, wszystkie wydziały uczelni.

## Co czytać

| Dokument | Dla kogo | Objętość |
|---|---|---|
| [`reports/synteza.html`](reports/synteza.html) | odbiorca, który ma pięć minut — wystąpienie, seminarium | 5 stron A4 |
| [`reports/raport.html`](reports/raport.html) | odbiorca, który chce zobaczyć wszystkie wyniki | ~98 stron A4 |
| [`notebooks/raport.ipynb`](notebooks/raport.ipynb) | odbiorca, który chce prześledzić obliczenia | 15 rozdziałów |

Wszystkie trzy opisują to samo badanie. Notebook jest źródłem — obie wersje HTML
powstają z niego skryptami z katalogu `tools/`, a synteza dodatkowo sprawdza przy
generowaniu, czy podane w niej liczby nadal zgadzają się z raportem.

## Najważniejsze ustalenia

| Obszar | Najsilniejszy wynik | Utrzymuje się w modelu wieloczynnikowym |
|---|---|---|
| Relacje społeczne | Wsparcie społeczne → satysfakcja z życia (ρ = 0,39) | Tak |
| Sen | Problemy ze snem → poziom stresu (r_rb = 0,43) | Tak |
| Aktywność fizyczna | Aktywność → zdrowie fizyczne (r_rb = 0,40) | Tak |
| Finanse | Ocena sytuacji finansowej → satysfakcja z życia (ρ = 0,25) | Tak |
| Dieta | Ocena diety → zdrowie fizyczne (ρ = 0,32) | Nie |
| Praca | Brak istotnych różnic między pracującymi a niepracującymi | — |

Wszystkie efekty mieszczą się w kategorii słabych lub umiarkowanych, a modele
wieloczynnikowe wyjaśniają od 16% do 29% zróżnicowania. Badanie jest przekrojowe,
więc **żadnej zależności nie należy interpretować przyczynowo** — pełna lista
zastrzeżeń znajduje się w rozdziale 13 raportu.

## Uruchomienie

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

jupyter lab notebooks/raport.ipynb
```

Aby odtworzyć wyniki co do cyfry, użyj `requirements-lock.txt` — zawiera dokładne
wersje, na których wygenerowano bieżącą wersję raportu.

Przeliczenie notebooka i złożenie obu dokumentów HTML od nowa:

```bash
jupyter nbconvert --execute --to notebook --inplace notebooks/raport.ipynb
python tools/build_report.py      # reports/raport.html
python tools/build_summary.py     # reports/synteza.html
```

Kolejność ma znaczenie: skrypty czytają zapisane wyniki z notebooka, więc
najpierw trzeba go wykonać. `build_summary.py` przerywa pracę, jeśli liczby
wpisane w syntezę przestały zgadzać się z raportem.

## Struktura projektu

```
├── data/raw/dane.csv          surowy eksport ankiety (niemodyfikowany)
├── notebooks/raport.ipynb     raport — źródło treści i wszystkich wyników
├── reports/
│   ├── raport.html            pełny raport do czytania i druku
│   └── synteza.html           wyciąg na wystąpienie konferencyjne
├── tools/
│   ├── build_report.py        notebook → pełny raport HTML
│   └── build_summary.py       ustalenia rozdziałów 10-14 → synteza
├── src/dobrostan/
│   ├── schema.py              opis kwestionariusza: zmienne, skale, etykiety
│   ├── prepare.py             przygotowanie danych z walidacją
│   ├── stats.py               testy statystyczne
│   ├── report.py              formatowanie wyników do tabel
│   └── plots.py               wykresy
├── docs/metodologia.md        decyzje metodologiczne i ich uzasadnienie
├── docs/zmiany-w-analizie.md  wykaz poprawek względem pierwszej wersji
```

Notebook nie zawiera logiki obliczeniowej — wywołuje funkcje z `src/dobrostan`
i opisuje wyniki. Dzięki temu każdą procedurę można sprawdzić i zmienić w jednym
miejscu, a raport pozostaje czytelny jako dokument.

## Architektura

`schema.py` jest **jedynym źródłem prawdy o kwestionariuszu**. Opisuje każdą
zmienną raz — nazwę pytania, kod, etykiety oraz kategorie odpowiedzi wraz
z przypisanymi wartościami liczbowymi. Z tego opisu generowane jest zarówno
kodowanie „w przód" (odpowiedź → liczba), jak i opis „wstecz" (liczba → etykieta
na wykresie), więc nie mogą się one rozjechać.

Przygotowanie danych kończy się walidacją, która przerywa przetwarzanie, gdy
kwestionariusz przestaje odpowiadać schematowi lub gdy kolumna liczbowa
pozostała tekstowa. Obie sytuacje wcześniej powodowały ciche zawężenie analiz,
a nie widoczny błąd.

## Dane

**Surowy zbiór nie jest udostępniany w tym repozytorium.** Ankieta zawiera
odpowiedzi 396 realnych studentów i mimo braku danych identyfikujących wprost
(pole e-mail zanonimizowano na etapie eksportu, sygnatura czasowa jest usuwana
przy wczytywaniu) pozostają w niej quasi-identyfikatory: najmniejsze wydziały
reprezentuje jedna i dwie osoby, co w połączeniu z wiekiem, płcią i etapem
studiów mogłoby pozwolić na rozpoznanie respondenta.

Raport jest w pełni czytelny bez pliku źródłowego — `notebooks/raport.ipynb`
zawiera zapisane wyniki wszystkich analiz i 61 wykresów, a `reports/` gotowe
dokumenty HTML.

Aby odtworzyć obliczenia, umieść plik ankiety w `data/raw/dane.csv`.
Oczekiwany format opisuje [`data/README.md`](data/README.md), a pełne mapowanie
pytań na zmienne — `src/dobrostan/schema.py`. Dostęp do danych na potrzeby
weryfikacji naukowej: kontakt przez profil GitHub.

## Dokumentacja

- [`docs/metodologia.md`](docs/metodologia.md) — dobór testów, kodowanie skal,
  korekta na wielokrotne testowanie, znane ograniczenia pomiaru
- [`docs/zmiany-w-analizie.md`](docs/zmiany-w-analizie.md) — co i dlaczego zmieniono
  względem pierwszej wersji raportu, z wpływem na wyniki
