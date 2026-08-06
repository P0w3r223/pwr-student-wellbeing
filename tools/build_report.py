"""Składa raport HTML z wykonanego notebooka.

    python tools/build_report.py

Notebook jest źródłem treści, ten skrypt — jej oprawą. Rozdzielenie tych ról
pozwala poprawiać wygląd raportu bez przeliczania analiz i odwrotnie.

W stosunku do `jupyter nbconvert --to html` dochodzą tu rzeczy, których raport
przeznaczony dla czytelnika wymaga, a eksport domyślny nie daje: strona
tytułowa, spis treści z zaznaczaniem bieżącego rozdziału, numeracja wykresów
i tabel, kod ukryty za przełącznikiem oraz arkusz stylów do druku na A4.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

import mistune

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "raport.ipynb"
OUTPUT = ROOT / "reports" / "raport.html"

TITLE = "Dobrostan studentów Politechniki Wrocławskiej"
SUBTITLE = "Analiza badania ankietowego dotyczącego satysfakcji z życia, zdrowia i stylu życia"
AUTHOR = "Piotr Cząstkiewicz"
DATE = "sierpień 2026"

#: Liczby ze strony tytułowej, które muszą zgadzać się z wykonanym notebookiem.
#: Notebook wypisuje przy wczytaniu „Wczytano N respondentów i M zmiennych".
RESPONDENTS = 396
COLUMNS = 46

#: Pola strony tytułowej — kolejność jest kolejnością wyświetlania.
FACTS = (
    ("Próba", f"{RESPONDENTS} respondentów"),
    ("Zmienne", str(COLUMNS)),
    ("Zbieranie danych", "styczeń 2026"),
    ("Dobór próby", "nielosowy, samoselekcja"),
    ("Metody", "nieparametryczne, korekta Benjaminiego-Hochberga"),
    ("Kod źródłowy", "src/dobrostan"),
)

ABSTRACT = (
    "Raport przedstawia zależności między dobrostanem studentów a ich stylem życia, "
    "sytuacją akademicką, społeczną i materialną. Wszystkie analizy oparto na metodach "
    "nieparametrycznych, a wartości p skorygowano na wielokrotne testowanie w obrębie "
    "pełnych rodzin wykonanych porównań. Badanie ma charakter przekrojowy i eksploracyjny, "
    "dlatego <strong>żadnej z opisanych zależności nie należy interpretować "
    "przyczynowo</strong> — pełną listę zastrzeżeń zawiera rozdział 13."
)


# ---------------------------------------------------------------------------
# Przekształcenia wyjścia notebooka
# ---------------------------------------------------------------------------


def strip_dataframe_index(table: str) -> str:
    """Usuwa kolumnę z numerem wiersza z tabeli wygenerowanej przez pandas.

    Numer porządkowy jest artefaktem struktury danych, a nie treścią wyniku —
    w raporcie zabiera miejsce pierwszej kolumnie i sugeruje, że coś znaczy.

    Usuwamy go wyłącznie wtedy, gdy indeks jest **bezimienny**. Sama numeracja
    nie wystarcza jako przesłanka: kolumna „Miejsce" w rankingu dziesięciu
    najważniejszych ustaleń też zawiera liczby 1-10, a jest treścią tabeli.
    Pandas wypisuje nazwę indeksu w drugim wierszu nagłówka i to ona rozstrzyga.
    """
    header = re.search(r"<thead>(.*?)</thead>", table, re.S)
    body = re.search(r"<tbody>(.*?)</tbody>", table, re.S)
    if header is None or body is None:
        return table

    # Drugi wiersz nagłówka pojawia się tylko dla indeksu z nazwą.
    if len(re.findall(r"<tr[^>]*>", header.group(1))) > 1:
        return table

    rows = re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S)
    if not rows or not all(re.match(r"\s*<th>\d+</th>", row) for row in rows):
        return table

    table = re.sub(r"(<tr[^>]*>)\s*<th></th>", r"\1", table, count=1)
    return re.sub(r"(<tr>)\s*<th>\d+</th>", r"\1", table)


def clean_table(table: str) -> str:
    """Zdejmuje z tabeli oprawę wstrzykniętą przez pandas.

    Własny arkusz stylów opisuje tabele w całości; pozostawienie stylów pandas
    dawałoby dwa źródła prawdy o wyglądzie, które rozjeżdżają się przy pierwszej
    zmianie.
    """
    # Pandas wypuszcza `<style scoped>`, a Styler `<style type="text/css">` —
    # zdejmujemy każdy wariant.
    table = re.sub(r"<style[^>]*>.*?</style>", "", table, flags=re.S)
    table = table.replace(' border="1"', "")
    table = re.sub(r'\s*style="text-align: right;"', "", table)
    return strip_dataframe_index(table).strip()


def slugify(text: str) -> str:
    """Zamienia nagłówek na identyfikator kotwicy."""
    translated = text.translate(
        str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    )
    return re.sub(r"[^a-z0-9]+", "-", translated.lower()).strip("-") or "sekcja"


def heading_title(text: str) -> str:
    """Zwraca nagłówek bez numeru rozdziału — numer nadaje już kontekst."""
    return re.sub(r"^\d+(\.\d+)*\.?\s*", "", text).strip()


# ---------------------------------------------------------------------------
# Składanie dokumentu
# ---------------------------------------------------------------------------


class Builder:
    """Przechodzi komórki notebooka i buduje z nich treść raportu."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.toc: list[tuple[int, str, str]] = []
        self.section = TITLE
        self.figures = 0
        self.tables = 0
        self.markdown = mistune.create_markdown(
            escape=False, plugins=["table", "strikethrough"]
        )

    # -- markdown ----------------------------------------------------------

    def add_markdown(self, source: str) -> None:
        rendered = self.markdown(source)
        rendered = re.sub(
            r"<h([123])>(.*?)</h\1>",
            self._anchor_heading,
            rendered,
            flags=re.S,
        )
        self.parts.append(rendered)

    def _anchor_heading(self, match: re.Match[str]) -> str:
        level = int(match.group(1))
        text = match.group(2)
        plain = re.sub(r"<[^>]+>", "", text).strip()
        anchor = slugify(plain)
        self.section = heading_title(plain)
        if level <= 2:
            self.toc.append((level, anchor, plain))
        # Kotwica jest osobnym elementem przed nagłówkiem, żeby pasek u góry
        # strony nie zasłaniał tytułu rozdziału po kliknięciu w spis treści.
        return (
            f'<span class="anchor" id="{anchor}"></span>'
            f'<h{level}>{text}<a class="permalink" href="#{anchor}"'
            f' aria-label="Odnośnik do sekcji">#</a></h{level}>'
        )

    # -- kod i wyniki ------------------------------------------------------

    def add_code(self, source: str, outputs: list[dict]) -> None:
        if source.strip():
            self.parts.append(
                '<details class="code"><summary>Kod</summary>'
                f'<pre><code>{html.escape(source.rstrip())}</code></pre></details>'
            )
        for output in outputs:
            self._add_output(output)

    def _add_output(self, output: dict) -> None:
        # Komórka, która rzuciła wyjątek, nie może zniknąć z raportu bez śladu —
        # brakujący wynik wygląda wtedy tak samo jak wynik, którego nie było.
        if output["output_type"] == "error":
            raise SystemExit(
                f"Notebook zawiera błąd wykonania w sekcji „{self.section}”: "
                f"{output.get('ename')}: {output.get('evalue')}.\n"
                "Przelicz notebook przed złożeniem raportu."
            )

        if output["output_type"] == "stream":
            text = "".join(output.get("text", "")).strip()
            if text:
                self.parts.append(f'<p class="note">{html.escape(text)}</p>')
            return

        data = output.get("data", {})
        if "image/png" in data:
            self._add_figure(data["image/png"])
        elif "text/html" in data:
            self._add_table("".join(data["text/html"]))
        elif "text/plain" in data:
            text = "".join(data["text/plain"]).strip()
            if text:
                self.parts.append(f"<pre class='plain'>{html.escape(text)}</pre>")

    def _add_figure(self, payload: str | list[str]) -> None:
        self.figures += 1
        source = payload if isinstance(payload, str) else "".join(payload)
        caption = f"Wykres {self.figures}. {self.section}"
        # Bez `loading="lazy"` — obrazy są wklejone w dokument, więc odroczenie
        # nic nie oszczędza, a przy drukowaniu grozi pustymi ramkami.
        self.parts.append(
            '<figure>'
            f'<img src="data:image/png;base64,{source.strip()}"'
            f' alt="{html.escape(caption)}">'
            f'<figcaption>{html.escape(caption)}</figcaption>'
            "</figure>"
        )

    def _add_table(self, table: str) -> None:
        self.tables += 1
        caption = f"Tabela {self.tables}. {self.section}"
        self.parts.append(
            '<figure class="table">'
            f'<div class="table-scroll">{clean_table(table)}</div>'
            f'<figcaption>{html.escape(caption)}</figcaption>'
            "</figure>"
        )

    # -- gotowe fragmenty --------------------------------------------------

    def toc_html(self) -> str:
        items = "".join(
            f'<li class="lvl{level}"><a href="#{anchor}">{html.escape(text)}</a></li>'
            for level, anchor, text in self.toc
        )
        return f"<ol class='toc-list'>{items}</ol>"

    def body_html(self) -> str:
        return "\n".join(self.parts)


