# The socio-economic gap in PISA 2022–2025 and the index that measures it

Analysis code and results for **Cobreros, Colomer, Correig-Fraga, Gortazar and Sayol (2026), *Explaining the learning decline in PISA 2025 by socioeconomic quartiles through methodological changes*** (Working paper - Revised, 23 September 2026).

The analysis is implemented in parallel in **Python and R**, so researchers can choose the language they prefer to explore the data, adapt the methods and build on the study. Both implementations read the OECD public-use data and construct the harmonized indices in their own language. The [Python workflow](code/python/README.md) and [R workflow](code/r/README.md) have separate outputs; the computational differences and the current differences in statistical specifications are described below.

PISA 2025 Volume I reports that the gap in performance between the top and bottom quarters of ESCS narrowed between 2022 and 2025 because advantaged students declined more, and reads it as a new phenomenon of affluent students who struggle academically. The home-possessions component of ESCS was built from different items in the two cycles, and parental education was collected with new questions. The paper rebuilds the socio-economic index on a rule that is the same in every cycle and recomputes the gaps: the narrowing disappears, and over 2015–2025 the gap has slowly widened.

Everything here runs on the public-use student files of the OECD. No restricted data are involved.

## Main result

Mathematics, change 2022 → 2025 in the Q4 − Q1 gap, simple average of 36 OECD systems (standard errors from 80 BRR replicates and ten plausible values):

| Index | Q1 | Q4 | Q4 − Q1 | s.e. |
|---|---|---|---|---|
| ESCS, published | −2.8 | −14.0 | −11.2 | 1.19 |
| ESCS, harmonized | −7.7 | −6.1 | +1.6 | 1.20 |
| HOMEPOS, published | +7.2 | −27.8 | −35.0 | 1.14 |
| HOMEPOS, harmonized (16 common items) | −6.5 | −10.7 | −4.2 | 1.14 |

The same comparison gives −16.9 against −2.2 in reading and −12.7 against +2.0 in science (`results/python/tables/quartiles_*.csv`). These are the Python estimates. The corresponding R estimates are in `results/r/tables/quartiles_*.csv`; a comparison on the same 36 systems is given below.

## What is in the repository

| Folder | Content |
|---|---|
| `code/python/` | Python entry point, numbered scripts, reusable functions and recorded dependency versions |
| `code/r/` | R entry points, modules, numerical kernel and recorded dependency versions |
| `data/extract/` | Shared OECD extracts and replicate weights, stored with Git LFS; see [data/README.md](data/README.md) |
| `data/interim/python/`, `data/interim/r/` | Separate working data and caches, rebuilt locally and ignored by Git |
| `results/python/`, `results/r/` | Each implementation's tables and figures |
| `validation/` | Comparison of the current Python and R outputs |
| `results/validation/` | Comparison results and input hashes |
| `reference/` | OECD reference documents, parameter tables and World Bank GDP data |
| `assets/fonts/` | Fonts used in the figures |

Tables and figures are supplied so the results can be read without running either workflow. Internal audit reports, diagnostics and historical snapshots live in the Git-ignored `audit/` directory.

## Running it

```bash
git lfs install                          # once; the data extract comes with the clone
git clone https://github.com/Innovamat-Technology/pisa_2025.git && cd pisa_2025
```

Run either workflow from the repository root:

| | Python | R |
|---|---|---|
| Setup and versions | [Python guide](code/python/README.md) | [R guide](code/r/README.md) |
| Main analysis | `python code/python/scripts/run_all.py 2` | `Rscript code/r/run_all.R 1 13` |
| Outputs | `results/python/` | `results/r/` |

Python can start from the supplied extracts; its optional step 1 regenerates them from the original SPSS files. R also reads the shared extracts directly. Its full workflow prepares the additional 2015 countries for the OECD-35 series and therefore requires the original 2015 SPSS file in `data/raw/` or `PISA_RAW_DIR`. Each implementation constructs the indices and performs the analyses in its own language.

The Python guide records Python 3.14.7 and pins the installed packages in `requirements.txt`; the R guide records R 4.6.1 and the installed package versions in `packages.csv`. These are the local environments recorded on 23 September 2026. Each guide explains how to install dependencies and resume an analysis. Run the two full calibrations separately on machines with limited memory.

