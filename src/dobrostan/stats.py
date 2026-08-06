"""Testy statystyczne i tabele wyników.

Moduł skupia procedury wykorzystywane w raporcie: korelację rang Spearmana,
testy U Manna-Whitneya i Kruskala-Wallisa wraz z testem post hoc Dunna, test
chi-kwadrat niezależności oraz korektę Benjaminiego-Hochberga.

Dwie decyzje wymagają uwagi przy czytaniu wyników:

**Kolejność grup jest deterministyczna.** Grupy porównywane w teście U
wyznaczamy z porządku kategorii (dla zmiennych porządkowych) albo alfabetycznie
— nigdy z kolejności wystąpienia w pliku. Wcześniej znak wielkości efektu
zależał od tego, kto pierwszy wypełnił ankietę.

**Korekta FDR obejmuje pełną rodzinę testów.** `spearman_ranking` liczy
korektę na wszystkich wykonanych porównaniach i dopiero potem obcina wynik do
`top_n`. Odwrotna kolejność — najpierw obcięcie, potem korekta — zaniża liczbę
porównań i czyni korektę zbyt łagodną.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy.stats import chi2_contingency, kruskal, mannwhitneyu, norm, spearmanr
from statsmodels.stats.multitest import multipletests

from . import schema

#: Progi interpretacyjne dla wielkości efektu (Cohen).
EFFECT_THRESHOLDS = ((0.10, "pomijalny"), (0.30, "mały"), (0.50, "umiarkowany"))

#: Domyślny poziom istotności przyjęty w całym raporcie.
ALPHA = 0.05


def describe_effect(value: float) -> str:
    """Opisuje wielkość efektu słownie na podstawie jej wartości bezwzględnej."""
    magnitude = abs(value)
    for threshold, name in EFFECT_THRESHOLDS:
        if magnitude < threshold:
            return name
    return "duży"


def format_p_value(p: float) -> str:
    """Formatuje wartość p do postaci używanej w tabelach raportu."""
    if pd.isna(p):
        return "—"
    return "<0,001" if p < 0.001 else f"{p:.3f}".replace(".", ",")


def format_number(value: float, decimals: int = 3) -> str:
    """Formatuje liczbę z przecinkiem dziesiętnym, zgodnie z polską konwencją."""
    if pd.isna(value):
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",")


def min_detectable_rb(n1: int, n2: int, alpha: float = ALPHA, power: float = 0.80) -> float:
    """Najmniejsza wielkość efektu, jaką test U wykryje przy danych liczebnościach.

    Odróżnia „grupy się nie różnią" od „grupy są za małe, żeby różnicę zobaczyć".
    Bez tej liczby wynik nieistotny w kilkunastoosobowej grupie czyta się jak
    dowód braku zależności, choć jest wyłącznie brakiem rozstrzygnięcia.

    Przybliżenie normalne rozkładu statystyki U; zwracana wartość to próg
    korelacji rangowo-dwuseryjnej przy zadanej mocy testu.
    """
    if min(n1, n2) < 1:
        return float("nan")

    z_alpha = norm.ppf(1 - alpha / 2)
    z_power = norm.ppf(power)
    sigma = np.sqrt((n1 + n2 + 1) / (12 * n1 * n2))
    return min(1.0, 2 * (0.5 + (z_alpha + z_power) * sigma) - 1)


def group_levels(series: pd.Series) -> list:
    """Zwraca poziomy zmiennej grupującej w deterministycznej kolejności.

    Dla zmiennych porządkowych zachowuje ich porządek, dla pozostałych sortuje
    rosnąco. Dzięki temu przypisanie „grupa 1"/„grupa 2" — a więc i znak
    wielkości efektu — nie zależy od kolejności wierszy w pliku.
    """
    values = series.dropna()
    if isinstance(series.dtype, pd.CategoricalDtype):
        return [level for level in series.cat.categories if (values == level).any()]
    return sorted(values.unique())


# ---------------------------------------------------------------------------
# Korelacje
# ---------------------------------------------------------------------------


def run_spearman(df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    """Korelacja rang Spearmana między dwiema zmiennymi."""
    data = df[[x, y]].dropna()

    if len(data) < 3 or data[x].nunique() < 2 or data[y].nunique() < 2:
        rho, p = np.nan, np.nan
    else:
        rho, p = spearmanr(data[x], data[y])

    return pd.DataFrame(
        {"zmienna_x": [x], "zmienna_y": [y], "n": [len(data)], "rho": [rho], "p": [p]}
    )


def fdr_correction(results: pd.DataFrame, p_col: str = "p", alpha: float = ALPHA) -> pd.DataFrame:
    """Dodaje skorygowane wartości p metodą Benjaminiego-Hochberga.

    Wywołuj na pełnej rodzinie testów. Zastosowanie korekty do podzbioru
    wyników (np. do dziesięciu najsilniejszych) zaniża liczbę porównań
    i sprawia, że korekta jest zbyt łagodna.
    """
    results = results.copy()
    usable = results[p_col].notna()

    results["p_fdr"] = np.nan
    results["istotne_fdr"] = False

    if usable.any():
        rejected, p_fdr, _, _ = multipletests(
            results.loc[usable, p_col], alpha=alpha, method="fdr_bh"
        )
        results.loc[usable, "p_fdr"] = p_fdr
        results.loc[usable, "istotne_fdr"] = rejected

    return results


def spearman_ranking(
    df: pd.DataFrame,
    target: str,
    exclude: list[str] | None = None,
    min_n: int = 30,
    top_n: int | None = None,
    alpha: float = ALPHA,
) -> pd.DataFrame:
    """Ranking korelacji Spearmana zmiennej `target` z pozostałymi zmiennymi.

    Korekta FDR jest liczona na wszystkich wykonanych porównaniach, a obcięcie
    do `top_n` następuje dopiero po niej. Kolumna `n_rodziny` zapisuje rozmiar
    rodziny testów, żeby dało się to zweryfikować w raporcie.

    Do rankingu wchodzą zmienne liczbowe oraz te zmienne jakościowe, których
    kolejność kategorii jest realną wielkością rosnącą (`schema.rankable_codes`).
    Nazwy zmiennych, które nie mogły wziąć udziału, trafiają do
    `ranking.attrs["pominiete"]` — ranking „najsilniejszych zależności", który
    milczy o tym, czego nie sprawdzał, jest mylący.
    """
    excluded = set(exclude or ())
    excluded.add(target)
    rankable = set(schema.rankable_codes())

    results = []
    skipped = []
    for column in df.columns:
        if column in excluded:
            continue

        series = _as_ranks(df[column], column in rankable)
        if series is None:
            skipped.append(column)
            continue
        if series.nunique(dropna=True) < 2:
            continue

        result = run_spearman(df.assign(**{column: series}), target, column)
        if result.loc[0, "n"] < min_n or pd.isna(result.loc[0, "rho"]):
            continue
        results.append(result)

    if not results:
        return pd.DataFrame()

    ranking = pd.concat(results, ignore_index=True)
    ranking["abs_rho"] = ranking["rho"].abs()

    # Korekta na pełnej rodzinie — przed jakimkolwiek obcięciem.
    ranking = fdr_correction(ranking, alpha=alpha)
    ranking["n_rodziny"] = len(ranking)

    ranking = ranking.sort_values("abs_rho", ascending=False, kind="stable").reset_index(drop=True)
    ranking = ranking.head(top_n) if top_n else ranking
    ranking.attrs["pominiete"] = sorted(skipped)
    return ranking


def _as_ranks(series: pd.Series, rankable: bool) -> pd.Series | None:
    """Zwraca serię nadającą się do korelacji rangowej albo None.

    Zmienne jakościowe zamieniamy na numery kategorii wyłącznie wtedy, gdy
    schemat potwierdza, że ich kolejność coś mierzy.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series
    if rankable and isinstance(series.dtype, pd.CategoricalDtype) and series.dtype.ordered:
        return series.cat.codes.where(series.notna())
    return None