def verify_title_facts(notebook: dict) -> None:
    """Sprawdza, czy liczebność próby na stronie tytułowej zgadza się z danymi.

    Strona tytułowa jest pierwszą rzeczą, którą czyta odbiorca, i jedyną częścią
    raportu niepochodzącą z obliczeń — bez tej kontroli mogłaby cicho
    zdezaktualizować się po zmianie zbioru.
    """
    stated = f"Wczytano {RESPONDENTS} respondentów i {COLUMNS} zmiennych."
    printed = "\n".join(
        "".join(output.get("text", ""))
        for cell in notebook["cells"]
        for output in cell.get("outputs", [])
        if output["output_type"] == "stream"
    )
    if stated not in printed:
        sys.exit(
            f"Strona tytułowa deklaruje „{stated}”, a notebook tego nie potwierdza.\n"
            "Popraw RESPONDENTS/COLUMNS albo przelicz notebook."
        )


def build() -> None:
    if not NOTEBOOK.exists():
        sys.exit(f"Brak notebooka: {NOTEBOOK}")

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    verify_title_facts(notebook)
    builder = Builder()

    for cell in notebook["cells"]:
        source = "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            builder.add_markdown(source)
        elif cell["cell_type"] == "code":
            builder.add_code(source, cell.get("outputs", []))

    facts = "".join(
        f"<div><dt>{html.escape(name)}</dt><dd>{html.escape(value)}</dd></div>"
        for name, value in FACTS
    )

    document = TEMPLATE.format(
        title=html.escape(TITLE),
        subtitle=html.escape(SUBTITLE),
        author=html.escape(AUTHOR),
        date=html.escape(DATE),
        abstract=ABSTRACT,
        facts=facts,
        toc=builder.toc_html(),
        body=builder.body_html(),
        style=STYLE,
        script=SCRIPT,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document, encoding="utf-8")

    size = OUTPUT.stat().st_size / 1024 / 1024
    print(
        f"{OUTPUT.relative_to(ROOT)}: {size:.1f} MB, "
        f"{builder.figures} wykresów, {builder.tables} tabel, "
        f"{len(builder.toc)} pozycji spisu treści"
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
  --sans: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --serif: Georgia, "Iowan Old Style", "Times New Roman", serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--surface);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.65;
  -webkit-text-size-adjust: 100%;
}

