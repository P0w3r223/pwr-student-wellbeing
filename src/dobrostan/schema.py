"""Jedno źródło prawdy o zmiennych badania.

Każda zmienna jest opisana raz: nazwa kolumny w kwestionariuszu, kod używany
w kodzie, etykiety do wykresów i tabel oraz — dla skal przedziałowych — pełna
lista kategorii odpowiedzi wraz z przypisaną wartością liczbową.

Wszystko, czego potrzebuje reszta pakietu, jest z tego wyprowadzane:

* `coding_map(kod)`    — surowa odpowiedź  -> wartość liczbowa (do przekodowania)
* `value_labels(kod)`  — wartość liczbowa  -> etykieta na wykresie
* `mapping_table()`    — powyższe jako DataFrame, do aneksu raportu

Dzięki temu kodowanie „w przód" i opis „wstecz" nie mogą się rozjechać —
wcześniej były to trzy niezależne słowniki, które już się różniły.

Konwencja nazewnicza: identyfikatory po angielsku, dokumentacja, komentarze
oraz wszystkie dane widoczne w raporcie po polsku.

Etykiety nie zawierają znaków nowej linii. Łamanie tekstu to decyzja
prezentacyjna i należy do warstwy wykresów (`plots.wrap_label`), nie do opisu
zmiennej.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

#: Odpowiedź oznaczająca odmowę — kodowana jako brak danych, nie jako wartość.
REFUSAL = "nie chcę odpowiadać"

#: Odpowiedzi oznaczające brak danych, a nie pozycję na skali.
#:
#: Rozróżnienie jest istotne dla walidacji: odpowiedź spoza tego zbioru
#: i spoza schematu zmiennej oznacza rozjazd kwestionariusza z kodem
#: i musi przerwać przetwarzanie, zamiast po cichu zamienić się w brak danych.
MISSING_MARKERS = (
    REFUSAL,
    "Brak - w trakcie pierwszego semestru",
)


@dataclass(frozen=True)
class Category:
    """Jedna odpowiedź na skali przedziałowej."""

    answer: str
    """Dokładne brzmienie odpowiedzi w kwestionariuszu."""

    value: float
    """Wartość reprezentatywna przypisana tej kategorii."""

    label: str
    """Skrócony opis na osi wykresu."""

    open_ended: bool = False
    """True dla kategorii bez ograniczenia z jednej strony („10 i więcej").

    Takim kategoriom przypisujemy wartość brzegową, a nie środek przedziału,
    co ścieśnia skalę na jej krańcu. Flaga pozwala udokumentować to w aneksie
    zamiast ukrywać w danych — patrz `docs/metodologia.md`.
    """


@dataclass(frozen=True)
class Variable:
    """Opis pojedynczej zmiennej w zbiorze."""

    label: str
    """Krótka nazwa na oś wykresu."""

    description: str
    """Pełna nazwa do tabel wyników i raportu."""

    categories: tuple[Category, ...] = field(default_factory=tuple)
    """Skala przedziałowa. Pusta dla zmiennych już liczbowych i tekstowych."""

    order: tuple[str, ...] = field(default_factory=tuple)
    """Kolejność kategorii dla zmiennych jakościowych porządkowych."""


def _intervals(pairs: list[tuple[str, float]], last_open: bool = True) -> tuple[Category, ...]:
    """Buduje kategorie, w których etykieta jest identyczna z brzmieniem odpowiedzi."""
    return tuple(
        Category(answer, value, answer, open_ended=last_open and i == len(pairs) - 1)
        for i, (answer, value) in enumerate(pairs)
    )


# ---------------------------------------------------------------------------
# Skale powtarzalne
# ---------------------------------------------------------------------------

# „Ile godzin…" — wspólna dla aktywności fizycznej, ekranu i mediów społecznościowych.
_HOURS = _intervals([("0", 0), ("1 - 2", 1.5), ("3 - 5", 4), ("6 - 9", 7.5), ("10 i więcej", 10)])

# Długość snu — kategorie otwarte po obu stronach skali.
_SLEEP = (
    Category("mniej niż 3", 2, "mniej niż 3", open_ended=True),
    Category("3 - 4", 3.5, "3 - 4"),
    Category("5 - 6", 5.5, "5 - 6"),
    Category("7 - 9", 8, "7 - 9"),
    Category("więcej niż 9", 10, "więcej niż 9", open_ended=True),
)

# Częstotliwość spożycia — identyczna dla czterech używek.
_FREQUENCY = _intervals(
    [
        ("rzadziej lub nigdy", 0),
        ("co miesiąc", 1),
        ("co tydzień", 2),
        ("co kilka dni", 3),
        ("codziennie", 4),
    ],
    last_open=False,
)


# ---------------------------------------------------------------------------
# Zmienne
# ---------------------------------------------------------------------------

VARIABLES: dict[str, Variable] = {
    # --- demografia i warunki życia ------------------------------------------
    "wiek_grupa": Variable(
        "Grupa wiekowa",
        "Grupa wiekowa",
        order=("18 - 20 lat", "21 - 23 lata", "24 - 26 lat", "27 lat i więcej"),
    ),
    "plec": Variable("Płeć", "Płeć"),
    "wydzial": Variable("Wydział", "Wydział"),
    "etap_studiow": Variable(
        "Etap studiów",
        "Etap studiów",
        order=(
            "I stopień - 1. rok",
            "I stopień - lata 2-4",
            "Ukończony I stopień",
            "II stopień (magister)",
            "Doktorat lub wyżej",
        ),
    ),
    "typ_zamieszkania": Variable("Typ zamieszkania", "Typ miejsca zamieszkania"),
    "wspollokatorzy": Variable(
        "Sposób zamieszkania",
        "Sposób zamieszkania",
        order=(
            "Mieszkam samodzielnie",
            "Z rodziną",
            "Z jednym współlokatorem",
            "Z kilkoma współlokatorami",
        ),
    ),
    "dojazd_min": Variable(
        "Czas dojazdu",
        "Czas dojazdu na uczelnię [min]",
        categories=_intervals(
            [
                ("do 15 minut", 7.5),
                ("16 - 30 minut", 23),
                ("31 - 45 minut", 38),
                ("46 - 60 minut", 53),
                ("powyżej 60 minut", 60),
            ]
        ),
    ),
    # --- dobrostan (skale 1-5, w kwestionariuszu już liczbowe) ---------------
    "sat_zycie": Variable("Sat. życia", "Satysfakcja z życia"),
    "sat_studia": Variable("Sat. ze studiów", "Satysfakcja ze studiów"),
    "sat_finanse": Variable("Sat. finansowa", "Satysfakcja finansowa"),
    "sat_zdrowie_fiz": Variable("Zdrowie fiz.", "Zdrowie fizyczne"),
    "sat_zdrowie_psych": Variable("Zdrowie psych.", "Zdrowie psychiczne"),
    "sat_relacje": Variable("Sat. z relacji", "Satysfakcja z relacji"),
    "sat_czas_wolny": Variable("Sat. z czasu wolnego", "Satysfakcja z czasu wolnego"),
    "sat_rodzina": Variable("Sat. z rodziny", "Satysfakcja z relacji rodzinnych"),
    "sat_srednia": Variable("Sat. ogólna", "Ogólny wskaźnik satysfakcji"),
    "poziom_stresu": Variable("Stres", "Poziom stresu"),
    "poczucie_kontroli": Variable("Kontrola", "Poczucie kontroli"),
    "poziom_wsparcia": Variable("Wsparcie", "Poziom wsparcia społecznego"),
    # --- relacje społeczne ---------------------------------------------------
    "liczba_bliskich": Variable(
        "Liczba bliskich znajomych",
        "Liczba bliskich znajomych",
        categories=_intervals(
            [("0", 0), ("1 - 2", 1.5), ("3 - 5", 4), ("6 - 9", 7.5), ("10 i więcej", 10)]
        ),
    ),
    "czestosc_spotkan": Variable(
        "Częstość spotkań",
        "Częstość spotkań ze znajomymi",
        categories=(
            Category("wcale", 0, "wcale"),
            Category("rzadziej niż raz w miesiącu", 1, "rzadziej niż 1×/mies."),
            Category("raz w miesiącu", 2, "1× w miesiącu"),
            Category("raz w tygodniu", 3, "1× w tygodniu"),
            Category("kilka razy w tygodniu", 4, "kilka razy w tygodniu"),
            Category("codziennie", 5, "codziennie"),
        ),
    ),
    "stan_cywilny": Variable(
        "Stan cywilny",
        "Stan cywilny",
        order=(
            "inne / brak odpowiedzi",
            "singiel / singielka",
            "w związku",
            "zaręczony / zaręczona",
            "małżeństwo",
        ),
    ),
    "czestosc_pomoc_psych": Variable(
        "Pomoc psychologiczna",
        "Częstość korzystania z pomocy psychologicznej",
        categories=(
            Category("nie korzystam", 0, "nie korzystam"),
            Category("1-2 razy w roku", 1, "1-2 razy w roku"),
            Category("kilka razy w roku", 2, "kilka razy w roku"),
            Category("raz w miesiącu", 3, "raz w miesiącu"),
            Category("kilka razy w miesiącu", 4, "kilka razy w miesiącu"),
            Category("raz w tygodniu", 5, "raz w tygodniu"),
        ),
    ),
    # --- styl życia ----------------------------------------------------------
    "aktywnosc_fiz_h_tydz": Variable(
        "Aktywność fizyczna",
        "Aktywność fizyczna [h/tydzień]",
        categories=_HOURS,
    ),
    "czas_ekran_h_dzien": Variable(
        "Czas przed ekranem", "Czas przed ekranem [h/dzień]", categories=_HOURS
    ),
    "czas_social_h_dzien": Variable(
        "Media społecznościowe",
        "Czas w mediach społecznościowych [h/dzień]",
        categories=_HOURS,
    ),
    "czestosc_fastfood": Variable("Fast food", "Częstość spożywania fast foodów", categories=_FREQUENCY),
    "czestosc_energetyki": Variable(
        "Energetyki", "Częstość spożywania napojów energetycznych", categories=_FREQUENCY
    ),
    "czestosc_alkohol": Variable(
        "Alkohol", "Częstość spożywania wyrobów alkoholowych", categories=_FREQUENCY
    ),
    "czestosc_nikotyna": Variable(
        "Nikotyna", "Częstość spożywania wyrobów nikotynowych", categories=_FREQUENCY
    ),
    "ocena_diety": Variable("Ocena diety", "Ocena jakości diety"),
    # --- sen -----------------------------------------------------------------
    "sen_h_dni_robocze": Variable("Sen (dni rob.)", "Długość snu w dni robocze [h]", categories=_SLEEP),
    "sen_h_weekend": Variable("Sen (weekend)", "Długość snu w weekendy [h]", categories=_SLEEP),
    "problemy_sen": Variable("Problemy ze snem", "Problemy ze snem"),
    "social_jetlag": Variable("Social jetlag", "Social jetlag [h]"),
    # --- studia --------------------------------------------------------------
    "srednia_ocen": Variable(
        "Średnia ocen",
        "Średnia ocen z ostatniego semestru",
        categories=(
            Category("poniżej 3,5", 3.0, "poniżej 3,5", open_ended=True),
            Category("3,5 - 3,99", 3.75, "3,5 - 3,99"),
            Category("4,0 - 4,49", 4.25, "4,0 - 4,49"),
            Category("4,5 - 5,0", 4.75, "4,5 - 5,0"),
            Category("powyżej 5,0", 5.0, "powyżej 5,0", open_ended=True),
        ),
    ),
    "nauka_h_tydz": Variable(
        "Czas nauki",
        "Czas poświęcony nauce [h/tydzień]",
        categories=(
            Category("0 - 2 godziny", 1, "0 - 2"),
            Category("3 - 6 godzin", 4.5, "3 - 6"),
            Category("7 - 11 godzin", 9, "7 - 11"),
            Category("11 - 15 godzin", 13, "11 - 15"),
            Category("15 - 20 godzin", 17.5, "15 - 20"),
            Category("powyżej 20 godzin", 20, "powyżej 20", open_ended=True),
        ),
    ),
    "liczba_organizacji": Variable(
        "Liczba organizacji",
        "Liczba organizacji studenckich",
        categories=(
            Category("0", 0, "0"),
            Category("1", 1, "1"),
            Category("2", 2, "2"),
            Category("3 lub więcej", 3, "3 lub więcej", open_ended=True),
        ),
    ),
    # --- praca i finanse -----------------------------------------------------
    "zrodlo_utrzymania": Variable("Źródło utrzymania", "Główne źródło utrzymania"),
    "wydatki_podstawowe": Variable(
        "Wydatki podstawowe",
        "Miesięczne wydatki podstawowe [zł]",
        categories=(
            Category("do 1 000 zł", 500, "do 1 000"),
            Category("1 000 - 2 000 zł", 1500, "1 000 - 2 000"),
            Category("2 000 - 3 000 zł", 2500, "2 000 - 3 000"),
            Category("3 000 - 4 000 zł", 3500, "3 000 - 4 000"),
            Category("powyżej 4 000 zł", 4000, "powyżej 4 000", open_ended=True),
        ),
    ),
    "wydatki_rozrywka": Variable(
        "Wydatki na rozrywkę",
        "Miesięczne wydatki na rozrywkę [zł]",
        categories=(
            Category("do 300 zł", 150, "do 300"),
            Category("300 - 600 zł", 450, "300 - 600"),
            Category("600 - 1 000 zł", 800, "600 - 1 000"),
            Category("1 000 - 1 500 zł", 1250, "1 000 - 1 500"),
            Category("powyżej 1 500 zł", 1500, "powyżej 1 500", open_ended=True),
        ),
    ),
    "ocena_finansowa": Variable("Ocena finansowa", "Ocena sytuacji finansowej"),
    "czy_pracuje": Variable(
        "Aktywność zawodowa",
        "Czy respondent pracuje",
        categories=(Category("Nie", 0, "Nie"), Category("Tak", 1, "Tak")),
    ),
    "forma_pracy": Variable(
        "Forma pracy",
        "Forma wykonywanej pracy",
        order=("Stacjonarna", "Hybrydowa", "Zdalna"),
    ),
    "praca_h_tydz": Variable(
        "Godziny pracy",
        "Liczba godzin pracy w tygodniu",
        categories=(
            Category("do 10 godzin", 5, "do 10"),
            Category("11 - 20 godzin", 15, "11 - 20"),
            Category("21 - 30 godzin", 25, "21 - 30"),
            Category("powyżej 30 godzin", 30, "powyżej 30", open_ended=True),
        ),
    ),
    "praca_zgodna": Variable(
        "Zgodność pracy z kierunkiem",
        "Zgodność pracy z kierunkiem studiów",
        categories=(
            Category("Nie", 0, "Nie"),
            Category("Częściowo", 0.5, "Częściowo"),
            Category("Tak", 1, "Tak"),
        ),
    ),
}


# ---------------------------------------------------------------------------
# Nazwy kolumn w surowym pliku
# ---------------------------------------------------------------------------

#: Kolumny usuwane od razu — sygnatura czasowa nie jest zmienną badawczą,
#: a pole e-mail zostało zanonimizowane już na etapie eksportu ankiety.
DROPPED_COLUMNS = (
    "Sygnatura czasowa",
    "Chcesz otrzymać końcowe wyniki badania? Jeśli tak, podaj swój adres e-mail:",
)

#: Nazwa kolumny po normalizacji -> kod zmiennej.
COLUMN_NAMES: dict[str, str] = {
    "do_jakiej_grupy_wiekowej_nalezysz": "wiek_grupa",
    "jaka_jest_twoja_plec": "plec",
    "na_jakich_wydzialach_studiujesz": "wydzial",
    "jaki_jest_twoj_najwyzszy_ukonczony_stopien_aktualny_etap_ksztalcenia": "etap_studiow",
    "ile_srednio_czasu_zajmuje_ci_dojazd_na_uczelnie_w_jedna_strone": "dojazd_min",
    "jakie_jest_twoje_obecne_miejsce_zamieszkania": "typ_zamieszkania",
    "z_kim_dzielisz_obecne_miejsce_zamieszkania": "wspollokatorzy",
    "jak_oceniasz_swoja_satysfakcje_z_ze_zycia": "sat_zycie",
    "jak_oceniasz_swoja_satysfakcje_z_ze_nauki_na_studiach": "sat_studia",
    "jak_oceniasz_swoja_satysfakcje_z_ze_finansow": "sat_finanse",
    "jak_oceniasz_swoja_satysfakcje_z_ze_zdrowia_fizycznego": "sat_zdrowie_fiz",
    "jak_oceniasz_swoja_satysfakcje_z_ze_zdrowia_psychicznego": "sat_zdrowie_psych",
    "jak_oceniasz_swoja_satysfakcje_z_ze_relacji": "sat_relacje",
    "jak_oceniasz_swoja_satysfakcje_z_ze_czasu_wolnego": "sat_czas_wolny",
    "ile_osob_uwazasz_za_swoich_bliskich_znajomych": "liczba_bliskich",
    "jak_czesto_spotykasz_sie_ze_znajomymi_w_czasie_wolnym": "czestosc_spotkan",
    "w_jakim_stopniu_odczuwasz_wsparcie_ze_strony_innych": "poziom_wsparcia",
    "jaki_jest_twoj_aktualny_stan_cywilny": "stan_cywilny",
    "jak_bardzo_jestes_zadowolony_z_relacji_z_rodzina": "sat_rodzina",
    "jak_oceniasz_swoj_ogolny_poziom_stresu": "poziom_stresu",
    "jak_oceniasz_poczucie_kontroli_nad_swoim_zyciem": "poczucie_kontroli",
    "jak_czesto_korzystasz_z_pomocy_psychologicznej": "czestosc_pomoc_psych",
    "ile_godzin_aktywnosci_fizycznej_uprawiasz_na_tydzien": "aktywnosc_fiz_h_tydz",
    "ile_godzin_dziennie_spedzasz_przed_ekranem": "czas_ekran_h_dzien",
    "ile_godzin_dziennie_spedzasz_korzystajac_z_mediow_spolecznosciowych": "czas_social_h_dzien",
    "jak_czesto_spozywasz_nastepujace_produkty_niezdrowe_jedzenie_fast_food_jedzenie_instant_itp": "czestosc_fastfood",
    "jak_czesto_spozywasz_nastepujace_produkty_napoje_energetyczne": "czestosc_energetyki",
    "jak_czesto_spozywasz_nastepujace_produkty_wyroby_alkoholowe": "czestosc_alkohol",
    "jak_czesto_spozywasz_nastepujace_produkty_wyroby_nikotynowe_w_tym_e_papierosy": "czestosc_nikotyna",
    "jaka_jest_twoja_ocena_wlasnej_diety": "ocena_diety",
    "ile_godzin_dziennie_spisz_w_dni_robocze": "sen_h_dni_robocze",
    "ile_godzin_dziennie_spisz_w_weekend": "sen_h_weekend",
    "czy_uwazasz_ze_masz_problemy_ze_snem": "problemy_sen",
    "jaka_jest_twoja_srednia_ocen_z_ostatniego_semestru": "srednia_ocen",
    "ile_godzin_tygodniowo_przeznaczasz_na_nauke_i_realizacje_zadan_zwiazanych_ze_studiami_poza_zajeciami": "nauka_h_tydz",
    "w_ilu_kolach_lub_organizacjach_studenckich_obecnie_uczestniczysz": "liczba_organizacji",
    "jakie_jest_twoje_glowne_zrodlo_utrzymania_w_trakcie_studiow": "zrodlo_utrzymania",
    "jaka_kwote_miesiecznie_przeznaczasz_na_niezbedne_wydatki_np_mieszkanie_wyzywienie_transport": "wydatki_podstawowe",
    "jaka_kwote_miesiecznie_przeznaczasz_na_wydatki_zwiazane_z_rozrywka_i_przyjemnosciami": "wydatki_rozrywka",
    "jak_oceniasz_swoja_obecna_sytuacje_finansowa": "ocena_finansowa",
    "czy_obecnie_pracujesz": "czy_pracuje",
    "jaka_jest_twoja_forma_pracy": "forma_pracy",
    "ile_godzin_tygodniowo_poswiecasz_na_prace": "praca_h_tydz",
    "czy_praca_ktora_wykonujesz_jest_powiazana_z_twoim_kierunkiem_studiow": "praca_zgodna",
}


# ---------------------------------------------------------------------------
# Etykiety wydziałów i skróty odpowiedzi jakościowych
# ---------------------------------------------------------------------------

FACULTIES = {
    "W1": "Architektury",
    "W2": "Budownictwa Lądowego i Wodnego",
    "W3": "Chemiczny",
    "W4": "Informatyki i Telekomunikacji",
    "W5": "Elektryczny",
    "W6": "Geoinżynierii, Górnictwa i Geologii",
    "W7": "Inżynierii Środowiska",
    "W8": "Zarządzania",
    "W9": "Mechaniczno-Energetyczny",
    "W10": "Mechaniczny",
    "W11": "Podstawowych Problemów Techniki",
    "W12": "Elektroniki, Fotoniki i Mikrosystemów",
    "W13": "Matematyki",
    "W14": "Medyczny",
}

MULTIPLE_FACULTIES = "Więcej niż jeden wydział"

#: Skrócenie rozwlekłych odpowiedzi jakościowych do postaci nadającej się na oś.
ANSWER_SHORTCUTS: dict[str, dict[str, str]] = {
    "etap_studiow": {
        "Studia I stopnia - 1. rok": "I stopień - 1. rok",
        "Studia I stopnia - kolejne lata (2-4)": "I stopień - lata 2-4",
        "Ukończone studia I stopnia (licencjat/inżynier)": "Ukończony I stopień",
        "Studia II stopnia lub ukończone studia II stopnia (magister)": "II stopień (magister)",
        "Studia doktoranckie / doktor lub wyżej": "Doktorat lub wyżej",
    },
    "typ_zamieszkania": {
        "Mieszkanie wynajmowane pod studia": "Mieszkanie wynajmowane",
        "Dom/mieszkanie rodzinne": "Dom rodzinny",
    },
    "wspollokatorzy": {
        "Mieszkam sam/a": "Mieszkam samodzielnie",
        "Rodzina": "Z rodziną",
        "Współlokator (jeden)": "Z jednym współlokatorem",
        "Współlokatorzy (wielu)": "Z kilkoma współlokatorami",
    },
    "stan_cywilny": {
        "inne/nie chce podawać": "inne / brak odpowiedzi",
        "singiel/singielka": "singiel / singielka",
        "w związku małżeńskim": "małżeństwo",
        "zaręczony/zaręczona": "zaręczony / zaręczona",
    },
}

#: Składowe ogólnego wskaźnika satysfakcji `sat_srednia`.
#:
#: Uwaga metodologiczna: `sat_srednia` jest średnią z tych zmiennych, więc jej
#: korelacja z dowolną z nich jest zależnością część-całość i jest zawyżona
#: z konstrukcji wskaźnika. `stats.correlation_table` pilnuje tego automatycznie.
SATISFACTION_COMPONENTS = (
    "sat_zycie",
    "sat_studia",
    "sat_finanse",
    "sat_zdrowie_fiz",
    "sat_zdrowie_psych",
    "sat_relacje",
    "sat_czas_wolny",
)


# ---------------------------------------------------------------------------
# Funkcje wyprowadzające
# ---------------------------------------------------------------------------


def coding_map(code: str) -> dict[str, float]:
    """Zwraca mapowanie: brzmienie odpowiedzi -> wartość liczbowa."""
    return {c.answer: c.value for c in VARIABLES[code].categories}


def value_labels(code: str) -> dict[float, str]:
    """Zwraca mapowanie odwrotne: wartość liczbowa -> etykieta na wykresie."""
    return {c.value: c.label for c in VARIABLES[code].categories}


def scaled_codes() -> list[str]:
    """Kody zmiennych wymagających przekodowania odpowiedzi na liczby."""
    return [code for code, v in VARIABLES.items() if v.categories]


def ordinal_codes() -> list[str]:
    """Kody zmiennych jakościowych o ustalonej kolejności kategorii."""
    return [code for code, v in VARIABLES.items() if v.order]


def labels() -> dict[str, str]:
    """Krótkie etykiety wszystkich zmiennych — na osie i legendy wykresów."""
    return {code: v.label for code, v in VARIABLES.items()}


def descriptions() -> dict[str, str]:
    """Pełne nazwy wszystkich zmiennych — do tabel wyników."""
    return {code: v.description for code, v in VARIABLES.items()}


def mapping_table() -> pd.DataFrame:
    """Zestawienie kodowania wszystkich skal przedziałowych.

    Trafia do aneksu raportu jako dokumentacja tego, jak kategorie odpowiedzi
    zostały zamienione na liczby. Kolumna `kategoria_otwarta` wskazuje pozycje,
    którym przypisano wartość brzegową zamiast środka przedziału.
    """
    rows = [
        {
            "zmienna": code,
            "odpowiedź": c.answer,
            "wartość_numeryczna": c.value,
            "etykieta": c.label,
            "kategoria_otwarta": c.open_ended,
        }
        for code in scaled_codes()
        for c in VARIABLES[code].categories
    ]
    return pd.DataFrame(rows)


def validate_schema() -> None:
    """Weryfikuje wewnętrzną spójność schematu.

    Wywoływane przy imporcie modułu — schemat rozjechany z sobą samym jest
    najkosztowniejszym rodzajem błędu w tym projekcie, bo psuje wyniki po cichu,
    zamiast rzucać wyjątek.
    """
    for raw, code in COLUMN_NAMES.items():
        if code not in VARIABLES:
            raise ValueError(f"Kolumna '{raw}' mapuje na nieopisaną zmienną '{code}'.")

    for code in scaled_codes():
        categories = VARIABLES[code].categories
        answers = [c.answer for c in categories]
        values = [c.value for c in categories]
        if len(set(answers)) != len(answers):
            raise ValueError(f"Zmienna '{code}' ma zduplikowane brzmienia odpowiedzi.")
        if len(set(values)) != len(values):
            raise ValueError(f"Zmienna '{code}' ma zduplikowane wartości liczbowe.")
        if values != sorted(values):
            raise ValueError(f"Zmienna '{code}' ma kategorie w kolejności niezgodnej z wartościami.")

    missing = set(SATISFACTION_COMPONENTS) - set(VARIABLES)
    if missing:
        raise ValueError(f"Składowe wskaźnika satysfakcji spoza schematu: {sorted(missing)}")


validate_schema()

__all__ = [
    "REFUSAL",
    "MISSING_MARKERS",
    "Category",
    "Variable",
    "VARIABLES",
    "DROPPED_COLUMNS",
    "COLUMN_NAMES",
    "FACULTIES",
    "MULTIPLE_FACULTIES",
    "ANSWER_SHORTCUTS",
    "SATISFACTION_COMPONENTS",
    "coding_map",
    "value_labels",
    "scaled_codes",
    "ordinal_codes",
    "labels",
    "descriptions",
    "mapping_table",
]
