"""Formatowanie wyników do postaci prezentowanej w raporcie.

Warstwa oddzielona od `stats`: tam liczby, tutaj ich postać czytelna dla
człowieka — polskie nazwy zmiennych, przecinek dziesiętny, progi istotności.

Bez tego podziału notebook powtarzał ten sam kilkunastolinijkowy blok
formatowania przy każdym teście, a formatowanie liczb rozjeżdżało się między
sekcjami (część tabel z przecinkiem, część z kropką).
"""

from __future__ import annotations

import pandas as pd

from . import schema
from .stats import format_number, format_p_value

#: Oznaczenie wyniku po korekcie — używane spójnie we wszystkich tabelach.
YES_NO = {True: "Tak", False: "Nie"}


def _describe(code: str) -> str:
    """Pełna nazwa zmiennej; nieznany kod zwracamy bez zmian."""
    return schema.descriptions().get(code, code)


def spearman(result: pd.DataFrame) -> pd.DataFrame:
    """Wynik pojedynczej korelacji Spearmana jako tabela do wyświetlenia."""
    return pd.DataFrame(
        {
            "Zmienna X": result["zmienna_x"].map(_describe),
            "Zmienna Y": result["zmienna_y"].map(_describe),
            "N": result["n"],
            "ρ": result["rho"].map(lambda v: format_number(v, 3)),
            "p": result["p"].map(format_p_value),
        }
    )


def correlations(result: pd.DataFrame, x_name: str | None = None) -> pd.DataFrame:
    """Tabela korelacji jednej zmiennej z wieloma wskaźnikami.

    Kolumna „Uwaga" oznacza pary powiązane konstrukcyjnie — ogólny wskaźnik
    satysfakcji zawiera swoje składowe, więc taka korelacja jest zawyżona
    z definicji i nie może być czytana jak zwykły wynik.
    """
    table = pd.DataFrame(
        {
            "Obszar": result["zmienna_y"].map(_describe),
            "N": result["n"],
            "ρ": result["rho"].map(lambda v: format_number(v, 3)),
            "p (FDR)": result["p_fdr"].map(format_p_value),
            "Istotna?": result["istotne_fdr"].map(YES_NO),
        }
    )

    if "czesc_calosci" in result.columns and result["czesc_calosci"].any():
        table["Uwaga"] = result["czesc_calosci"].map(
            {True: "zależność część-całość", False: ""}
        )

    if x_name:
        table.insert(0, "Zmienna", x_name)

    return table.reset_index(drop=True)


def mann_whitney(result: pd.DataFrame, value_labels: dict | None = None) -> pd.DataFrame:
    """Wynik testu U Manna-Whitneya jako tabela do wyświetlenia."""
    medians = (
        (lambda s: s.map(value_labels)) if value_labels else (lambda s: s.map(lambda v: format_number(v, 1)))
    )

    return pd.DataFrame(
        {
            "Grupa 1": result["grupa_1"],
            "Grupa 2": result["grupa_2"],
            "N₁": result["n_1"],
            "N₂": result["n_2"],
            "Mediana 1": medians(result["mediana_1"]),
            "Mediana 2": medians(result["mediana_2"]),
            "U": result["U"].map(lambda v: format_number(v, 1)),
            "p": result["p"].map(format_p_value),
            "r_rb": result["r_rb"].map(lambda v: format_number(v, 3)),
            "Siła efektu": result["efekt"],
        }
    )


def comparisons(result: pd.DataFrame) -> pd.DataFrame:
    """Tabela porównań grupowych dla wielu wskaźników, po korekcie FDR."""
    return pd.DataFrame(
        {
            "Obszar": result["wynik"].map(_describe),
            "p (FDR)": result["p_fdr"].map(format_p_value),
            "|r_rb|": result["r_rb"].abs().map(lambda v: format_number(v, 3)),
            "Siła efektu": result["efekt"],
            "Różnica istotna?": result["istotne_fdr"].map(YES_NO),
        }
    ).reset_index(drop=True)