/* --- pasek u góry --- */

.appbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.55rem 1.25rem;
  background: rgba(252, 252, 251, 0.94);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  font-family: var(--sans);
  font-size: 0.82rem;
}

.appbar strong { font-weight: 600; letter-spacing: 0.01em; }
.appbar .spacer { flex: 1; }

.appbar button {
  font: inherit;
  color: var(--muted);
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 999px;
  padding: 0.25rem 0.85rem;
  cursor: pointer;
}

.appbar button:hover { color: var(--ink); border-color: var(--ink); }
.appbar button[aria-pressed="true"] {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

/* --- układ strony --- */

.layout {
  display: grid;
  grid-template-columns: 17.5rem minmax(0, 1fr);
  align-items: start;
}

.toc {
  position: sticky;
  top: 3rem;
  max-height: calc(100vh - 3rem);
  overflow-y: auto;
  padding: 2rem 1rem 3rem 1.5rem;
  font-family: var(--sans);
  font-size: 0.8rem;
  border-right: 1px solid var(--line);
}

.toc h2 {
  margin: 0 0 0.75rem;
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}

.toc-list { list-style: none; margin: 0; padding: 0; }
.toc-list a {
  display: block;
  padding: 0.2rem 0.5rem;
  color: var(--muted);
  text-decoration: none;
  border-left: 2px solid transparent;
  border-radius: 0 3px 3px 0;
  line-height: 1.35;
}
.toc-list a:hover { color: var(--ink); background: var(--accent-soft); }
.toc-list .lvl2 a { padding-left: 1.25rem; font-size: 0.95em; }
.toc-list a.current {
  color: var(--accent);
  border-left-color: var(--accent);
  background: var(--accent-soft);
  font-weight: 600;
}

/* --- strona tytułowa --- */

.titlepage {
  max-width: 44rem;
  margin: 0 auto;
  padding: 4.5rem 1.5rem 3rem;
}

.titlepage .kicker {
  font-family: var(--sans);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 600;
}

.titlepage h1 {
  font-family: var(--sans);
  font-size: clamp(1.9rem, 4.4vw, 2.7rem);
  line-height: 1.15;
  letter-spacing: -0.015em;
  margin: 0.6rem 0 0.75rem;
}

.titlepage .subtitle {
  font-size: 1.12rem;
  color: var(--muted);
  margin: 0 0 2rem;
  max-width: 34rem;
}

.byline {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  padding: 0.9rem 0;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--line);
  font-family: var(--sans);
  font-size: 0.88rem;
}
.byline .author { font-weight: 600; }
.byline .date { color: var(--muted); }

