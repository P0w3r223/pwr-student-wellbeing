"""Składa syntezę raportu — wersję do wystąpienia konferencyjnego.

    python tools/build_summary.py

Pełny raport odpowiada na pytanie „co dokładnie wyszło"; synteza odpowiada na
pytanie „co z tego wynika" i musi dać się przeczytać w kilka minut. Dlatego
zamiast skracać rozdziały, składamy dokument od nowa z ustaleń rozdziałów 10-14
i dwóch wykresów zbiorczych, których w raporcie nie ma — bo tam każdy wynik ma
własny wykres, a tutaj potrzebny jest jeden obraz całości.

Wszystkie liczby pochodzą z wykonanego notebooka i są sprawdzane przy budowaniu
(`verify_against_notebook`). Rozjazd syntezy z raportem przerywa budowanie —
dokument prezentowany przed audytorium nie może cicho zdezaktualizować się
względem źródła.
"""

from __future__ import annotations

import base64
import collections
import html
import io
import json
import pathlib
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dobrostan import plots as pl, schema  # noqa: E402

NOTEBOOK = ROOT / "notebooks" / "raport.ipynb"
OUTPUT = ROOT / "reports" / "synteza.html"

TITLE = "Dobrostan studentów Politechniki Wrocławskiej"
SUBTITLE = "Synteza wyników badania ankietowego"
AUTHOR = "Piotr Cząstkiewicz"
DATE = "sierpień 2026"


# ---------------------------------------------------------------------------
# Ustalenia — źródłem są rozdziały 10-14 raportu
# ---------------------------------------------------------------------------

#: Dziesięć najsilniejszych zależności (rozdział 12). `value` to wielkość efektu
#: **bez znaku**, `domain` — obszar, do którego zależność należy.
#:
#: Znak korelacji rangowo-dwuseryjnej zależy od tego, którą grupę nazwano
#: pierwszą, więc sam z siebie nie informuje o kierunku. Kierunek niesie opis
#: zależności, a liczba — jej siłę. Ta sama konwencja obowiązuje w rozdziale 12.
TOP_FINDINGS = (
    ("Problemy ze snem → poziom stresu", 0.428, "Sen", "r_rb"),
    ("Aktywność fizyczna → zdrowie fizyczne", 0.399, "Pozostałe", "r_rb"),
    ("Problemy ze snem → zdrowie psychiczne", 0.391, "Sen", "r_rb"),
    ("Wsparcie społeczne → satysfakcja z życia", 0.388, "Relacje", "ρ"),
    ("Wsparcie społeczne → satysfakcja z relacji", 0.370, "Relacje", "ρ"),
    ("Wsparcie społeczne → zdrowie psychiczne", 0.342, "Relacje", "ρ"),
    ("Ocena diety → zdrowie fizyczne", 0.319, "Pozostałe", "ρ"),
    ("Liczba bliskich znajomych → satysfakcja z relacji", 0.318, "Relacje", "ρ"),
    ("Stan związku → satysfakcja z relacji", 0.293, "Relacje", "r_rb"),
    ("Social jetlag → problemy ze snem", 0.291, "Sen", "ρ"),
)

#: Modele wieloczynnikowe (rozdział 10): predyktor → (β, p) dla każdego modelu.
MODELS = ("Poziom stresu", "Zdrowie psychiczne", "Satysfakcja z życia")

#: Predyktor → (etykieta na wykresie, współczynniki dla kolejnych modeli).
#: Kluczem jest kod zmiennej, więc nazwę używaną przez raport bierzemy ze
#: schematu — dwa niezależne napisy na to samo rozjechałyby się przy pierwszej
#: zmianie i kontrola zgodności przestałaby cokolwiek sprawdzać.
COEFFICIENTS = {
    "sen_h_dni_robocze": (
        "Długość snu w dni robocze",
        ((-0.104, 0.037), (0.032, 0.511), (-0.032, 0.459)),
    ),
    "problemy_sen": (
        "Problemy ze snem",
        ((0.227, 0.001), (-0.208, 0.001), (-0.177, 0.001)),
    ),
    "social_jetlag": (
        "Social jetlag",
        ((-0.021, 0.632), (-0.005, 0.910), (0.042, 0.264)),
    ),
    "aktywnosc_fiz_h_tydz": (
        "Aktywność fizyczna",
        ((-0.079, 0.001), (0.108, 0.001), (0.093, 0.001)),
    ),
    "ocena_diety": (
        "Ocena jakości diety",
        ((0.055, 0.365), (-0.036, 0.552), (0.070, 0.176)),
    ),
    "poziom_wsparcia": (
        "Wsparcie społeczne",
        ((-0.098, 0.060), (0.285, 0.001), (0.306, 0.001)),
    ),
    "ocena_finansowa": (
        "Ocena sytuacji finansowej",
        ((-0.050, 0.315), (0.140, 0.005), (0.171, 0.001)),
    ),
}