| Stage | Python, under `code/python/scripts/` | R, under `code/r/` | Produces |
|---|---|---|---|
| 1 | `01_extract.py` | `R/inputs.R`, `R/analyses.R` | Python: optional extraction; R: reference tables, additional 2015 countries and trend indices |
| 2–4 | `02_build_base.py`, `03_irt_homepos.py`, `04_harmonise.py` | Stage 2: `R/irt.R`, `R/core.R` | Base, common-item HOMEPOS, harmonized components and ESCS |
| 5 | `05_quartile_changes.py` | `R/analyses.R` | Quartiles, deciles and gap changes (Tables 2, A.3–A.5, B.1, B.2, B.7, C.1, C.2, C.7) |
| 6 | `06_reclassification.py` | `R/analyses.R` | Reclassifications, transitions and gap levels (Tables 3 and 4) |
| 7 | `07_four_cycle_series.py` | `R/irt.R`, `R/analyses.R` | Four-cycle series (Tables A.1, B.3, C.3); R also produces the OECD-35 variant |
| 8–9 | `08_items.py`, `09_correlations_pared.py` | `R/descriptive.R` | Item validation, subscales, residuals and correlations (Tables 5, 6, A.2, B.4, B.6, C.4, C.6) |
| 10–12 | `10_composite_weights.py`, `11_missing_and_thresholds.py`, `12_systems.py` | `R/robustness.R` | Alternative composites, fixed groups and comparisons across systems (Tables 7, A.6, B.5, C.5, D.1) |
| 13 | `13_figures.py` | `R/figures.R` | Figures in PDF and PNG |

Compare the outputs independently of the analysis workflows:

```bash
Rscript validation/compare.R
```

This reads the current CSV files, records their hashes and writes coverage and numerical differences to `results/validation/`. It does not refit models. The [validation guide](validation/README.md) explains the optional comparison of individual scores and how to interpret methodological differences.

Figures of the paper: Figure 1 is `fig_quartile_profiles_math`, Figure 2 `fig_decile_profile`, Figure 3 `fig_gap_series_math`, Figure 4 `fig_systems_math`; Figures B.1–B.3 and C.1–C.3 are the `_scie` and `_read` versions. `fig_pairwise_differences`, `fig_item_content` and `fig_item_correlations_*` are not in the paper.

## Working in Python or R

To extend the Python analysis, start with the numbered scripts and reusable functions in `code/python/scripts/lib/`. For R, start with `code/r/step.R` and the modules in `code/r/R/`. Keep the input files fixed and write new specifications to separate tables so they can be compared with the supplied results.

## Implementation differences

Small numerical differences can arise when the same statistical specification is implemented in the two environments:

- **Random imputation.** R and NumPy use different random-number routines. The same integer seed does not produce the same residual draws when imputing a missing ESCS component, so some students receive slightly different scores and quartile assignments.
- **Ties at quartile boundaries.** The scripts split tied index values using random tie-breaking. Different draws can assign students with identical values to different groups, particularly for discrete measures such as parental education or books at home.
- **Numerical optimization.** Floating-point operations, numerical libraries and convergence tolerances can produce small differences in IRT estimates and WLE scores. For the matched 16-item HOMEPOS specification, the individual-score RMSE between the implementations is about `7.4e-6` and the maximum absolute difference is `1.6e-4` index units. The deterministic HISEI, PARED and books components agree to machine precision.

For the same 36 systems, the change in the Q4−Q1 performance gap using harmonized ESCS is:

| Domain | Python, score points | R, score points | R − Python |
|---|---:|---:|---:|
| Mathematics | +1.587 | +1.761 | +0.174 |
| Reading | −2.171 | −2.004 | +0.166 |
| Science | +1.964 | +2.081 | +0.116 |

These aggregate differences are small and mainly reflect the random imputation draws. Differences can be larger for individual students, individual countries or groups with many tied values. A fixed seed supports reproducibility within an implementation; matching draws across languages requires explicitly sharing the draws or using the same generator and call sequence.

**The current default specifications also differ in some respects.** These are methodological differences, not consequences of the programming language:

| Aspect | Python defaults | R defaults |
|---|---|---|
| Variance of the international mean | Averages national replicate estimates before calculating variance | Sums national covariance matrices and divides by the square of the number of systems |
| Correlations with performance | Correlates with the student's mean across ten plausible values | Calculates each plausible-value correlation separately and averages the correlations |
| Partial correlations | Pearson correlation of residuals multiplied by the square root of the weight | Weighted correlation of residuals in the original metric |
| Computers in the four-cycle series | Some unknown/zero response combinations are treated as zero | These combinations remain missing |

Both implementations include the OECD link error in changes of group means. R tables with the suffix `_paper_protocol` retain earlier specifications, including quartile standard errors conditional on excluding the link error. This suffix is historical and does not identify current Python defaults. The validation command reports comparisons with current R defaults and, where available, the historical R variant separately.