def correlation_table(
    df: pd.DataFrame,
    x: str,
    outcomes: list[str],
    alpha: float = ALPHA,
) -> pd.DataFrame:
    """Korelacje jednej zmiennej z listą wskaźników dobrostanu, z korektą FDR.

    Kolumna `czesc_calosci` oznacza wiersze, których nie wolno czytać jak
    niezależnego wyniku, bo zmienne są powiązane konstrukcyjnie:

    * korelacja `sat_srednia` z własną składową (albo odwrotnie),
    * `sat_srednia` zestawiona w jednej tabeli ze swoimi składowymi — wskaźnik
      jest wtedy ważoną powtórką pozostałych wierszy, a nie osobnym ustaleniem.
    """
    results = pd.concat([run_spearman(df, x, y) for y in outcomes], ignore_index=True)
    results = fdr_correction(results, alpha=alpha)
    results["czesc_calosci"] = flag_part_whole(results["zmienna_y"], outcomes, x)

    return results.sort_values(
        "rho", key=lambda s: s.abs(), ascending=False, kind="stable"
    ).reset_index(drop=True)


def flag_part_whole(
    tested: pd.Series | list[str],
    outcomes: list[str],
    other: str | None = None,
) -> list[bool]:
    """Oznacza wyniki powiązane konstrukcyjnie z ogólnym wskaźnikiem satysfakcji.

    `sat_srednia` jest średnią siedmiu wymiarów satysfakcji, więc nie jest
    ustaleniem niezależnym, gdy:

    * zestawiamy ją z własną składową (albo składową z nią),
    * stoi w jednej tabeli obok swoich składowych — jest wtedy ich zagregowaną
      powtórką, a nie osobnym wynikiem, i dodatkowo powiększa rodzinę testów.

    Wspólna dla korelacji, porównań grup i testu Kruskala-Wallisa — reguła
    obowiązująca tylko w jednej z tych ścieżek dawałaby ostrzeżenie zależne od
    tego, którym testem zbadano ten sam układ zmiennych.
    """
    components = set(schema.SATISFACTION_COMPONENTS)
    shares_table = bool(set(outcomes) & components)

    return [
        (other == "sat_srednia" and y in components)
        or (y == "sat_srednia" and (other in components or shares_table))
        for y in tested
    ]


