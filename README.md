# The socio-economic gap in PISA 2022–2025 and the index that measures it

Replication material for **Cobreros, Colomer, Correig-Fraga, Gortazar and Sayol (2026), *Explaining the learning decline in PISA 2025 by socioeconomic quartiles through methodological changes*** (Working paper, 22 September 2026).

PISA 2025 Volume I reports that the gap in performance between the top and bottom quarters of ESCS narrowed between 2022 and 2025 because advantaged students declined more, and reads it as a new phenomenon of affluent students who struggle academically. The home-possessions component of ESCS was built from different items in the two cycles, and parental education was collected with new questions. The paper rebuilds the socio-economic index on a rule that is the same in every cycle and recomputes the gaps: the narrowing disappears, and over 2015–2025 the gap has slowly widened.

Everything here runs on the public-use student files of the OECD. No restricted data are involved.

## Main result

Mathematics, change 2022 → 2025 in the Q4 − Q1 gap, simple average of 36 OECD systems (standard errors from 80 BRR replicates and ten plausible values):

| Index | Q1 | Q4 | Q4 − Q1 | s.e. |
|---|---|---|---|---|
| ESCS, published | −2.8 | −14.0 | −11.2 | 1.19 |
| ESCS, harmonised | −7.7 | −6.2 | +1.6 | 1.21 |
| HOMEPOS, published | +7.2 | −27.8 | −35.0 | 1.14 |
| HOMEPOS, harmonised (16 common items) | −6.5 | −10.4 | −4.0 | 1.13 |

The same comparison gives −16.9 against −2.3 in reading and −12.7 against +2.0 in science (`results/tables/quartiles_*.csv`).

## What is in the repository

| Folder | Content |
|---|---|
| `scripts/` | the pipeline, thirteen numbered steps plus `run_all.py`; shared code in `scripts/lib/` |
| `data/extract/` | the rows and columns of the OECD public-use files that the analysis reads, through Git LFS (`data/README.md` has sources, citations and the variable list) |
| `results/tables/` | every table of the paper and the data behind every figure, as CSV |
| `results/figures/` | the figures, as PDF and PNG |
| `reference/` | GDP per capita from the World Bank, used in step 12 |

The tables and figures are committed, so the results can be read without running anything.

## Running it

```bash
git lfs install                          # once; the data extract comes with the clone
git clone https://github.com/Innovamat-Technology/pisa_2025.git && cd pisa_2025
pip install -r requirements.txt
python scripts/run_all.py 2              # about half an hour on a laptop, a few GB of memory
```

There is no need to download anything from the OECD: step 1 (the extraction from the original SPSS files) is only for whoever wants to start from the raw files, and `data/README.md` explains how. `python scripts/run_all.py N` restarts from step N.

| Step | Script | Produces |
|---|---|---|
| 1 | `01_extract.py` | the extract in `data/extract/` from the original `.sav` files (optional) |
| 2 | `02_build_base.py` | working file: systems present in 2022 and 2025, items recoded to one metric |
| 3 | `03_grm_homepos.py` | harmonised HOMEPOS: graded response model on the 16 common items, one calibration |
| 4 | `04_harmonise.py` | harmonised HISEI, PARED, books and the composite (OECD rule; principal component kept as a check) |
| 5 | `05_quartile_changes.py` | change by quartile and decile, gap changes by system (Tables 2, A.3–A.5, B.1, B.2, B.7, C.1, C.2, C.7) |
| 6 | `06_reclassification.py` | students classified differently by the two HOMEPOS (Tables 3 and 4), gap levels by cycle |
| 7 | `07_four_cycle_series.py` | 2015–2025 series on published and four-cycle harmonised indices (Tables A.1, B.3, C.3) |
| 8 | `08_items.py` | item validation, national items, subscales, residual of the published HOMEPOS (Tables 5, A.2, B.6, C.6) |
| 9 | `09_correlations_pared.py` | correlations between components (Tables 6, B.4, C.4), parental-education coverage |
| 10 | `10_composite_weights.py` | ten constructions of the composite (Table D.1) |
| 11 | `11_missing_and_thresholds.py` | fixed-threshold groups and rules (Tables 7, B.5, C.5), students without ESCS |
| 12 | `12_systems.py` | results across systems and their relation to income, achievement and ESCS (Table A.6) |
| 13 | `13_figures.py` | all figures |

Steps 5 and 8 to 12 take the domain as an argument (`math`, `scie`, `read`); `run_all.py` runs the three. `scripts/lib/` holds the paths and item lists (`config.py`), the BRR engine (`brr.py`), the graded response model (`grm.py`) and the OECD composite rule (`escs_rule.py`).

Figures of the paper: Figure 1 is `fig_quartile_profiles_math`, Figure 2 `fig_decile_profile`, Figure 3 `fig_gap_series_math`, Figure 4 `fig_systems_math`; Figures B.1–B.3 and C.1–C.3 are the `_scie` and `_read` versions. `fig_pairwise_differences`, `fig_item_content` and `fig_item_correlations_*` are not in the paper.

## Method in brief

Quartiles hold 25% of the final student weight within each country and cycle, with ties broken at random under a fixed seed, and are recomputed under each of the 80 replicate weights. Standard errors combine BRR sampling variance (Fay factor 0.5) and imputation variance across ten plausible values. OECD figures are simple averages of country estimates, averaged replicate by replicate.

Harmonised HOMEPOS is a single-factor graded response model on the 16 items asked in both cycles, with one set of item parameters for the pooled sample, each country-by-cycle cell weighted equally, and EAP scores. HISEI is only standardised. PARED maps the two values that exist only in 2022 (3 and 14.5 years) to 6 and 14. The composite follows the OECD rule (PISA 2025 Technical Report, chapter 22): a single missing component is imputed by a regression on the other two fitted within each system and cycle, plus a random residual; the three components are standardised with every system-by-cycle cell weighing the same, averaged with equal weights, and the average standardised again. The only difference from the OECD is that the standardisation runs over the pooled cycles, so the metric is not re-anchored in each one. Step 10 shows that nine other constructions, including the first principal component, give the same answer within about one point.

For the 2015–2025 series the possessions model uses the thirteen items whose concept exists in every cycle, recoded to common response categories (`scripts/07_four_cycle_series.py` documents each recode), parental education in 2015 is rebuilt from HISCED with the mapping observed in the 2018 file, and the composite follows the same OECD rule with the four cycles pooled.

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

## Licence

The code is under the MIT License; the paper, tables and figures under CC BY 4.0. Both let you reuse the material for any purpose as long as you credit the authors. The data extract remains the OECD's and is subject to its terms of use. See `LICENSE`.