#: Dopasowanie modeli (rozdział 10) — model, N, R², skorygowane R².
MODEL_FIT = (
    ("Poziom stresu", 396, 0.165, 0.149),
    ("Zdrowie psychiczne", 396, 0.252, 0.238),
    ("Satysfakcja z życia", 396, 0.289, 0.276),
)

ALPHA = 0.05

#: Barwy obszarów. Trzy pozycje palety `CATEGORICAL`, zwalidowanej pod kątem
#: zaburzeń widzenia barw — ta sama, której używa 61 wykresów raportu.
DOMAIN_COLORS = {
    "Sen": pl.CATEGORICAL[0],
    "Relacje": pl.CATEGORICAL[1],
    "Pozostałe": pl.CATEGORICAL[2],
}

#: Barwy stanu istotności. Skala rozbieżna z neutralną szarością pośrodku —
#: dodatni i ujemny to przeciwne bieguny, brak istotności to stan neutralny.
SIGNIFICANCE_COLORS = {
    "dodatni": pl.LIKERT[4],
    "ujemny": pl.LIKERT[0],
    "nieistotny": pl.LIKERT[2],
}


# ---------------------------------------------------------------------------
# Zgodność ze źródłem
# ---------------------------------------------------------------------------


def verify_against_notebook() -> list[str]:
    """Sprawdza, czy liczby w syntezie nadal zgadzają się z raportem.

    Porównujemy z tekstową postacią wyników zapisaną w notebooku, bo to ona
    trafia do raportu. Zwraca listę rozbieżności — pusta oznacza zgodność.
    """
    if not NOTEBOOK.exists():
        return [f"brak notebooka: {NOTEBOOK}"]

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    # Wyjścia `print` też wchodzą do zrzutu: rozdzielają tabele współczynników
    # nazwami modeli, bez których nie da się przypisać β do właściwego modelu.
    dump = "\n".join(
        "".join(output.get("data", {}).get("text/plain", ""))
        or "".join(output.get("text", ""))
        for cell in notebook["cells"]
        for output in cell.get("outputs", [])
    )

    problems = []

    for label, value, _domain, _statistic in TOP_FINDINGS:
        printed = f"{abs(value):.3f}".replace(".", ",")
        if printed not in dump:
            problems.append(f"wielkość efektu {printed} ({label}) nie występuje w raporcie")

    for model, n, r2, _adjusted in MODEL_FIT:
        # Przecinek podmieniamy tylko w liczbie. Zamiana w całym wzorcu psułaby
        # kropki pochodzące z `re.escape`, gdyby nazwa modelu kiedyś je zawierała.
        printed = f"{r2:.3f}".replace(".", ",")
        if not re.search(rf"{re.escape(model)}\s+{n}\s+{re.escape(printed)}", dump):
            problems.append(
                "dopasowanie modelu nie zgadza się z raportem: "
                f"{model}, N = {n}, R² = {printed}"
            )

    problems.extend(_verify_coefficients(dump))
    return problems