.abstract {
  margin: 2rem 0;
  padding-left: 1.1rem;
  border-left: 3px solid var(--rule);
  color: var(--muted);
  font-size: 0.98rem;
}
.abstract strong { color: var(--ink); }

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 1px;
  margin: 2.5rem 0 0;
  background: var(--line);
  border: 1px solid var(--line);
  font-family: var(--sans);
}
.facts > div { background: var(--surface); padding: 0.8rem 1rem; }
.facts dt {
  font-size: 0.66rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
}
.facts dd { margin: 0.2rem 0 0; font-size: 0.92rem; font-weight: 600; }

/* --- treść --- */

article {
  display: grid;
  grid-template-columns:
    [full-start] minmax(1rem, 1fr)
    [wide-start] minmax(0, 5rem)
    [text-start] min(44rem, calc(100% - 2rem))
    [text-end] minmax(0, 5rem)
    [wide-end] minmax(1rem, 1fr)
    [full-end];
  padding-bottom: 5rem;
}

article > * { grid-column: text; }
article > figure { grid-column: wide; }

article h1, article h2, article h3 {
  font-family: var(--sans);
  line-height: 1.25;
  letter-spacing: -0.01em;
  scroll-margin-top: 4rem;
}

article h1 {
  font-size: 1.75rem;
  margin: 4rem 0 1.25rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--ink);
}
article h2 { font-size: 1.22rem; margin: 2.75rem 0 0.85rem; }
article h3 {
  font-size: 0.82rem;
  margin: 2rem 0 0.7rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

article p { margin: 0 0 1.05rem; }
article ul, article ol { margin: 0 0 1.05rem; padding-left: 1.4rem; }
article li { margin-bottom: 0.35rem; }
article hr { display: none; }

.anchor { display: block; height: 0; scroll-margin-top: 4.5rem; }

.permalink {
  margin-left: 0.4rem;
  color: var(--line);
  text-decoration: none;
  font-weight: 400;
  opacity: 0;
  transition: opacity 0.15s;
}
h1:hover .permalink, h2:hover .permalink, h3:hover .permalink { opacity: 1; }
.permalink:hover { color: var(--accent); }

a { color: var(--accent); }

/* --- wykresy i tabele --- */

figure {
  margin: 2rem 0;
  padding: 0;
}

figure img {
  display: block;
  width: 100%;
  height: auto;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--surface);
}

