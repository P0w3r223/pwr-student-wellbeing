# Dane

## `raw/dane.csv`

Surowy eksport formularza ankietowego. **Plik jest niemodyfikowalny** — wszystkie
przekształcenia wykonuje `src/dobrostan/prepare.py` w pamięci, przy każdym
uruchomieniu raportu od nowa.

| Właściwość | Wartość |
|---|---|
| Liczba respondentów | 396 |
| Liczba kolumn | 46 |
| Okres zbierania | styczeń 2026 |
| Populacja | studenci Politechniki Wrocławskiej |
| Dobór próby | nielosowy, samoselekcja (udział dobrowolny) |
| Kodowanie znaków | UTF-8 |

## Dane osobowe

Zbiór **nie zawiera danych umożliwiających identyfikację respondentów**:

- Kolumna z adresem e-mail (pytanie o chęć otrzymania wyników) została
  zanonimizowana już na etapie eksportu — wszystkie 396 wartości to `-`.
  Weryfikacja: w pliku nie występuje żaden ciąg zawierający `@`.
- Kolumna „Sygnatura czasowa" pozostaje w pliku źródłowym, ale jest usuwana
  przy wczytywaniu (`schema.DROPPED_COLUMNS`), ponieważ nie jest zmienną
  badawczą, a moment wypełnienia ankiety mógłby w połączeniu z pozostałymi
  odpowiedziami zawężać krąg osób.
- Żadne pytanie nie zbierało imienia, nazwiska, numeru indeksu ani numeru
  telefonu.

Najmniejsze grupy w zbiorze (Wydział Inżynierii Środowiska — 1 osoba, Wydział
Medyczny — 2 osoby) są zbyt małe, by publikować dla nich rozkłady odpowiedzi.
W raporcie występują wyłącznie w zestawieniu liczebności całej próby.

## Braki danych

| Zmienna | Braki | Przyczyna |
|---|---|---|
| `srednia_ocen` | 27,3% | studenci I semestru nie mają jeszcze średniej |
| `praca_h_tydz` | 65,7% | pytanie warunkowe — tylko dla osób pracujących |
| `praca_zgodna` | 65,7% | pytanie warunkowe — tylko dla osób pracujących |
| `forma_pracy` | 65,7% | pytanie warunkowe — tylko dla osób pracujących |
| pozostałe | < 2% | wybór odpowiedzi „nie chcę odpowiadać" |

Braki w zmiennych warunkowych są z konstrukcji kwestionariusza, nie z odmowy.
Brak w `srednia_ocen` **nie jest losowy** — dotyczy systematycznie najmłodszej
grupy respondentów, co omówiono w rozdziale 13 raportu.

## Znane wady narzędzia

Pytanie o tygodniowy czas nauki zawiera nachodzące na siebie przedziały
(`7 - 11 godzin` oraz `11 - 15 godzin`). Respondent poświęcający dokładnie
11 godzin nie miał jednoznacznego wyboru. Przy powtórzeniu badania kategorię
należy poprawić na `7 - 10` i `11 - 15`.
