"""Wykresy raportu.

Wszystkie funkcje zwracają parę `(fig, ax)` i nie wywołują `plt.show()` —
o wyświetleniu decyduje notebook, a nie warstwa rysująca. Dzięki temu ten sam
wykres da się wstawić w siatkę `subplots` albo zapisać do pliku.

Paleta
------
Barwy pochodzą z palety zwalidowanej pod kątem daltonizmu (ΔE w OKLab,
symulacja Machado-Oliveira-Fernandes 2009):

* `CATEGORICAL` — porównania grup, najwyżej trzy serie; najgorsza para
  wszystkich kombinacji: CVD ΔE 9,2 · widzenie normalne ΔE 24,0
* `LIKERT` — skale 1-5 na słupkach skumulowanych; skala rozbieżna
  czerwony-szary-niebieski, najgorsza para sąsiednia: CVD ΔE 13,7 ·
  widzenie normalne ΔE 17,0

Kolor na skali Likerta koduje **pozycję na skali odpowiedzi (1→5)**, a nie
ocenę zjawiska. Dla satysfakcji 5 oznacza stan pożądany, dla stresu — wręcz
przeciwnie; kierunek interpretacji podaje opis wykresu, nie barwa.

Część barw ma kontrast do tła poniżej 3:1, co zgodnie z regułą ulgi wymaga
widocznych etykiet liczbowych. Wykresy słupkowe podpisują wartości wprost,
więc identyfikacja nigdy nie opiera się wyłącznie na kolorze.
"""

from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter
from scipy.stats import t as student_t

from .stats import cross_table, frequency_table

# --- paleta ----------------------------------------------------------------

#: Barwy serii w porównaniach grupowych. Przypisywane w stałej kolejności.
CATEGORICAL = ("#2a78d6", "#eb6834", "#1baf7a")

#: Skala rozbieżna dla pozycji 1-5 na skali odpowiedzi.
LIKERT = ("#9c2b2b", "#e07b7b", "#c9c8c3", "#6da7ec", "#184f95")

#: Jednobarwna skala natężenia — heatmapy liczebności.
SEQUENTIAL = LinearSegmentedColormap.from_list(
    "dobrostan_sekwencyjna", ["#eef4fd", "#9ec5f4", "#3987e5", "#1c5cab", "#0d366b"]
)

#: Skala rozbieżna dla współczynników korelacji (-1 … 0 … 1).
DIVERGING = LinearSegmentedColormap.from_list(
    "dobrostan_rozbiezna", ["#9c2b2b", "#e07b7b", "#f2f1ee", "#6da7ec", "#184f95"]
)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

#: Ziarno generatora dla rozrzutu punktów — bez niego wykres zmieniałby się
#: przy każdym uruchomieniu, a raport przestawał być odtwarzalny.
JITTER_SEED = 20260105


def apply_style() -> None:
    """Ustawia wspólny styl wykresów. Wywoływane raz, na początku notebooka."""
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK_MUTED,
            "axes.titlecolor": INK,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.5,
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "text.color": INK,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "legend.title_fontsize": 9,
            "figure.dpi": 110,
            "axes.prop_cycle": plt.cycler(color=list(CATEGORICAL)),
        }
    )


def wrap_label(text: object, width: int = 16) -> str:
    """Łamie długą etykietę na kilka wierszy.

    Łamanie tekstu jest decyzją prezentacyjną i należy do wykresu. Wcześniej
    znaki nowej linii były wpisane na stałe w nazwy zmiennych, przez co ta sama
    etykieta wymagała odwracania („unwrap") w tabelach.
    """
    if pd.isna(text):
        return ""
    return "\n".join(textwrap.wrap(str(text), width=width)) or str(text)


