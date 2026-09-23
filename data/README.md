# Data

## What is in `data/extract/`

A subset of the PISA student questionnaire public-use files, cut down to what the analysis reads. It is stored with Git LFS so that the pipeline runs straight after cloning (`git lfs install` once, then `git clone` or `git lfs pull`).

| File | Content |
|---|---|
| `stu_2025`, `stu_2022` | identifiers, final student weight, the 30 plausible values in mathematics, reading and science, the published socio-economic indices and every home-possessions item |
| `stu_2018`, `stu_2015` | the same, with the possessions items of those cycles (ST011, ST012, ST013); used for the four-cycle series |
| `wts_<year>.npy` | the 80 BRR replicate weights (`W_FSTURWT1`–`W_FSTURWT80`), rows in the same order as `stu_<year>` |

Rows: students of OECD member systems only (`OECD == 1`). Values: as released, with the SPSS user-missing codes (valid skip, not applicable, invalid, no response) set to missing. Variable names are lower-cased; in 2015 and 2018 `PARED` is renamed `pared_published` and `ST013Q01TA` is renamed `books6`. Nothing else is recoded at this stage.

The extract is produced by `code/python/scripts/01_extract.py`. Anyone who prefers to start from the original files can download them (below), place them in `data/raw/` and run the same script; the rest of the pipeline is unchanged.

## Source and attribution

All data are from the OECD Programme for International Student Assessment (PISA) and remain the OECD's. They were downloaded from the PISA database pages (https://www.oecd.org/en/about/programmes/pisa/pisa-data.html) on 18 September 2026.

| Cycle | Original file | Citation |
|---|---|---|
| 2025 | `CY09_MS_STU_PUF.sav` (student questionnaire public-use file) | OECD (2026), *PISA 2025 Database*, OECD, Paris. |
| 2022 | `CY08MSP_STU_QQQ.SAV` | OECD (2023), *PISA 2022 Database*, OECD, Paris. |
| 2018 | `CY07_MSU_STU_QQQ.sav` | OECD (2019), *PISA 2018 Database*, OECD, Paris. |
| 2015 | `CY6_MS_CMB_STU_QQQ.sav` | OECD (2016), *PISA 2015 Database*, OECD, Paris. |

Use of these data is subject to the OECD terms and conditions (https://www.oecd.org/en/about/terms-conditions.html). The authors of this repository have selected rows and columns and changed the file format; the OECD is not responsible for this adaptation or for the analysis built on it.

## Variables kept

Every cycle: `CNT`, `CNTSCHID`, `CNTSTUID`, `W_FSTUWT`, `PV1MATH`–`PV10MATH`, `PV1READ`–`PV10READ`, `PV1SCIE`–`PV10SCIE`, `ESCS`, `HOMEPOS`, `HISEI`.

2022 and 2025 also: `PAREDINT`, `HISCED`, `IMMIG`, and the 16 possessions items asked in both cycles: `ST250Q01JA`, `ST250Q02JA`, `ST250Q03JA`, `ST250Q04JA`, `ST250Q05JA`, `ST251Q01JA`, `ST251Q03JA`, `ST251Q04JA`, `ST251Q06JA`, `ST251Q07JA`, `ST254Q01JA`, `ST254Q02JA`, `ST254Q03JA`, `ST254Q04JA`, `ST254Q05JA`, `ST255Q01JA`.

2022 only: the eight book-type items `ST256Q01JA`, `ST256Q02JA`, `ST256Q03JA`, `ST256Q06JA`, `ST256Q07JA`, `ST256Q08JA`, `ST256Q09JA`, `ST256Q10JA` and `ST253Q01JA`, `ST254Q06JA`, `ST251Q02JA`.

2025 only: the twenty nationally selected items `ST250Q08DA`–`ST250Q16DA` and `ST250Q18DA`–`ST250Q28DA`.

2015 and 2018 only: `HISCED`, `PARED`, `PAREDINT` (2018), `ST011Q01TA`–`ST011Q12TA`, `ST011Q16NA`, `ST012Q01TA`–`ST012Q03TA`, `ST012Q05NA`–`ST012Q09NA`, `ST013Q01TA`.

## Not in the repository

`data/raw/` (the original `.sav` files, about 2 GB each) and `data/interim/python/` and `data/interim/r/` (working data and caches rebuilt by each implementation) are ignored by git.