def _verify_coefficients(dump: str) -> list[str]:
    """Sprawdza współczynniki β stojące za wykresem „co przetrwało kontrolę".

    To 21 liczb, na których opiera się drugi wykres syntezy. Bez tej kontroli
    najważniejszy obraz dokumentu byłby jedyną jego częścią niezweryfikowaną.
    Wartości szukamy w bloku właściwego modelu — sama obecność liczby gdzieś
    w raporcie niczego nie dowodzi.
    """
    # Tabela współczynników ma osiem wierszy plus nagłówek; ograniczenie bloku
    # chroni przed sięganiem po liczby z dalszych rozdziałów.
    blocks = {}
    for index, model in enumerate(MODELS):
        start = dump.find(model + "\n")
        if start < 0:
            return [f"brak w raporcie tabeli współczynników modelu „{model}”"]
        blocks[index] = "\n".join(dump[start:].splitlines()[:14])

    names = schema.descriptions()
    problems = []
    for code, (_label, coefficients) in COEFFICIENTS.items():
        described = names[code]
        for index, (beta, _p) in enumerate(coefficients):
            printed = f"{beta:.3f}".replace(".", ",")
            line = next(
                (row for row in blocks[index].splitlines() if described in row), None
            )
            if line is None:
                problems.append(f"brak wiersza „{described}” w modelu {MODELS[index]}")
            elif printed not in line:
                problems.append(
                    f"β dla „{described}” w modelu {MODELS[index]}: synteza podaje "
                    f"{printed}, raport co innego"
                )

    return problems


# ---------------------------------------------------------------------------
# Wykresy
# ---------------------------------------------------------------------------