def _wrap_ticks(ax, axis: str = "x", width: int = 16) -> None:
    """Łamie etykiety osi, jeśli są dłuższe niż `width`."""
    getter, setter = (ax.get_xticklabels, ax.set_xticklabels) if axis == "x" else (
        ax.get_yticklabels,
        ax.set_yticklabels,
    )
    setter([wrap_label(label.get_text(), width) for label in getter()])


def _relative_luminance(color: str) -> float:
    """Luminancja względna barwy wg definicji WCAG."""
    channels = []
    for value in mcolors.to_rgb(color):
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _label_color(background: str) -> str:
    """Dobiera kolor napisu na tle segmentu — biały albo ciemny atrament.

    Skala Likerta ma jasny neutralny środek; stały biały napis byłby na nim
    nieczytelny. Wybieramy wariant o wyższym kontraście.
    """
    luminance = _relative_luminance(background)
    contrast_white = 1.05 / (luminance + 0.05)
    contrast_ink = (luminance + 0.05) / (_relative_luminance(INK) + 0.05)
    return "white" if contrast_white >= contrast_ink else INK


def _new_axes(ax, figsize):
    """Zwraca (fig, ax) — tworzy nowe osie albo korzysta z przekazanych."""
    if ax is None:
        return plt.subplots(figsize=figsize)
    return ax.figure, ax


def _finish(fig, ax) -> None:
    """Domyka wykres — układ dopasowujemy tylko dla samodzielnych rysunków."""
    ax.set_axisbelow(True)
    if len(fig.axes) == 1:
        fig.tight_layout()


# ---------------------------------------------------------------------------
# Rozkłady
# ---------------------------------------------------------------------------


def plot_distribution(
    df: pd.DataFrame,
    column: str,
    value_labels: dict | None = None,
    na_label: str | None = None,
    sort: str = "index",
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str = "Udział respondentów [%]",
    show_n: bool = True,
    horizontal: bool = False,
    wrap: int = 16,
    figsize: tuple[float, float] = (8, 5),
    ax=None,
):
    """Procentowy rozkład odpowiedzi dla jednej zmiennej."""
    table = frequency_table(
        df, column, sort=sort, value_labels=value_labels, na_label=na_label
    )
    category_col = table.columns[0]
    fig, ax = _new_axes(ax, figsize)

    categories = [wrap_label(v, wrap) for v in table[category_col]]
    shares = table["Udział [%]"]

    bars = (ax.barh if horizontal else ax.bar)(categories, shares, color=CATEGORICAL[0])

    if show_n:
        labels = [f"{p:.1f}% (n={n})" for p, n in zip(shares, table["Liczebność"])]
        if not horizontal:
            labels = [label.replace(" (", "\n(") for label in labels]
    else:
        labels = [f"{p:.1f}%" for p in shares]

    ax.bar_label(bars, labels=labels, padding=3, fontsize=8.5, color=INK_MUTED)

    ax.set_title(f"{title or column} (N = {int(table['Liczebność'].sum())})")

    upper = min(100, shares.max() * 1.22)
    if horizontal:
        ax.set_xlabel(ylabel)
        ax.set_ylabel(xlabel or "")
        ax.set_xlim(0, upper)
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=100))
        ax.grid(axis="x")
        ax.invert_yaxis()
    else:
        ax.set_xlabel(xlabel or "")
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, upper)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
        ax.grid(axis="y")

    _finish(fig, ax)
    return fig, ax


