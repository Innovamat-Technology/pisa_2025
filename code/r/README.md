# PISA analysis in R

This is the R implementation of the study. The [Python implementation](../python/README.md) has its own calculations and outputs. The [main README](../../README.md) describes the research question, the analysis stages and the differences between implementations.

Run commands from the repository root. Install the required packages once:

```bash
Rscript -e 'install.packages(c("data.table", "arrow", "haven", "Rcpp", "readxl", "ggplot2", "jsonlite", "digest", "tidyselect"), repos="https://cloud.r-project.org")'
```

A C++ compiler is required for the Rcpp numerical kernel. Then run:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 Rscript code/r/run_all.R 1 13
```

R reads the shared Parquet extracts and NumPy replicate-weight files natively; it does not execute Python. Stage 1 prepares reference tables, retrieves the officially rescaled older indices and recovers Colombia and Lithuania from the original 2015 SPSS file for the additional OECD-35 series. That SPSS file must be available in `data/raw/`, or in `PISA_RAW_DIR`. The recovered data stay in R's own cache.

The arguments to `run_all.R` are the first and last stage; defaults are 1 and 13. Each stage starts a fresh process to release memory. Steps 2–4 are grouped into stage 2. To resume or run an individual stage:

```bash
Rscript code/r/run_all.R 5 13
Rscript code/r/step.R 9
```

Stage 7 accepts `paper` or `oecd35`; the full workflow runs both. The former follows the original 34-system four-cycle sample. The latter restores the additional 2015 countries, recalibrates the model and incorporates the officially rescaled older components.

## Code and outputs

| Stage | Module | Analysis |
|---|---|---|
| 1 | `R/inputs.R`, `R/analyses.R` | Additional 2015 countries, official trend indices and reference tables |
| 2–4 | `R/irt.R`, `R/core.R` | Base, common-item HOMEPOS, components and ESCS |
| 5–6 | `R/analyses.R` | Quartiles, deciles, reclassifications, transitions and gap levels |
| 7 | `R/irt.R`, `R/analyses.R` | Four-cycle series |
| 8–9 | `R/descriptive.R` | Items, subscales, residuals and correlations |
| 10–12 | `R/robustness.R` | Alternative composites, fixed groups and results across systems |
| 13 | `R/figures.R` | PDF and PNG figures |
| 15, optional | `R/official_2025.R` | Additional specifications using official recodes and fixed 2025 parameters |

`R/kernels.cpp` contains the numerical kernels loaded through Rcpp. Paths and shared numerical functions are in `R/core.R`.

- Shared inputs: `data/extract/` and `reference/`.
- Working data and caches: `data/interim/r/`, ignored by Git.
- Tables and figures: `results/r/tables/` and `results/r/figures/`.
- Execution record: `results/r/run_status.csv` and `results/r/sessionInfo.txt`.
- Internal diagnostics and logs: `audit/tables/` and `audit/logs/r/`, ignored by Git.

The main workflow requires no archived audit reports or Python outputs. The [validation workflow](../../validation/README.md) compares the two implementations independently after their results have been generated.

## Additional specifications

The main README documents the methodological differences and country samples. R also retains these explicit variants:

- `_paper_protocol`: earlier formulas for comparison, including quartile standard errors without the link error. This historical suffix does not identify current Python defaults.
- `_fixed_quartiles`: fixed group assignments as an alternative to recalculating quartiles under each replicate weight.
- `_official_recodes`: official item categories with the authors' pooled calibration, using minimums of three and ten responses.
- `_anchored_2025`: official 2025 country/language parameters fixed across both years for the common items.
- `_trend2022`: older indices officially rescaled for 2022, used in the additional long series.

The optional stage 15 uses the technical annexes in `reference/` and the original 2022 and 2025 SPSS files, as well as the main R intermediate data:

```bash
Rscript code/r/step.R 15
Rscript code/r/step.R 15 summary          # refresh summaries from existing intermediate results
```

It writes the sensitivity estimates to `results/r/tables/` and internal scoring diagnostics to `audit/`. The harmonized indices remain the authors' specifications; neither the official recodes nor fixed parameters establish an official OECD trend scale. Pooled calibration, country/language groups, eligibility and public-use-file suppressions remain relevant to interpretation.

## Recorded versions

The environment recorded on 23 September 2026 used **R 4.6.1** on Fedora Linux 44. [packages.csv](packages.csv) records the installed versions of the nine direct packages and their dependencies; [versions.txt](versions.txt) records the R session and numerical libraries. The principal versions were data.table 1.18.4, arrow 24.0.0, haven 2.5.5, Rcpp 1.1.1-1.1, readxl 1.4.5, ggplot2 4.0.3, jsonlite 2.0.0, digest 0.6.39 and tidyselect 1.2.1.

These files document the observed environment. The installation command above obtains the versions available from CRAN when it is run; it is not a lockfile-based restoration. The recorded Rcpp build is distribution-specific. Historical run versions remain in `results/r/sessionInfo.txt`; a completed `run_all.R` invocation updates that file.
