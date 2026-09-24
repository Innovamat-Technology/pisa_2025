# PISA analysis in Python

This is the Python implementation of the study. The [R implementation](../r/README.md) has its own calculations and outputs. The [main README](../../README.md) describes the research question, the analysis stages and the differences between implementations.

Run commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r code/python/requirements.txt
python code/python/scripts/run_all.py 2
```

The supplied extracts in `data/extract/` are sufficient for the main analysis. To regenerate them from the original SPSS files, place those files in `data/raw/`, or set `PISA_RAW_DIR`, and start at step 1. See the [data guide](../../data/README.md).

`run_all.py N` starts at step N and continues through step 13. Individual scripts can also be run directly; steps 5 and 8–12 accept `math`, `read` or `scie` as an argument:

```bash
python code/python/scripts/09_correlations_pared.py math
```

## Code and outputs

`scripts/` contains the thirteen main stages, the optional Latin American extension and `run_all.py`. Reusable functions and configuration live in `scripts/lib/`: BRR calculations in `brr.py`, IRT estimation in `irt.py`, the composite rule in `escs_rule.py`, and paths and item lists in `config.py`.

- Shared inputs: `data/extract/` and `reference/`.
- Working data: `data/interim/python/`, ignored by Git.
- Tables and figures: `results/python/tables/` and `results/python/figures/`.
- Shared fonts: `assets/fonts/`.

New specifications should write distinct output names. The [validation workflow](../../validation/README.md) compares the results of both implementations after they have been generated.

## Seven-country Latin American extension

```bash
python code/python/scripts/14_latam_quartiles.py --countries ARG BRA CHL COL MEX PER URY
```

This optional, standalone script repeats the 2022–2025 mathematics quartile analysis. It reads both original SPSS files, including non-OECD countries, from `data/raw/` or `PISA_RAW_DIR`; the supplied OECD extracts alone are insufficient. It reuses the Python IRT, imputation and BRR functions, recalibrating the harmonized indices on the selected countries and both years. The international mean uses independent national covariance matrices, as in the main R specification. The original OECD results are used to validate published-index estimates for overlapping countries.

The [report](../../results/python/latam/README.md), Excel workbook, CSV tables and PDF/PNG figures are written to `results/python/latam/`. Intermediate data and full-precision model parameters go to `data/interim/python/latam/`. `--refresh` rebuilds extraction and calibration; `--output PATH` selects another output directory. Input SHA-256 fingerprints prevent reuse of extracts from different source files. The script checks weight alignment, quartile weight shares, BRR/PV variances, existing results and official OECD equity tables.

To extend the selected seven countries to 2015–2025 and generate language versions:

```bash
python code/python/scripts/15_latam_history.py
python code/python/scripts/16_latam_reports.py
```

Step 15 needs the four original SPSS files and the seven-country step-14 output for validation. It estimates the **Q4−Q1 mathematics gap in each cycle**, for published ESCS/HOMEPOS and indices harmonized jointly across the four cycles. It does not calculate between-cycle changes. Argentina starts in 2018 because its 2015 national sample is not comparable. The pooled 13-item IRT model gives each available country-year equal weight and requires eight observed items for WLE scoring. The computer recode follows the corrected R specification: none plus unknown remains missing. The historical reconstruction is distinct from the 16-item, two-cycle model in step 14. Gaps retain the covariance between quartiles in BRR/PV variance estimates. Raw quartile score levels are also retained as supporting tables.

Step 16 renders Catalan, Spanish and English reports, workbooks and PNG/PDF figures for both the 2022–2025 analysis and the historical series. All language versions read the same CSV tables; estimates are not recomputed during rendering. Use `--current-only` to render just the 2022–2025 reports. Catalan outputs are in each analysis folder; Spanish and English outputs are in its `es/` and `en/` subfolders. The [output index](../../results/python/latam/index.md) links all versions. Historical results are in `results/python/latam/history/`, and the working data and full-precision calibration are in `data/interim/python/latam/history/`. These optional scripts are not part of `run_all.py`.

## Recorded versions

The environment recorded on 23 September 2026 used **Python 3.14.7**. [requirements.txt](requirements.txt) pins the installed analysis packages, including transitive dependencies. The main packages were NumPy 2.5.3, pandas 3.0.6, SciPy 1.18.1, matplotlib 3.11.2, pyreadstat 1.3.6 and pyarrow 25.0.1. The Latin American extension additionally uses openpyxl 3.1.5 (and et_xmlfile 2.0.0) to read the official reference workbook and write its Excel results.

[versions.txt](versions.txt) records the interpreter and operating system. The requirements file fixes package versions; it does not fix the operating system or numerical libraries supplied by it.