def plot_distribution_by_group(
    df: pd.DataFrame,
    column: str,
    groupby: str,
    value_labels: dict | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str = "Udział respondentów [%]",
    legend_title: str | None = None,
    wrap: int = 16,
    figsize: tuple[float, float] = (9, 5),
    ax=None,
):
    """Rozkład odpowiedzi porównany między grupami.

    Udziały liczone są wewnątrz każdej grupy, więc słupki jednego koloru
    sumują się do 100% — porównujemy kształt rozkładu, nie liczebność grup.
    """
    data = df[[column, groupby]].dropna()
    table = data.groupby([column, groupby], observed=True).size().unstack(fill_value=0)
    table = table.div(table.sum(axis=0), axis=1) * 100

    if value_labels is not None:
        table.index = [value_labels.get(v, v) for v in table.index]
    table.index = [wrap_label(v, wrap) for v in table.index]

    fig, ax = _new_axes(ax, figsize)
    table.plot(kind="bar", ax=ax, color=list(CATEGORICAL[: table.shape[1]]), width=0.78)

    for container in ax.containers:
        ax.bar_label(
            container,
            labels=[f"{v:.1f}%" if v > 0 else "" for v in container.datavalues],
            padding=3,
            fontsize=8,
            color=INK_MUTED,
        )

    ax.set_title(title or column)
    ax.set_xlabel(xlabel or "")
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.grid(axis="y")
    ax.tick_params(axis="x", labelrotation=0)
    ax.legend(title=legend_title or groupby)

    _finish(fig, ax)
    return fig, ax


def plot_stacked_likert(
    df: pd.DataFrame,
    x: str,
    y: str,
    x_labels: dict | None = None,
    y_labels: dict | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str = "Udział respondentów [%]",
    legend_title: str | None = None,
    show_group_size: bool = True,
    min_label_percent: float = 5.0,
    wrap: int = 14,
    figsize: tuple[float, float] = (9, 6),
    ax=None,
):
    """Skumulowany rozkład odpowiedzi `y` w kategoriach zmiennej `x`.

    Segmenty rozdziela cienka biała przerwa, a udziały poniżej
    `min_label_percent` pozostają bez etykiety, żeby nie zlewały się w szum.
    """
    shares = cross_table(df, x, y, normalize=True, x_labels=x_labels, y_labels=y_labels)
    counts = cross_table(df, x, y, normalize=False, x_labels=x_labels).sum(axis=1)

    fig, ax = _new_axes(ax, figsize)

    colors = list(LIKERT[: shares.shape[1]]) if shares.shape[1] <= len(LIKERT) else None
    shares.plot(kind="bar", stacked=True, ax=ax, color=colors, width=0.72, edgecolor=SURFACE, linewidth=1.6)

    segment_colors = colors or [CATEGORICAL[0]] * len(ax.containers)
    for container, background in zip(ax.containers, segment_colors):
        ax.bar_label(
            container,
            labels=[f"{h:.1f}%" if h >= min_label_percent else "" for h in container.datavalues],
            label_type="center",
            fontsize=8.5,
            color=_label_color(background),
        )

    if show_group_size:
        ax.set_xticks(range(len(shares.index)))
        ax.set_xticklabels(
            [f"{wrap_label(v, wrap)}\n(N={int(counts.get(v, 0))})" for v in shares.index]
        )
    else:
        _wrap_ticks(ax, "x", wrap)

    ax.set_title(title or f"{y} względem {x}")
    ax.set_xlabel(xlabel or "")
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.tick_params(axis="x", labelrotation=0)
    ax.grid(axis="y")

    # Odwrócona kolejność w legendzie odpowiada układowi segmentów na słupku.
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles[::-1],
        labels[::-1],
        title=legend_title or y,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
    )

    _finish(fig, ax)
    return fig, ax