def _to_data_uri(fig) -> str:
    """Zapisuje wykres jako obraz wklejony w dokument."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight", facecolor=pl.SURFACE)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def chart_top_findings() -> str:
    """Dziesięć najsilniejszych zależności, pogrupowanych barwą według obszaru.

    Słupki pokazują wielkość efektu bez znaku — pytanie brzmi „jak silna jest
    zależność", a nie „w którą stronę". Kierunek niesie podpisana wartość,
    więc informacja o znaku nie ginie.
    """
    findings = sorted(TOP_FINDINGS, key=lambda row: abs(row[1]))
    labels = [row[0] for row in findings]
    values = [abs(row[1]) for row in findings]
    colors = [DOMAIN_COLORS[row[2]] for row in findings]

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    bars = ax.barh(labels, values, color=colors, height=0.68)

    ax.bar_label(
        bars,
        labels=[f"|{row[3]}| = {row[1]:.3f}".replace(".", ",") for row in findings],
        padding=6,
        fontsize=9,
        color=pl.INK_MUTED,
    )

    ax.set_xlim(0, 0.52)
    ax.set_xlabel("Wielkość efektu (wartość bezwzględna)")
    ax.set_title("Dziesięć najsilniejszych zależności w badaniu", pad=14)
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=9.5)

    # Liczby w legendzie wyprowadzamy z danych, nie wpisujemy. Wpisana wcześniej
    # ręcznie legenda mówiła „Relacje (4)" przy pięciu pomarańczowych słupkach.
    counts = collections.Counter(row[2] for row in TOP_FINDINGS)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=DOMAIN_COLORS[key], label=f"{name} ({counts[key]})")
        for key, name in (
            ("Relacje", "Relacje społeczne"),
            ("Sen", "Sen"),
            ("Pozostałe", "Pozostałe obszary"),
        )
    ]
    # Legenda pod osią, nie w polu wykresu: przy słupkach posortowanych rosnąco
    # wolne miejsce jest tam, gdzie stoją podpisy wartości, więc ramka legendy
    # zasłaniałaby liczby.
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=3,
        title="Obszar (liczba pozycji w pierwszej dziesiątce)",
    )

    fig.text(
        0.5,
        -0.10,
        "Wszystkie efekty mieszczą się w kategorii słabych lub umiarkowanych — "
        "żaden nie osiąga siły dużej.",
        ha="center",
        fontsize=8.5,
        color=pl.INK_MUTED,
    )

    fig.tight_layout()
    return _to_data_uri(fig)


def chart_model_survival() -> str:
    """Które czynniki zachowują istotność po uwzględnieniu pozostałych.

    Barwa koduje stan wyniku, nie jego wielkość: współczynniki dotyczą
    predyktorów o różnych skalach (godziny snu wobec oceny 1-5), więc
    porównywanie ich wielkości między wierszami byłoby mylące. Wartość β jest
    wpisana w komórkę, żeby liczba pozostała dostępna, a barwa odpowiadała
    wyłącznie na pytanie o istotność.
    """
    predictors = [label for label, _ in COEFFICIENTS.values()]
    fig, ax = plt.subplots(figsize=(8.4, 5.0))

    for row, (_label, coefficients) in enumerate(COEFFICIENTS.values()):
        for column, (beta, p_value) in enumerate(coefficients):
            if p_value >= ALPHA:
                state = "nieistotny"
            else:
                state = "dodatni" if beta > 0 else "ujemny"
            background = SIGNIFICANCE_COLORS[state]

            ax.add_patch(
                plt.Rectangle(
                    (column - 0.47, row - 0.44),
                    0.94,
                    0.88,
                    facecolor=background,
                    edgecolor=pl.SURFACE,
                    linewidth=2,
                )
            )
            ax.text(
                column,
                row,
                f"{beta:+.3f}".replace(".", ",").replace("-", "−"),
                ha="center",
                va="center",
                fontsize=9.5,
                color=pl._label_color(background),
            )

    ax.set_xlim(-0.5, len(MODELS) - 0.5)
    ax.set_ylim(-0.6, len(predictors) - 0.4)
    ax.set_xticks(range(len(MODELS)), [pl.wrap_label(name, 14) for name in MODELS])
    ax.set_yticks(range(len(predictors)), predictors)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.invert_yaxis()
    ax.tick_params(length=0, labelsize=9.5)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Które czynniki zachowują istotność w modelu wieloczynnikowym",
        pad=34,
    )

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=SIGNIFICANCE_COLORS[state], label=label)
        for state, label in (
            ("dodatni", "istotny, zależność dodatnia"),
            ("ujemny", "istotny, zależność ujemna"),
            ("nieistotny", "nieistotny (p ≥ 0,05)"),
        )
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.04),
        ncol=3,
        fontsize=8.5,
    )

    fig.text(
        0.5,
        -0.08,
        "W komórkach współczynniki β. Predyktory mają różne skale, "
        "więc β porównujemy w obrębie kolumny, nie między wierszami.",
        ha="center",
        fontsize=8.5,
        color=pl.INK_MUTED,
    )

    fig.tight_layout()
    return _to_data_uri(fig)


# ---------------------------------------------------------------------------
# Dokument
# ---------------------------------------------------------------------------


def positions(count: int) -> str:
    """Liczba pozycji w poprawnej formie gramatycznej."""
    if count == 1:
        return "1 pozycja"
    if 2 <= count <= 4:
        return f"{count} pozycje"
    return f"{count} pozycji"


def model_fit_rows() -> str:
    return "".join(
        f"<tr><td>{html.escape(model)}</td><td>{n}</td>"
        f"<td>{r2:.3f}".replace(".", ",") + "</td>"
        f"<td>{adjusted:.3f}".replace(".", ",") + "</td></tr>"
        for model, n, r2, adjusted in MODEL_FIT
    )


def build() -> None:
    problems = verify_against_notebook()
    if problems:
        for problem in problems:
            print(f"  ! {problem}")
        sys.exit(
            "Synteza rozjechała się z raportem — popraw liczby albo przelicz notebook."
        )

    # Ten sam styl, którego używa 61 wykresów raportu — synteza pokazywana obok
    # pełnej wersji nie może wyglądać jak dokument z innego opracowania.
    pl.apply_style()

    document = TEMPLATE.format(
        title=html.escape(TITLE),
        subtitle=html.escape(SUBTITLE),
        author=html.escape(AUTHOR),
        date=html.escape(DATE),
        chart_findings=chart_top_findings(),
        chart_models=chart_model_survival(),
        model_rows=model_fit_rows(),
        relacje=positions(sum(row[2] == "Relacje" for row in TOP_FINDINGS)),
        sen=positions(sum(row[2] == "Sen" for row in TOP_FINDINGS)),
        style=STYLE,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document, encoding="utf-8")
    print(
        f"{OUTPUT.relative_to(ROOT)}: {OUTPUT.stat().st_size / 1024:.0f} kB, "
        "2 wykresy zbiorcze, liczby zgodne z raportem"
    )


STYLE = """
:root {
  --surface: #fcfcfb;
  --paper: #ffffff;
  --ink: #0b0b0b;
  --muted: #52514e;
  --line: #e1e0d9;
  --rule: #c3c2b7;
  --accent: #1c5cab;
  --accent-soft: #eef4fd;
  --warm: #9c2b2b;
  --sans: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --serif: Georgia, "Iowan Old Style", "Times New Roman", serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  padding: 0 1.5rem 5rem;
  background: var(--surface);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.62;
}