figcaption {
  margin-top: 0.6rem;
  font-family: var(--sans);
  font-size: 0.76rem;
  color: var(--muted);
  letter-spacing: 0.01em;
}

.table-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 3px; }

table {
  border-collapse: collapse;
  width: 100%;
  background: var(--paper);
  font-family: var(--sans);
  font-size: 0.83rem;
}

thead th {
  position: sticky;
  top: 0;
  background: var(--paper);
  text-align: left;
  font-weight: 600;
  padding: 0.55rem 0.85rem;
  border-bottom: 2px solid var(--ink);
  white-space: nowrap;
}

tbody td, tbody th {
  padding: 0.45rem 0.85rem;
  border-bottom: 1px solid var(--line);
  text-align: left;
  font-weight: 400;
  vertical-align: top;
}

tbody tr:last-child td, tbody tr:last-child th { border-bottom: none; }
tbody tr:hover { background: var(--accent-soft); }

/* Kolumny liczbowe wyrównujemy do prawej — cyfry porównuje się kolumnami. */
tbody td:not(:first-child) { font-variant-numeric: tabular-nums; }

/* --- kod i komunikaty --- */

details.code {
  margin: 1.25rem 0;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--paper);
  font-family: var(--sans);
}

body.hide-code details.code { display: none; }

details.code summary {
  cursor: pointer;
  padding: 0.4rem 0.8rem;
  font-size: 0.74rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  user-select: none;
}

details.code pre {
  margin: 0;
  padding: 0.9rem 1rem;
  border-top: 1px solid var(--line);
  overflow-x: auto;
  font-size: 0.79rem;
  line-height: 1.5;
  font-family: "Cascadia Mono", Consolas, "SF Mono", monospace;
}

.note {
  margin: 1rem 0;
  padding: 0.5rem 0.9rem;
  border-left: 3px solid var(--rule);
  background: var(--paper);
  font-family: var(--sans);
  font-size: 0.8rem;
  color: var(--muted);
  white-space: pre-wrap;
}

pre.plain {
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 0.79rem;
  overflow-x: auto;
  color: var(--muted);
}

.colophon {
  grid-column: text;
  margin-top: 4rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--line);
  font-family: var(--sans);
  font-size: 0.78rem;
  color: var(--muted);
}

/* --- ekrany wąskie --- */

@media (max-width: 62rem) {
  .layout { grid-template-columns: 1fr; }
  .toc {
    position: static;
    max-height: none;
    border-right: none;
    border-bottom: 1px solid var(--line);
    padding: 1.25rem 1.5rem;
  }
  body.toc-collapsed .toc { display: none; }
}