def plot_box(
    df: pd.DataFrame,
    x: str,
    y: str,
    x_labels: dict | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    show_points: bool = False,
    wrap: int = 14,
    figsize: tuple[float, float] = (8, 5),
    ax=None,
):
    """Rozkład zmiennej liczbowej `y` w kategoriach zmiennej `x`."""
    data = df[[x, y]].dropna()
    grouped = list(data.groupby(x, observed=True))
    groups = [group[y].values for _, group in grouped]

    labels = [
        wrap_label((x_labels or {}).get(name, name), wrap) for name, _ in grouped
    ]

    fig, ax = _new_axes(ax, figsize)
    box = ax.boxplot(groups, tick_labels=labels, patch_artist=True, widths=0.55)

    for patch in box["boxes"]:
        patch.set_facecolor(CATEGORICAL[0])
        patch.set_alpha(0.55)
        patch.set_edgecolor(CATEGORICAL[0])
    for element in ("whiskers", "caps", "medians"):
        for artist in box[element]:
            artist.set_color(INK_MUTED)
    for median in box["medians"]:
        median.set_linewidth(2)

    if show_points:
        rng = np.random.default_rng(JITTER_SEED)
        for position, values in enumerate(groups, start=1):
            ax.scatter(
                rng.normal(position, 0.045, len(values)),
                values,
                alpha=0.35,
                s=12,
                color=INK_MUTED,
                zorder=3,
            )

    ax.set_title(title or f"{y} względem {x}")
    ax.set_xlabel(xlabel or "")
    ax.set_ylabel(ylabel or "")
    ax.grid(axis="y")

    _finish(fig, ax)
    return fig, ax


# ---------------------------------------------------------------------------
# Zależności
# ---------------------------------------------------------------------------


