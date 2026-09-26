# Wellbeing of students at Wrocław University of Science and Technology

An analysis of a survey on life satisfaction, mental and physical health and lifestyle among students
of Wrocław University of Science and Technology (Politechnika Wrocławska).

**Sample:** 396 respondents, 46 variables, every faculty of the university. The reports and the
notebook are in Polish.

## Main findings

| Area | Strongest result | Holds in the multivariable model |
|---|---|---|
| Relationships | Social support → life satisfaction (ρ = 0.39) | Yes |
| Sleep | Sleep problems → stress (r_rb = 0.43) | Yes |
| Physical activity | Activity → physical health (r_rb = 0.40) | Yes |
| Finances | Rating of one's finances → life satisfaction (ρ = 0.25) | Yes |
| Diet | Rating of one's diet → physical health (ρ = 0.32) | No |
| Work | No significant difference between students who work and those who do not | n/a |

All effects are weak or moderate, and the multivariable models explain 16% to 29% of the variance. The
survey is cross-sectional, so **no relationship here should be read as causal**; the full list of
caveats is in chapter 13 of the report.

## What to read

| Document | For whom | Length |
|---|---|---|
| [`reports/synteza.html`](reports/synteza.html) | a reader with five minutes: a talk or a seminar | 5 A4 pages |
| [`reports/raport.html`](reports/raport.html) | a reader who wants every result | ~98 A4 pages |
| [`notebooks/raport.ipynb`](notebooks/raport.ipynb) | a reader who wants to follow the computation | 15 chapters |

All three describe the same study. The notebook is the source: both HTML documents are built from it
by the scripts in `tools/`, and the summary checks while it is built that its numbers still match the
full report.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

jupyter lab notebooks/raport.ipynb
```

**The raw data set is not in this repository.** The report can be read in full without the source file: `notebooks/raport.ipynb` holds the saved
results of every analysis and 61 charts, and `reports/` holds the finished HTML documents.

## Details

<details>
<summary><strong>Why these methods</strong></summary>

Most outcomes are 5-point ordinal scales, so the tests are nonparametric (Mann-Whitney,
Kruskal-Wallis, Spearman). Each family has about 31 to 33 tests, so p-values are corrected with the
Benjamini-Hochberg false discovery rate. Details and the reasons for each choice:
[`docs/metodologia.md`](docs/metodologia.md) (Polish).

</details>

<details>
<summary><strong>Rebuild the reports</strong></summary>

To reproduce the results to the digit, use `requirements-lock.txt`, which pins the exact versions the
current report was built with.

To re-execute the notebook and rebuild both HTML documents:

```bash
jupyter nbconvert --execute --to notebook --inplace notebooks/raport.ipynb
python tools/build_report.py      # reports/raport.html
python tools/build_summary.py     # reports/synteza.html
```

Order matters: the scripts read the results saved in the notebook, so the notebook runs first.
`build_summary.py` stops if the numbers written into the summary no longer match the report.

</details>

<details>
<summary><strong>Project layout and design</strong></summary>

```
├── data/raw/dane.csv          raw survey export (not in the repository, see "Data")
├── notebooks/raport.ipynb     the report: source of the text and of every result
├── reports/
│   ├── raport.html            full report for reading and printing
│   └── synteza.html           summary for a conference talk
├── tools/
│   ├── build_report.py        notebook → full HTML report
│   └── build_summary.py       findings of chapters 10-14 → summary
├── src/dobrostan/
│   ├── schema.py              the questionnaire: variables, scales, labels
│   ├── prepare.py             data preparation with validation
│   ├── stats.py               statistical tests
│   ├── report.py              formatting results into tables
│   └── plots.py               charts
├── docs/metodologia.md        methodological decisions and their reasons
├── docs/zmiany-w-analizie.md  corrections made after the first version
```

The notebook holds no computation logic. It calls functions from `src/dobrostan` and describes the
results, so each procedure can be checked and changed in one place.

`schema.py` is **the single source of truth about the questionnaire**. It describes each variable
once: the question, its code, its labels and the answer categories with their numeric values. Both
the forward coding (answer → number) and the reverse description (number → chart label) are
generated from it, so they cannot drift apart.

Data preparation ends with a validation step that stops processing when the questionnaire no longer
matches the schema or when a numeric column is still text. Both used to narrow an analysis silently
instead of raising a visible error.

</details>

<details>
<summary><strong>Data</strong></summary>

The survey holds the answers of 396 real students.
It has no direct identifiers (the e-mail field was anonymised at export and the timestamp is dropped
on load), but quasi-identifiers remain: the smallest faculties are represented by one and two people,
which together with age, gender and year of study could identify a respondent.

To reproduce the computation, put the survey file at `data/raw/dane.csv`. The expected format is
described in [`data/README.md`](data/README.md), and the mapping of questions to variables in
`src/dobrostan/schema.py`. Access to the data for scientific verification: contact through the
GitHub profile.

</details>

<details>
<summary><strong>Documentation (Polish)</strong></summary>

- [`docs/metodologia.md`](docs/metodologia.md): choice of tests, scale coding, correction for
  multiple testing, known limits of the measurement
- [`docs/zmiany-w-analizie.md`](docs/zmiany-w-analizie.md): what changed after the first version of
  the report and why, with the effect on the results

</details>

## License

MIT for the code, see [LICENSE](LICENSE). The survey data is not published.