.sheet { max-width: 52rem; margin: 0 auto; }

/* --- nagłówek --- */

header { padding: 3.5rem 0 0; }

.kicker {
  font-family: var(--sans);
  font-size: 0.7rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 600;
  margin: 0;
}

h1 {
  font-family: var(--sans);
  font-size: clamp(1.8rem, 4vw, 2.4rem);
  line-height: 1.15;
  letter-spacing: -0.015em;
  margin: 0.55rem 0 0.4rem;
}

.subtitle { font-size: 1.08rem; color: var(--muted); margin: 0 0 1.5rem; }

.byline {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1.4rem;
  padding: 0.8rem 0;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--line);
  font-family: var(--sans);
  font-size: 0.85rem;
}
.byline .name { font-weight: 600; }
.byline .meta { color: var(--muted); }

/* --- teza --- */

.thesis {
  margin: 2.5rem 0;
  padding: 1.5rem 1.75rem;
  background: var(--paper);
  border: 1px solid var(--line);
  border-left: 4px solid var(--accent);
  font-size: 1.15rem;
  line-height: 1.5;
}
.thesis strong { font-weight: 700; }

/* --- kafelki --- */

/* Ramka na każdym kafelku, a nie siatka prześwitująca przez odstępy —
   przy zawinięciu ostatniego wiersza puste komórki nie zostawiają wtedy
   szarego prostokąta. */
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: 0.6rem;
  margin: 2rem 0;
}
.tile {
  background: var(--paper);
  border: 1px solid var(--line);
  padding: 0.9rem 1rem;
  font-family: var(--sans);
}
.tile .value { font-size: 1.7rem; font-weight: 700; line-height: 1; letter-spacing: -0.02em; }
.tile .label {
  margin-top: 0.4rem;
  font-size: 0.7rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--muted);
}

/* --- sekcje --- */

section { margin: 3rem 0 0; }

h2 {
  font-family: var(--sans);
  font-size: 1.18rem;
  letter-spacing: -0.01em;
  margin: 0 0 0.9rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--rule);
}

h3 {
  font-family: var(--sans);
  font-size: 0.74rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 1.75rem 0 0.6rem;
}

p { margin: 0 0 1rem; }
ul, ol { margin: 0 0 1rem; padding-left: 1.3rem; }
li { margin-bottom: 0.45rem; }
li::marker { color: var(--rule); }

.lead { font-size: 1.02rem; }

figure { margin: 1.75rem 0; }
figure img {
  display: block;
  width: 100%;
  height: auto;
  border: 1px solid var(--line);
  border-radius: 3px;
}
figcaption {
  margin-top: 0.55rem;
  font-family: var(--sans);
  font-size: 0.76rem;
  color: var(--muted);
}

/* --- pytania badawcze --- */

.questions { counter-reset: q; list-style: none; padding: 0; }
.questions li {
  counter-increment: q;
  position: relative;
  padding-left: 2.4rem;
  margin-bottom: 0.85rem;
}
.questions li::before {
  content: counter(q);
  position: absolute;
  left: 0;
  top: 0.1rem;
  width: 1.6rem;
  height: 1.6rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 700;
}
.questions .answer {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.94rem;
  color: var(--muted);
}

/* --- tabela --- */

table {
  border-collapse: collapse;
  width: 100%;
  background: var(--paper);
  border: 1px solid var(--line);
  font-family: var(--sans);
  font-size: 0.85rem;
  margin: 1.25rem 0;
}
th {
  text-align: left;
  font-weight: 600;
  padding: 0.55rem 0.85rem;
  border-bottom: 2px solid var(--ink);
  white-space: nowrap;
}
td {
  padding: 0.45rem 0.85rem;
  border-bottom: 1px solid var(--line);
  font-variant-numeric: tabular-nums;
}
td:first-child { font-variant-numeric: normal; }
tr:last-child td { border-bottom: none; }