Country samples and sensitivity analyses also need to be matched:

- `OECD` is the original 36-system sample in the 2022–2025 comparison. Use this row and the same index for the main comparison between languages.
- `OECD35` in R follows the official aggregate, excluding Costa Rica, Luxembourg and Spain. Results report `n_systems` where applicable.
- The original four-cycle series uses 34 systems. The R `_oecd35` series restores Colombia and Lithuania in 2015, recalibrates the model and additionally uses the officially rescaled older components. Its changes cannot be attributed only to country counts.
- R labels the older indices rescaled for 2022 as `_trend2022`. The `_official_recodes` and `_anchored_2025` tables are additional sensitivities, described in the [R guide](code/r/README.md#additional-specifications).

The [current comparison files](results/validation/) retain discrepancies by table, column and protocol, including the largest-difference row and the values in both languages. Coverage means matching rows and columns; it does not assert identical estimates or specifications.

## Method in brief

Quartiles hold 25% of the final student weight within each country and cycle, with ties broken at random under a fixed seed, and are recomputed under each of the 80 replicate weights. Standard errors combine BRR sampling variance (Fay factor 0.5) and imputation variance across ten plausible values. International point estimates give each country equal weight; the current implementations use the variance aggregation choices described above.

For changes in individual group means between 2022 and 2025, standard errors also include the OECD cross-cycle link error: `sqrt(SE_2022² + SE_2025² + L²)`, with `L = 1.220` in mathematics, `1.094` in reading and `3.116` in science (score points). This applies to quartiles, deciles and fixed-threshold groups, including international averages; the common link variance is added once and is not divided by the number of systems. The additive link cancels in within-cycle differences between groups and in changes in those gaps, whose standard errors therefore combine only sampling and plausible-value imputation variance. Confidence intervals use 1.96 standard errors. [Reference sources](reference/README.md) document the constants and the published-value reconstruction.

harmonized HOMEPOS uses the same model family as the OECD questionnaire indices (two-parameter logistic for dichotomous items, generalized partial credit for polytomous ones) on the 16 items asked in both cycles, with one set of item parameters for the pooled sample, each country-by-cycle cell weighted equally, and weighted likelihood estimates as scores. HISEI is only standardized. PARED maps the two values that exist only in 2022 (3 and 14.5 years) to 6 and 14. The composite applies an equal-weighted component rule: a single missing component is imputed by a regression on the other two fitted within each system and cycle, plus a random residual; the three components are standardized with every system-by-cycle cell weighing the same, averaged with equal weights, and the average standardized again. This pooled harmonization differs from the OECD calibration in its population, country/language groups, item recodes, parameters and scoring eligibility. The [reference files](reference/README.md) include the relevant OECD technical chapters and parameter tables. R provides sensitivities using official recodes and fixed official parameters; these remain the authors’ analyses, rather than an official OECD trend scale. Step 10 compares nine other constructions, including the first principal component.

For the 2015–2025 series the possessions model uses the thirteen items whose concept exists in every cycle, recoded to common response categories (`code/python/scripts/07_four_cycle_series.py` documents each recode), parental education in 2015 is rebuilt from HISCED with the mapping observed in the 2018 file, and the composite follows the same OECD rule with the four cycles pooled.

Costa Rica is left out of the analysis sample because its files carry no ESCS, HISEI or PARED; its possessions items still enter the calibration of the possessions model. Luxembourg took part only in 2025.

## How to cite

Cobreros, L., Colomer, M., Correig-Fraga, E., Gortazar, L. and Sayol, I. (2026). *Explaining the learning decline in PISA 2025 by socioeconomic quartiles through methodological changes*. Working paper, EsadeEcPol, World Bank and Innovamat Research Lab, 22 September 2026.

```bibtex
@unpublished{cobreros2026pisa,
  author = {Cobreros, Lucia and Colomer, Marc and Correig-Fraga, Eudald and Gortazar, Lucas and Sayol, Isaac},
  title  = {Explaining the learning decline in {PISA} 2025 by socioeconomic quartiles through methodological changes},
  year   = {2026},
  month  = sep,
  note   = {Working paper, EsadeEcPol, World Bank and Innovamat Research Lab},
  url    = {https://github.com/Innovamat-Technology/pisa_2025}
}
```

## License

The code is under the MIT License; the paper, tables and figures under CC BY 4.0. Both let you reuse the material for any purpose as long as you credit the authors. The data extract remains the OECD's and is subject to its terms of use. See `LICENSE`.