def plot_correlation_heatmap(
    df: pd.DataFrame,
    columns: list[str],
    labels: dict | None = None,
    method: str = "spearman",
    title: str = "Macierz korelacji",
    lower_triangle: bool = True,
    figsize: tuple[float, float] = (7, 5.5),
    ax=None,
):
    """Macierz korelacji wybranych zmiennych."""
    corr = df[columns].corr(method=method)
    if labels is not None:
        names = [wrap_label(labels.get(c, c), 14) for c in columns]
        corr.index, corr.columns = names, names

    mask = np.triu(np.ones_like(corr, dtype=bool), k=0) if lower_triangle else None

    fig, ax = _new_axes(ax, figsize)
    sns.heatmap(
        corr,
        mask=mask,
        annot=True,
        fmt=".2f",
        annot_kws={"fontsize": 9},
        cmap=DIVERGING,
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=1.2,
        linecolor=SURFACE,
        cbar_kws={"label": f"ρ {method.capitalize()}", "shrink": 0.85},
        ax=ax,
    )

    ax.set_title(title, pad=12)
    ax.tick_params(axis="both", rotation=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    _finish(fig, ax)
    return fig, ax


def plot_correlation_ranking(
    ranking: pd.DataFrame,
    labels: dict | None = None,
    variable_col: str = "zmienna_y",
    value_col: str = "rho",
    significance_col: str = "istotne_fdr",
    title: str | None = None,
    figsize: tuple[float, float] = (8, 5),
    ax=None,
):
    """Ranking korelacji Spearmana.

    Słupki zmiennych, które nie przeszły korekty FDR, są wyszarzone i opatrzone
    gwiazdką — wynik nieistotny nie powinien wyglądać tak samo jak istotny.
    """
    data = ranking.sort_values(value_col).copy()

    if labels is not None:
        data["label"] = data[variable_col].map(labels).fillna(data[variable_col])
    else:
        data["label"] = data[variable_col]

    significant = (
        data[significance_col] if significance_col in data.columns else pd.Series(True, index=data.index)
    )
    colors = [CATEGORICAL[0] if s else AXIS for s in significant]

    fig, ax = _new_axes(ax, figsize)
    bars = ax.barh(data["label"], data[value_col], color=colors)

    ax.bar_label(
        bars,
        labels=[
            f"{v:.2f}".replace(".", ",") + ("" if s else " *")
            for v, s in zip(data[value_col], significant)
        ],
        padding=4,
        fontsize=8.5,
        color=INK_MUTED,
    )

    ax.axvline(0, color=AXIS, linewidth=1)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("ρ Spearmana")
    ax.set_title(title or "")
    ax.grid(axis="x")

    if not significant.all():
        ax.text(
            0.5,
            -0.16,
            "* nieistotne po korekcie Benjaminiego-Hochberga",
            transform=ax.transAxes,
            ha="center",
            fontsize=8,
            color=INK_MUTED,
        )

    _finish(fig, ax)
    return fig, ax


def plot_transition_heatmap(
    df: pd.DataFrame,
    x: str,
    y: str,
    x_labels: dict | None = None,
    y_labels: dict | None = None,
    normalize: bool = False,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (6.5, 5),
    ax=None,
):
    """Heatmapa liczebności (lub udziałów) dla dwóch zmiennych porządkowych."""
    data = df[[x, y]].dropna()
    table = pd.crosstab(data[y], data[x])
    if normalize:
        table = table / table.values.sum() * 100

    ticks_x = [wrap_label((x_labels or {}).get(v, v), 12) for v in table.columns]
    ticks_y = [wrap_label((y_labels or {}).get(v, v), 12) for v in table.index]

    fig, ax = _new_axes(ax, figsize)
    image = ax.imshow(table.values, cmap=SEQUENTIAL, aspect="auto", origin="lower")

    threshold = table.values.max() * 0.55
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            value = table.iloc[i, j]
            ax.text(
                j,
                i,
                f"{value:.1f}%" if normalize else str(int(value)),
                ha="center",
                va="center",
                fontsize=9,
                color="white" if value > threshold else INK,
            )

    ax.set_xticks(np.arange(len(ticks_x)), ticks_x)
    ax.set_yticks(np.arange(len(ticks_y)), ticks_y)
    ax.set_xlabel(xlabel or x)
    ax.set_ylabel(ylabel or y)
    ax.set_title(title or f"{y} względem {x}")

    bar = fig.colorbar(image, ax=ax)
    bar.set_label("Udział [%]" if normalize else "Liczba respondentów")

    for spine in ax.spines.values():
        spine.set_visible(False)

    _finish(fig, ax)
    return fig, ax


def plot_mean_ci(
    df: pd.DataFrame,
    x: str,
    y: str,
    x_labels: dict | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "Średnia",
    confidence: float = 0.95,
    ylim: tuple[float, float] | None = None,
    wrap: int = 12,
    figsize: tuple[float, float] = (8.5, 5),
    ax=None,
):
    """Średnie w grupach wraz z przedziałami ufności.

    Zwraca `(fig, ax)`; zestawienie liczbowe stojące za wykresem dostępne jest
    jako `ax.summary`.
    """
    data = df[[x, y]].dropna()
    summary = data.groupby(x, observed=True)[y].agg(["mean", "count", "std"]).reset_index()

    summary["sem"] = summary["std"] / np.sqrt(summary["count"])
    summary["ci"] = student_t.ppf(1 - (1 - confidence) / 2, summary["count"] - 1) * summary["sem"]

    summary["label"] = (
        summary[x].map(x_labels) if x_labels is not None else summary[x].astype(str)
    )

    fig, ax = _new_axes(ax, figsize)
    ax.errorbar(
        range(len(summary)),
        summary["mean"],
        yerr=summary["ci"],
        fmt="o-",
        linewidth=2,
        capsize=5,
        markersize=7,
        color=CATEGORICAL[0],
    )

    ax.set_xticks(range(len(summary)))
    ax.set_xticklabels(
        [f"{wrap_label(label, wrap)}\n(N={int(n)})" for label, n in zip(summary["label"], summary["count"])]
    )

    ax.set_title(f"{title} ({int(confidence * 100)}% CI)" if title else "")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.grid(axis="y")

    _finish(fig, ax)
    ax.summary = summary
    return fig, ax


__all__ = [
    "CATEGORICAL",
    "LIKERT",
    "SEQUENTIAL",
    "DIVERGING",
    "apply_style",
    "wrap_label",
    "plot_distribution",
    "plot_distribution_by_group",
    "plot_stacked_likert",
    "plot_box",
    "plot_correlation_heatmap",
    "plot_correlation_ranking",
    "plot_transition_heatmap",
    "plot_mean_ci",
]