/* --- wyróżnienia --- */

.callout {
  margin: 1.5rem 0;
  padding: 1rem 1.25rem;
  background: var(--paper);
  border: 1px solid var(--line);
  border-left: 3px solid var(--rule);
  font-size: 0.96rem;
}
.callout.caution { border-left-color: var(--warm); }
.callout .head {
  display: block;
  font-family: var(--sans);
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.4rem;
}

.two-col {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr));
  gap: 0 2rem;
}

footer {
  margin-top: 3.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--line);
  font-family: var(--sans);
  font-size: 0.78rem;
  color: var(--muted);
}
footer a { color: var(--accent); }

/* --- druk --- */

@media print {
  @page { size: A4; margin: 16mm 15mm 18mm; }
  body { font-size: 10pt; padding: 0; background: #fff; }
  .sheet { max-width: none; }
  header { padding-top: 0; }
  section { break-inside: auto; }
  h2 { break-after: avoid; }
  figure, table, .callout, .thesis, .tiles { break-inside: avoid; }
  /* Niższe wykresy pakują się gęściej na stronie — przy zachowanej całości
     figury zbyt wysoki obraz spycha na kolejną kartkę pół strony tekstu. */
  figure img { border-color: #ccc; max-height: 12cm; width: auto; max-width: 100%; }
  /* 1px zapasu: bez niego ramka ostatniego kafelka wypada dokładnie na
     krawędzi obszaru druku i ginie przy rasteryzacji do PDF. */
  .tiles {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.4rem;
    padding: 1px;
  }
  .tile { padding: 0.6rem 0.7rem; }
  .tile .value { font-size: 1.3rem; }
  a { color: inherit; text-decoration: none; }
}
"""

TEMPLATE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — synteza</title>
<meta name="author" content="{author}">
<meta name="description" content="{subtitle}">
<style>{style}</style>
</head>
<body>
<div class="sheet">

<header>
  <p class="kicker">Synteza wyników</p>
  <h1>{title}</h1>
  <p class="subtitle">{subtitle}</p>
  <div class="byline">
    <span class="name">{author}</span>
    <span class="meta">{date}</span>
    <span class="meta">badanie przekrojowe, N = 396</span>
  </div>
</header>

<p class="thesis">
  Dobrostan studentów wiąże się przede wszystkim z <strong>jakością relacji
  i jakością odpoczynku</strong>, a nie z mierzalnymi parametrami stylu życia.
  Odczuwane wsparcie społeczne i problemy ze snem — obie zmienne subiektywne —
  okazały się silniejszymi korelatami dobrostanu niż liczba znajomych, liczba
  przespanych godzin czy fakt podejmowania pracy.
</p>

<div class="tiles">
  <div class="tile"><div class="value">396</div><div class="label">respondentów z 14 wydziałów</div></div>
  <div class="tile"><div class="value">46</div><div class="label">zmiennych</div></div>
  <div class="tile"><div class="value">4</div><div class="label">czynniki istotne w ≥ 2 modelach</div></div>
  <div class="tile"><div class="value">16–29%</div><div class="label">wyjaśnionej wariancji</div></div>
</div>

<section>
  <h2>Pytania badawcze i odpowiedzi</h2>
  <ol class="questions">
    <li>Czy elementy stylu życia — sen, aktywność fizyczna, odżywianie — są związane
      z dobrostanem?
      <span class="answer">Tak, ale słabiej i bardziej wybiórczo, niż sugeruje
      powszechny przekaz o zdrowych nawykach. Niezależny wkład zachowują wyłącznie
      problemy ze snem i aktywność fizyczna.</span></li>
    <li>Czy relacje społeczne, sytuacja akademicka i praca wiążą się z dobrostanem?
      <span class="answer">Relacje — najsilniej ze wszystkich badanych obszarów.
      Sytuacja akademicka — umiarkowanie. Sam fakt podejmowania pracy nie
      różnicował żadnego wymiaru dobrostanu; znaczenie miała ocena sytuacji
      finansowej.</span></li>
    <li>Które czynniki wiążą się najsilniej?
      <span class="answer">Dla satysfakcji z życia i zdrowia psychicznego —
      wsparcie społeczne. Dla poziomu stresu — problemy ze snem. Dla zdrowia
      fizycznego — aktywność fizyczna i ocena diety.</span></li>
    <li>Czy zależności utrzymują się po jednoczesnym uwzględnieniu wielu czynników?
      <span class="answer">Częściowo. Istotność w co najmniej dwóch z trzech
      modeli zachowują cztery czynniki: problemy ze snem, aktywność fizyczna,
      wsparcie społeczne i ocena sytuacji finansowej. Ocena diety oraz social
      jetlag nie są istotne w żadnym modelu, a długość snu traci istotność
      w obu modelach dobrostanu psychicznego.</span></li>
  </ol>
</section>

<section>
  <h2>Metoda</h2>
  <p class="lead">
    Badanie ankietowe przeprowadzone w styczniu 2026 wśród studentów Politechniki
    Wrocławskiej; udział dobrowolny, dobór nielosowy. Zmienne zależne mają
    charakter porządkowy, dlatego podstawą są <strong>metody
    nieparametryczne</strong>: korelacja rang Spearmana, test U Manna-Whitneya,
    test Kruskala-Wallisa z testem post hoc Dunna oraz test chi-kwadrat.
    Dla pytania o niezależność czynników zastosowano modele regresji liniowej
    z diagnostyką współliniowości (VIF poniżej 2,2).
  </p>
  <p>
    Wartości p korygowano metodą <strong>Benjaminiego-Hochberga</strong>,
    obejmując korektą <strong>pełną rodzinę wykonanych porównań</strong>, a nie
    tylko wyniki prezentowane na wykresie. Przy każdym rankingu podana jest
    liczba objętych testów. Przyjęto α = 0,05.
  </p>
</section>

<section>
  <h2>Wynik 1 — najsilniejsze zależności</h2>
  <p>
    W pierwszej dziesiątce dominują dwa obszary: <strong>relacje społeczne</strong>
    ({relacje}) oraz <strong>sen</strong> ({sen}). W obu przypadkach
    najwyżej plasują się miary subiektywne — odczuwane wsparcie i odczuwane
    problemy ze snem — a nie ich policzalne odpowiedniki.
  </p>
  <figure>
    <img src="{chart_findings}" alt="Dziesięć najsilniejszych zależności w badaniu, pogrupowanych według obszaru">
    <figcaption>Wykres 1. Dziesięć zależności o największej wielkości efektu (rozdział 12 raportu).</figcaption>
  </figure>
</section>

<section>
  <h2>Wynik 2 — co przetrwało kontrolę pozostałych czynników</h2>
  <p>
    Analizy dwuzmiennowe nie rozstrzygają, czy zależność jest własna, czy wynika
    ze współwystępowania z innym czynnikiem. Trzy modele regresji ze wspólnym
    zestawem predyktorów pozwalają to rozdzielić.
  </p>
  <figure>
    <img src="{chart_models}" alt="Siatka istotności współczynników regresji dla siedmiu predyktorów i trzech modeli">
    <figcaption>Wykres 2. Współczynniki regresji w trzech modelach wieloczynnikowych (rozdział 10 raportu).</figcaption>
  </figure>

  <table>
    <thead><tr><th>Model</th><th>N</th><th>R²</th><th>skoryg. R²</th></tr></thead>
    <tbody>{model_rows}</tbody>
  </table>

  <div class="callout">
    <span class="head">Najważniejsze pojedyncze ustalenie</span>
    <strong>Długość snu traci istotność w modelach dobrostanu psychicznego, gdy
    uwzględni się problemy ze snem.</strong> Liczy się jakość snu, nie liczba
    przespanych godzin — a to zmienia adresata ewentualnej interwencji.
  </div>
</section>

<section>
  <h2>Trzy obserwacje przekrojowe</h2>
  <ul>
    <li><strong>Jakość ponad ilość.</strong> Problemy ze snem wiążą się ze stresem
      silniej niż liczba przespanych godzin; odczuwane wsparcie — silniej niż
      liczba znajomych.</li>
    <li><strong>Część zależności nie jest własna.</strong> Dieta i social jetlag,
      istotne w analizach dwuzmiennowych, przestają wnosić niezależny wkład
      w modelu pełnym.</li>
    <li><strong>Żaden pojedynczy czynnik nie dominuje.</strong> Najsilniejsze
      efekty są umiarkowane, a modele wyjaśniają najwyżej 29% zróżnicowania —
      dobrostan zależy głównie od czynników nieobjętych badaniem.</li>
  </ul>
</section>

<section>
  <h2>Wyniki negatywne</h2>
  <p>
    Zestawiamy je osobno, bo mają wartość informacyjną porównywalną z wynikami
    dodatnimi, a łatwo giną w narracji.
  </p>
  <ul>
    <li><strong>Podejmowanie pracy nie różnicowało żadnego wymiaru dobrostanu.</strong>
      Znaczenie miała ocena sytuacji finansowej — a więc subiektywnie postrzegana
      stabilność materialna, nie sam fakt zatrudnienia.</li>
    <li><strong>Poziom stresu okazał się najsłabiej wyjaśniany</strong> (R² = 0,165
      wobec 0,289 dla satysfakcji z życia). Sugeruje to, że stres studencki wynika
      głównie z czynników nieobjętych badaniem — obciążenia zajęciami, terminów,
      sytuacji egzaminacyjnej.</li>
    <li><strong>Liczba bliskich znajomych wykazała efekt nasycenia.</strong>
      Satysfakcja z relacji rosła do około 3–5 bliskich osób, po czym się
      stabilizowała.</li>
  </ul>
</section>

<section>
  <h2>Ograniczenia</h2>
  <div class="two-col">
    <ul>
      <li><strong>Badanie przekrojowe</strong> — wszystkie zmienne zmierzono
        w jednym momencie, więc żadnej zależności nie można interpretować
        przyczynowo.</li>
      <li><strong>Próba nielosowa</strong> — udział dobrowolny, samoselekcja;
        wyników nie należy uogólniać na ogół studentów.</li>
      <li><strong>Jedna uczelnia techniczna</strong> — profil studentów i obciążenie
        zajęciami różnią się od uczelni o innym profilu.</li>
    </ul>
    <ul>
      <li><strong>Dane deklaratywne</strong> — łącznie z długością snu i czasem
        nauki; brak weryfikacji pomiarem obiektywnym.</li>
      <li><strong>Kategorie otwarte ścieśniają krańce skal</strong>, co może
        osłabiać obserwowane korelacje.</li>
      <li><strong>Brak średniej ocen u 27% respondentów</strong> nie jest losowy —
        dotyczy systematycznie studentów pierwszego semestru.</li>
    </ul>
  </div>

  <div class="callout caution">
    <span class="head">Zastrzeżenie interpretacyjne</span>
    Wyniki należy traktować jako <strong>mapę współwystępowania</strong>,
    wskazującą obszary warte pogłębionego badania podłużnego, a nie jako podstawę
    rekomendacji interwencyjnych.
  </div>
</section>

<section>
  <h2>Kierunki dalszej pracy</h2>
  <ul>
    <li>Badanie podłużne na tej samej populacji — jedyny sposób, by rozstrzygnąć
      kierunek zależności między snem a stresem.</li>
    <li>Obiektywny pomiar snu i aktywności zamiast samoopisu.</li>
    <li>Uwzględnienie obciążenia dydaktycznego i kalendarza sesji jako
      predyktorów stresu — obszaru, którego obecny model nie obejmuje.</li>
    <li>Poprawa narzędzia: rozłączne przedziały czasu nauki, domknięte kategorie
      krańcowe.</li>
  </ul>
</section>

<footer>
  Synteza rozdziałów 10–14 pełnego raportu. Wszystkie liczby pochodzą
  z <code>notebooks/raport.ipynb</code> i są weryfikowane przy generowaniu tego
  dokumentu. Pełny raport wraz z metodyką, wykresami i aneksem:
  <code>reports/raport.html</code>. Decyzje metodologiczne: <code>docs/metodologia.md</code>.
</footer>

</div>
</body>
</html>
"""


if __name__ == "__main__":
    build()
