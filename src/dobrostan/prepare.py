"""Przygotowanie surowych danych ankietowych do analizy.

Wejściem jest plik CSV wyeksportowany z formularza, wyjściem ramka gotowa do
analiz statystycznych. Kolejne etapy są osobnymi funkcjami, dzięki czemu każdy
z nich da się uruchomić i sprawdzić niezależnie:

    load_raw -> drop_service_columns -> rename_columns -> shorten_answers
             -> recode_scales -> derive_indicators -> set_ordinal_categories
             -> validate_output

Całość spina `prepare_data()`.

Wszystkie mapowania pochodzą z `schema.py` — ten moduł nie zawiera własnej
wiedzy o kwestionariuszu, tylko logikę przekształceń.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from unidecode import unidecode

from . import schema

#: Minimalna liczba respondentów, poniżej której wynik jest podejrzany —
#: zwykle oznacza wczytanie niepełnego eksportu z formularza.
MIN_RESPONDENTS = 100


def load_raw(path: str | Path) -> pd.DataFrame:
    """Wczytuje surowy eksport ankiety."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku z danymi: {path}")
    return pd.read_csv(path)


def drop_service_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Usuwa pola techniczne formularza, niebędące zmiennymi badawczymi."""
    return df.drop(columns=list(schema.DROPPED_COLUMNS), errors="ignore")


def _normalize(name: str) -> str:
    """Sprowadza nagłówek kolumny do postaci snake_case bez znaków diakrytycznych."""
    return re.sub(r"[^a-z0-9]+", "_", unidecode(name.lower())).strip("_")


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Zamienia pełne brzmienia pytań na krótkie kody zmiennych.

    Kolumna, której nie ma w schemacie, przerywa przetwarzanie — oznacza to,
    że kwestionariusz zmienił się względem kodu i wynik byłby niepełny.
    """
    df = df.copy()
    df.columns = [_normalize(c) for c in df.columns]

    unknown = [c for c in df.columns if c not in schema.COLUMN_NAMES]
    if unknown:
        raise ValueError(
            "Kolumny nieopisane w schemacie: "
            + ", ".join(unknown)
            + ". Uzupełnij schema.COLUMN_NAMES albo sprawdź, czy plik pochodzi z właściwej ankiety."
        )

    return df.rename(columns=schema.COLUMN_NAMES)


def _merge_faculties(series: pd.Series) -> pd.Series:
    """Zamienia kody wydziałów na nazwy, a odpowiedzi wielokrotne na jedną kategorię."""
    multiple = series.apply(lambda x: isinstance(x, str) and "," in x)
    return series.where(~multiple, schema.MULTIPLE_FACULTIES).replace(schema.FACULTIES)


def shorten_answers(df: pd.DataFrame) -> pd.DataFrame:
    """Skraca rozwlekłe odpowiedzi jakościowe do postaci nadającej się na wykres."""
    df = df.copy()
    df["wydzial"] = _merge_faculties(df["wydzial"])

    for column, shortcuts in schema.ANSWER_SHORTCUTS.items():
        df[column] = df[column].replace(shortcuts)

    return df


def _recode_column(series: pd.Series, code: str) -> pd.Series:
    """Zamienia odpowiedzi jednej zmiennej na wartości liczbowe.

    Odpowiedź spoza schematu i spoza listy znaczników braku przerywa
    przetwarzanie. Wcześniejsza wersja pozostawiała ją bez zmian, przez co
    kolumna zostawała tekstowa i po cichu wypadała z analiz numerycznych.
    """
    mapping = schema.coding_map(code)
    allowed = set(mapping) | set(schema.MISSING_MARKERS)

    foreign = {v for v in series.dropna().astype(str).unique() if v not in allowed}
    if foreign:
        raise ValueError(f"Zmienna '{code}' zawiera odpowiedzi spoza schematu: {sorted(foreign)}")

    return pd.to_numeric(series.map(mapping), errors="raise")


def recode_scales(df: pd.DataFrame) -> pd.DataFrame:
    """Zamienia wszystkie skale przedziałowe na wartości liczbowe.

    Konwersja typu jest jawna. Do pandas 2.1 `Series.replace` samo rzutowało
    kolumnę na typ liczbowy; od pandas 2.2 to zachowanie jest wycofane, a w 3.0
    usunięte — kolumna zostawała typu `object` i była pomijana przez wszystkie
    funkcje sprawdzające `is_numeric_dtype`, w tym rankingi korelacji.
    """
    df = df.copy()
    for code in schema.scaled_codes():
        if code in df.columns:
            df[code] = _recode_column(df[code], code)
    return df