/* --- druk --- */

@media print {
  @page { size: A4; margin: 18mm 16mm 20mm; }

  body { font-size: 10.5pt; background: #fff; }
  .appbar, .toc, .permalink { display: none !important; }
  .layout { display: block; }
  article {
    display: block;
    max-width: none;
    padding: 0;
  }
  .titlepage { max-width: none; padding: 0 0 1rem; break-after: page; }
  details.code { display: none !important; }

  article h1 { break-before: page; font-size: 15pt; }
  article h1:first-of-type { break-before: avoid; }
  article h2, article h3 { break-after: avoid; }
  figure, table, .note { break-inside: avoid; }
  figure img { border-color: #ccc; }
  thead th { position: static; }
  a { color: inherit; text-decoration: none; }
}
"""

SCRIPT = """
(function () {
  var body = document.body;
  body.classList.add('hide-code');

  var codeToggle = document.getElementById('toggle-code');
  codeToggle.addEventListener('click', function () {
    var hidden = body.classList.toggle('hide-code');
    codeToggle.setAttribute('aria-pressed', String(!hidden));
    codeToggle.textContent = hidden ? 'Pokaż kod' : 'Ukryj kod';
  });

  document.getElementById('print').addEventListener('click', function () {
    window.print();
  });

  // Podświetlenie bieżącej sekcji w spisie treści. Obserwujemy kotwice, a nie
  // same nagłówki, bo nagłówek chowa się pod paskiem u góry strony.
  var links = {};
  document.querySelectorAll('.toc-list a').forEach(function (link) {
    links[link.getAttribute('href').slice(1)] = link;
  });

  var visible = new Set();
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) { visible.add(entry.target.id); }
      else { visible.delete(entry.target.id); }
    });

    var order = Object.keys(links);
    var current = order.filter(function (id) { return visible.has(id); })[0];
    if (!current) { return; }

    Object.keys(links).forEach(function (id) {
      links[id].classList.toggle('current', id === current);
    });
    var active = links[current];
    if (active && active.offsetParent) {
      var nav = document.querySelector('.toc');
      var top = active.offsetTop - nav.clientHeight / 2;
      if (Math.abs(nav.scrollTop - top) > nav.clientHeight / 3) {
        nav.scrollTo({ top: top, behavior: 'smooth' });
      }
    }
  }, { rootMargin: '-15% 0px -70% 0px' });

  Object.keys(links).forEach(function (id) {
    var anchor = document.getElementById(id);
    if (anchor) { observer.observe(anchor); }
  });
})();
"""

TEMPLATE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="author" content="{author}">
<meta name="description" content="{subtitle}">
<style>{style}</style>
</head>
<body>

<div class="appbar">
  <strong>{title}</strong>
  <span class="spacer"></span>
  <button id="toggle-code" aria-pressed="false">Pokaż kod</button>
  <button id="print">Drukuj / PDF</button>
</div>

<div class="layout">
  <nav class="toc" aria-label="Spis treści">
    <h2>Spis treści</h2>
    {toc}
  </nav>

  <main>
    <header class="titlepage">
      <p class="kicker">Raport z badania</p>
      <h1>{title}</h1>
      <p class="subtitle">{subtitle}</p>
      <div class="byline">
        <span class="author">{author}</span>
        <span class="date">{date}</span>
      </div>
      <div class="abstract">{abstract}</div>
      <dl class="facts">{facts}</dl>
    </header>

    <article>
      {body}
      <div class="colophon">
        Raport wygenerowano z notebooka <code>notebooks/raport.ipynb</code>
        skryptem <code>tools/build_report.py</code>. Kod analiz znajduje się
        w pakiecie <code>src/dobrostan</code>, decyzje metodologiczne —
        w <code>docs/metodologia.md</code>.
      </div>
    </article>
  </main>
</div>

<script>{script}</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