def kruskal(result: pd.DataFrame) -> pd.DataFrame:
    """Tabela wyników testu Kruskala-Wallisa dla wielu wskaźników."""
    return pd.DataFrame(
        {
            "Obszar": result["wynik"].map(_describe),
            "H": result["H"].map(lambda v: format_number(v, 2)),
            "η²": result["eta2_H"].map(lambda v: format_number(v, 3)),
            "p (FDR)": result["p_fdr"].map(format_p_value),
            "Istotna?": result["istotne_fdr"].map(YES_NO),
        }
    ).reset_index(drop=True)


def dunn(result: pd.DataFrame, value_labels: dict | None = None) -> pd.DataFrame:
    """Tabela porównań post hoc testem Dunna."""
    comparison = result["porownanie"]
    if value_labels:
        for code, label in value_labels.items():
            comparison = comparison.str.replace(str(code), str(label), regex=False)

    return pd.DataFrame(
        {
            "Porównanie": comparison,
            "p (FDR)": result["p_fdr"].map(format_p_value),
            "Istotna?": result["istotne_fdr"].map(YES_NO),
        }
    ).reset_index(drop=True)


def chi2(result: pd.DataFrame) -> pd.DataFrame:
    """Tabela wyniku testu chi-kwadrat niezależności."""
    return pd.DataFrame(
        {
            "χ²": result["chi2"].map(lambda v: format_number(v, 2)),
            "df": result["dof"],
            "N": result["n"],
            "p": result["p"].map(format_p_value),
            "V Craméra": result["cramers_v"].map(lambda v: format_number(v, 3)),
        }
    )


def ranking(result: pd.DataFrame) -> pd.DataFrame:
    """Ranking korelacji wraz z rozmiarem rodziny testów objętej korektą."""
    return pd.DataFrame(
        {
            "Zmienna": result["zmienna_y"].map(_describe),
            "N": result["n"],
            "ρ": result["rho"].map(lambda v: format_number(v, 3)),
            "p (FDR)": result["p_fdr"].map(format_p_value),
            "Istotna?": result["istotne_fdr"].map(YES_NO),
        }
    ).reset_index(drop=True)


def group_sizes(series: pd.Series, name: str = "Grupa") -> pd.DataFrame:
    """Liczebności grup — wyświetlane przed każdym porównaniem."""
    return series.value_counts().rename_axis(name).to_frame("Liczebność")


def regression(model, names: dict[str, str] | None = None) -> pd.DataFrame:
    """Współczynniki modelu regresji jako tabela do wyświetlenia."""
    table = model.summary2().tables[1].reset_index()
    table.columns = ["Zmienna", "β", "SE", "t", "p", "CI dolna", "CI górna"]

    if names:
        table["Zmienna"] = table["Zmienna"].replace(names)

    return pd.DataFrame(
        {
            "Zmienna": table["Zmienna"],
            "β": table["β"].map(lambda v: format_number(v, 3)),
            "95% CI": [
                f"[{format_number(lo, 2)}; {format_number(hi, 2)}]"
                for lo, hi in zip(table["CI dolna"], table["CI górna"])
            ],
            "p": table["p"].map(format_p_value),
        }
    )


def model_fit(model, label: str) -> pd.DataFrame:
    """Jednowierszowe podsumowanie dopasowania modelu regresji."""
    return pd.DataFrame(
        {
            "Model": [label],
            "N": [int(model.nobs)],
            "R²": [format_number(model.rsquared, 3)],
            "skoryg. R²": [format_number(model.rsquared_adj, 3)],
            "F": [format_number(model.fvalue, 2)],
            "p": [format_p_value(model.f_pvalue)],
        }
    )


__all__ = [
    "spearman",
    "correlations",
    "mann_whitney",
    "comparisons",
    "kruskal",
    "dunn",
    "chi2",
    "ranking",
    "group_sizes",
    "regression",
    "model_fit",
]