def derive_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje zmienne pochodne: social jetlag i ogólny wskaźnik satysfakcji."""
    df = df.copy()

    # Bezwzględna różnica długości snu — interesuje nas wielkość rozjazdu
    # rytmu dobowego, nie jego kierunek.
    df["social_jetlag"] = (df["sen_h_weekend"] - df["sen_h_dni_robocze"]).abs()

    components = list(schema.SATISFACTION_COMPONENTS)
    incomplete = int(df[components].isna().any(axis=1).sum())
    if incomplete:
        raise ValueError(
            f"{incomplete} respondentów ma niekompletne składowe wskaźnika satysfakcji. "
            "Ustal regułę uśredniania przy brakach, zanim wskaźnik trafi do analiz."
        )
    df["sat_srednia"] = df[components].mean(axis=1)

    return df


def set_ordinal_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Nadaje kolejność zmiennym jakościowym porządkowym."""
    df = df.copy()
    for code in schema.ordinal_codes():
        present = set(df[code].dropna().unique())
        expected = set(schema.VARIABLES[code].order)
        if not present <= expected:
            raise ValueError(
                f"Zmienna '{code}' zawiera kategorie spoza zdefiniowanego porządku: "
                f"{sorted(present - expected)}"
            )
        df[code] = pd.Categorical(df[code], categories=schema.VARIABLES[code].order, ordered=True)
    return df


def _looks_numeric(series: pd.Series) -> bool:
    """Czy kolumna tekstowa przechowuje w rzeczywistości same liczby."""
    values = series.dropna()
    if values.empty:
        return False
    return all(isinstance(v, (int, float, np.number)) and not isinstance(v, bool) for v in values)


def validate_output(df: pd.DataFrame) -> None:
    """Weryfikuje, że przygotowana ramka nadaje się do analiz.

    Sprawdzenia celują w awarie ciche — takie, które nie rzucają wyjątku,
    tylko po cichu zawężają zbiór analizowanych zmiennych.
    """
    if len(df) < MIN_RESPONDENTS:
        raise ValueError(f"Zbiór ma tylko {len(df)} wierszy — oczekiwano co najmniej {MIN_RESPONDENTS}.")

    missing = set(schema.VARIABLES) - set(df.columns)
    if missing:
        raise ValueError(f"W wyniku brakuje zmiennych: {sorted(missing)}")

    # Kolumna, która ma zdefiniowaną skalę, musi po przekodowaniu być liczbowa.
    not_numeric = [
        code for code in schema.scaled_codes() if not pd.api.types.is_numeric_dtype(df[code])
    ]
    if not_numeric:
        raise ValueError(f"Zmienne ze skalą pozostały nieliczbowe: {not_numeric}")

    # Kolumna typu object przechowująca same liczby to typowy objaw
    # niedokończonej konwersji — analizy numeryczne pominęłyby ją bez ostrzeżenia.
    suspicious = [c for c in df.columns if df[c].dtype == object and _looks_numeric(df[c])]
    if suspicious:
        raise ValueError(f"Kolumny zawierają liczby, ale mają typ tekstowy: {suspicious}")


def prepare_data(path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Wczytuje i przygotowuje dane ankietowe.

    Zwraca ramkę gotową do analiz oraz tabelę mapowań kategorii na wartości
    liczbowe, wykorzystywaną przy opisywaniu osi wykresów i w aneksie raportu.
    """
    df = (
        load_raw(path)
        .pipe(drop_service_columns)
        .pipe(rename_columns)
        .pipe(shorten_answers)
        .pipe(recode_scales)
        .pipe(derive_indicators)
        .pipe(set_ordinal_categories)
    )
    validate_output(df)
    return df, schema.mapping_table()


__all__ = [
    "MIN_RESPONDENTS",
    "prepare_data",
    "load_raw",
    "drop_service_columns",
    "rename_columns",
    "shorten_answers",
    "recode_scales",
    "derive_indicators",
    "set_ordinal_categories",
    "validate_output",
]