# ---------------------------------------------------------------------------
# Porównania grup
# ---------------------------------------------------------------------------


def run_mannwhitney(df: pd.DataFrame, group: str, outcome: str) -> pd.DataFrame:
    """Test U Manna-Whitneya dla dwóch niezależnych grup.

    Wielkość efektu podana jest jako korelacja rangowo-dwuseryjna. Wartość
    dodatnia oznacza, że `grupa_1` osiąga wyższe wyniki niż `grupa_2`; grupy
    wyznaczane są w deterministycznej kolejności (patrz `group_levels`).
    """
    data = df[[group, outcome]].dropna()
    levels = group_levels(data[group])

    if len(levels) != 2:
        raise ValueError(
            f"Zmienna '{group}' musi mieć dokładnie 2 grupy, znaleziono {len(levels)}: {levels}"
        )

    first, second = levels
    x1 = data.loc[data[group] == first, outcome]
    x2 = data.loc[data[group] == second, outcome]

    u, p = mannwhitneyu(x1, x2, alternative="two-sided")

    # Konwencja: r_rb > 0 oznacza przewagę pierwszej grupy.
    r_rb = 2 * u / (len(x1) * len(x2)) - 1

    return pd.DataFrame(
        {
            "grupa": [group],
            "wynik": [outcome],
            "grupa_1": [first],
            "grupa_2": [second],
            "n_1": [len(x1)],
            "n_2": [len(x2)],
            "mediana_1": [x1.median()],
            "mediana_2": [x2.median()],
            "U": [u],
            "p": [p],
            "r_rb": [r_rb],
            "efekt": [describe_effect(r_rb)],
        }
    )


def comparison_table(
    df: pd.DataFrame,
    group: str,
    outcomes: list[str],
    alpha: float = ALPHA,
) -> pd.DataFrame:
    """Test U Manna-Whitneya dla listy wskaźników, z korektą FDR na całej rodzinie."""
    results = pd.concat(
        [run_mannwhitney(df, group, outcome) for outcome in outcomes], ignore_index=True
    )
    results = fdr_correction(results, alpha=alpha)
    results["czesc_calosci"] = flag_part_whole(results["wynik"], outcomes)
    return results.sort_values("p_fdr", kind="stable").reset_index(drop=True)


