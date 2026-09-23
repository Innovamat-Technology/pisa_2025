# Reference files

`gdp_per_capita_ppp_2022.csv`: GDP per capita, PPP (constant 2021 international $), 2022. World Bank, World Development Indicators, indicator NY.GDP.PCAP.PP.KD, retrieved from the World Bank API on 21 September 2026 (series last updated 13 July 2026). License: CC BY 4.0.

## PISA cross-cycle link error

PISA 2025 includes linking uncertainty in standard errors of changes in mean performance, including subgroup means. See [Volume I, Annex A3](https://www.oecd.org/en/publications/pisa-2025-results-volume-i_73451bc5-en/full-report/technical-notes-on-analyses-in-this-volume_46a7001c.html), which refers to [PISA 2022 Volume I, Annex A7](https://www.oecd.org/en/publications/pisa-2022-results-volume-i_53f23881-en/full-report/comparing-mathematics-reading-and-science-performance-across-pisa-assessments_1c417d6f.html) for the treatment of location-invariant statistics. The common additive link cancels in differences between group means within a cycle, and therefore in changes in those gaps.

For 2022–2025, `code/python/scripts/lib/config.py` uses link standard deviations of **1.220** score points for mathematics, **1.094** for reading and **3.116** for science. These reproduce the standard errors in the [official equity tables](https://stat.link/k68msa), Tables I.B1.2b.24, I.B1.2b.23 and I.B1.2b.22 respectively. They were recovered to three decimals using `L² = SE(change)² − SE(2022)² − SE(2025)²` for the four ESCS quartiles of OECD average-35; the five-decimal rounding of the published standard errors accounts for residual discrepancies below 0.00001 points.

The local PISA 2025 Technical Report annex workbook, `15-PISA-2025-Technical Report-AnnexTables_14092026.xlsx`, sheet `T15.A.20`, independently gives **1.22**, **1.09** and **3.12** at two-decimal precision. Its SHA-256 is `ec2eb4a3164093fc4b83b4617f959e55453a14be0707233630c761ec9fa327c6`. The PDF chapter's final table list numbers this linking-error table 15.A.21; the workbook and the reference in the chapter body number it 15.A.20.

`pisa_2025_equity_standard_errors.csv` transcribes the OECD average-35, published-ESCS standard errors from the three equity tables. Each row contains the 2022, 2025 and 2022–2025-change standard errors for a quartile mean or the Q4−Q1 gap. The CSV records the published values used to check inclusion and cancellation of link uncertainty, including its treatment in an international average. Neither analysis requires the other language’s output.

## Shared OECD material

Both implementations use the same source documentation. The R workflow reads the equity workbook to reconstruct link errors and uses the technical annexes for its additional sensitivity analyses.

| File | Source and use |
|---|---|
| `oecd_2025_equity.xlsx` | [Official equity tables](https://stat.link/k68msa), tables I.B1.2b.22–24 and 36–38; estimates, standard errors and link-error reconstruction |
| `technical2025_ch22.pdf`, `technical2025_ch22_tables.xlsx` | PISA 2025 Technical Report, Chapter 22 and annex: calibration, recodes, ESCS constants and the STQ item parameters |
| `technical2025_ch13.pdf`, `technical2025_ch13_tables.xlsx` | Chapter 13 and table 13.A.4: public-use-file suppressions |
| `technical2025_ch25.pdf` | Chapter 25, annex 25.A: corrections after the Volume I analyses |
| `iso_language_codes.csv` | ISO 639-3 to ISO 639-1 mapping from the system `iso-codes` database; country-specific aliases are explicit in `code/r/R/official_2025.R` |

The technical chapters and annex workbooks were supplied locally from the OECD technical-report distribution on 23 September 2026. Their content has not been edited. The [PISA database](https://www.oecd.org/en/data/datasets/pisa-2025-database.html) and [technical report archive](https://www.oecd.org/content/dam/oecd/en/about/programmes/edu/pisa/publications/technical-report/PISA%202025%20Technical%20Report.zip) are the upstream sources. OECD material remains subject to its terms of use.

The R workflow also downloads the [official indices rescaled for 2022](https://webfs.oecd.org/pisa2022/escs_trend.zip) into its ignored cache for the additional four-cycle specification. The main README explains how that specification differs from the original series.