def run_kruskal(df: pd.DataFrame, group: str, outcome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Test Kruskala-Wallisa wraz z zestawieniem statystyk opisowych grup."""
    data = df[[group, outcome]].dropna()
    grouped = data.groupby(group, observed=True)
    samples = [g[outcome].values for _, g in grouped]

    if len(samples) < 2:
        raise ValueError(f"Zmienna '{group}' musi zawierać co najmniej dwie grupy.")

    h, p = kruskal(*samples)
    n, k = len(data), len(samples)

    # η²_H — udział wariancji rang wyjaśniony przez podział na grupy.
    # Nie mylić z epsilon-kwadratem, który liczy się inaczej: ε² = H(n+1)/(n²−1).
    eta2 = max(0.0, (h - k + 1) / (n - k))

    result = pd.DataFrame(
        {"grupa": [group], "wynik": [outcome], "n": [n], "k": [k], "H": [h], "p": [p], "eta2_H": [eta2]}
    )

    summary = (
        grouped[outcome]
        .agg(N="count", Mediana="median", Średnia="mean", SD="std")
        .reset_index()
    )

    return result, summary


def kruskal_table(
    df: pd.DataFrame,
    group: str,
    outcomes: list[str],
    alpha: float = ALPHA,
) -> pd.DataFrame:
    """Test Kruskala-Wallisa dla listy wskaźników, z korektą FDR na całej rodzinie.

    Odpowiednik `comparison_table` dla porównań wielogrupowych — dzięki temu
    obie ścieżki liczą korektę i oznaczają zależności część-całość tak samo.
    """
    results = pd.concat(
        [run_kruskal(df, group, outcome)[0] for outcome in outcomes], ignore_index=True
    )
    results = fdr_correction(results, alpha=alpha)
    results["czesc_calosci"] = flag_part_whole(results["wynik"], outcomes)
    return results


def run_dunn(df: pd.DataFrame, group: str, outcome: str, p_adjust: str | None = None) -> pd.DataFrame:
    """Test post hoc Dunna — porównania parami po teście Kruskala-Wallisa.

    Domyślnie bez wewnętrznej korekty; stosuj `fdr_correction` na wyniku,
    żeby wszystkie korekty w raporcie pochodziły z jednego miejsca.
    """
    data = df[[group, outcome]].dropna()
    posthoc = sp.posthoc_dunn(data, val_col=outcome, group_col=group, p_adjust=p_adjust)

    # Porównywane grupy zwracamy osobno, a nie jako gotowy napis „A vs B".
    # Sklejony napis kusi, żeby podmieniać w nim kody na etykiety, a kody bywają
    # swoimi prefiksami („0" w „0.0", „4" w „4.0") i podmiana je przekręca.
    comparisons = [
        {
            "grupa": group,
            "wynik": outcome,
            "grupa_1": g1,
            "grupa_2": g2,
            "p": posthoc.loc[g1, g2],
        }
        for i, g1 in enumerate(posthoc.index)
        for j, g2 in enumerate(posthoc.columns)
        if j > i
    ]

    return pd.DataFrame(comparisons)


def run_chi2(df: pd.DataFrame, x: str, y: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Test chi-kwadrat niezależności wraz z siłą związku (V Craméra)."""
    data = df[[x, y]].dropna()
    table = pd.crosstab(data[x], data[y])

    if table.empty:
        raise ValueError(f"Brak danych do tabeli kontyngencji '{x}' × '{y}'.")

    chi2, p, dof, _ = chi2_contingency(table)
    n = table.values.sum()
    rows, cols = table.shape

    smaller_dim = min(rows - 1, cols - 1)
    cramers_v = np.sqrt(chi2 / (n * smaller_dim)) if smaller_dim > 0 else np.nan

    result = pd.DataFrame(
        {"x": [x], "y": [y], "n": [n], "chi2": [chi2], "dof": [dof], "p": [p], "cramers_v": [cramers_v]}
    )

    return result, table


# ---------------------------------------------------------------------------
# Tabele opisowe
# ---------------------------------------------------------------------------


def frequency_table(
    df: pd.DataFrame,
    column: str,
    sort: str = "index",
    column_name: str | None = None,
    value_labels: dict | None = None,
    na_label: str | None = None,
) -> pd.DataFrame:
    """Tabela liczebności zmiennej kategorycznej.

    Braki danych są uwzględniane w mianowniku udziałów procentowych tylko
    wtedy, gdy podano `na_label` — czyli gdy brak jest świadomie prezentowany
    jako osobna kategoria (np. „I semestr — brak ocen"). Bez `na_label` braki
    wypadają z zestawienia, żeby nie tworzyć słupka bez podpisu.
    """
    counts = df[column].value_counts(dropna=na_label is None)

    if sort == "index":
        counts = counts.sort_index()
    elif sort == "count":
        counts = counts.sort_values(ascending=False)

    categories = counts.index
    if value_labels is not None:
        categories = [
            na_label if pd.isna(value) and na_label is not None else value_labels.get(value, value)
            for value in categories
        ]
    elif na_label is not None:
        categories = [na_label if pd.isna(value) else value for value in categories]

    return pd.DataFrame(
        {
            column_name or "Kategoria": categories,
            "Liczebność": counts.values,
            "Udział [%]": (counts.values / counts.sum() * 100).round(1),
        }
    ).reset_index(drop=True)


def cross_table(
    df: pd.DataFrame,
    x: str,
    y: str,
    normalize: bool = False,
    decimals: int = 1,
    x_labels: dict | None = None,
    y_labels: dict | None = None,
) -> pd.DataFrame:
    """Tabela krzyżowa dwóch zmiennych, opcjonalnie w udziałach wierszowych."""
    table = pd.crosstab(df[x], df[y], normalize="index" if normalize else False, dropna=False)

    if x_labels is not None:
        table.index = [x_labels.get(v, v) for v in table.index]
    if y_labels is not None:
        table.columns = [y_labels.get(v, v) for v in table.columns]

    return table.mul(100).round(decimals) if normalize else table


__all__ = [
    "ALPHA",
    "describe_effect",
    "format_p_value",
    "format_number",
    "group_levels",
    "run_spearman",
    "fdr_correction",
    "spearman_ranking",
    "correlation_table",
    "run_mannwhitney",
    "comparison_table",
    "run_kruskal",
    "min_detectable_rb",
    "kruskal_table",
    "flag_part_whole",
    "run_dunn",
    "run_chi2",
    "frequency_table",
    "cross_table",
]
