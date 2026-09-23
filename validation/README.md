# Comparing Python and R

Run from the repository root, using the R environment described in the [R guide](../code/r/README.md):

```bash
Rscript validation/compare.R
```

The command reads the current CSV files in `results/python/tables/` and `results/r/tables/`. It needs `data.table`, `digest` and `jsonlite`; it does not load either analysis engine or require the SPSS files, intermediate data or local audit history. The supplied tables can therefore be compared immediately after cloning and installing these packages.

It compares each Python table with the identically named R table, and additionally with the R `_paper_protocol` variant when available. Keys identify the same country, year, index or item in both tables. Item identifiers are normalized to upper case. Missing or duplicate keys are errors; extra R rows and columns are reported because R includes additional analyses.

## Outputs

All files are written to `results/validation/`:

| File | Content |
|---|---|
| `table_coverage.csv` | Row and numeric-column coverage for each table/protocol pair, including additional R rows and columns |
| `comparison_by_column.csv` | Missing-value mismatches, mean and maximum absolute differences, and the row and values with the largest difference |
| `main_results.csv` | Q4−Q1 changes and standard errors for the original 36-system aggregate, by language and protocol |
| `irt_parameter_comparison.csv` | Differences in slopes and category thresholds, including thresholds stored as JSON arrays |
| `r_only_outputs.csv` | R extensions without a corresponding Python table |
| `input_manifest.csv` | Relative paths and SHA-256 hashes of the tables actually compared |
| `summary.json`, `sessionInfo.txt` | Coverage summary, interpretation, execution time and R environment |

Successful execution means that the Python rows and numeric columns have matching R coverage. **It does not mean numerical equivalence.** The [main README](../README.md#implementation-differences) documents the current methodological and computational differences. In particular, `r_legacy_paper_protocol` is a historical R specification and is not a claim to reproduce current Python defaults. Numerical differences remain visible rather than being judged against a single arbitrary tolerance.

## Individual scores

Once both analyses have generated their intermediate data, also compare student-level scores:

```bash
Rscript validation/compare.R --individual
```

This additionally requires `arrow` and `tidyselect`, reads `data/interim/python/indices_h.parquet` and `data/interim/r/analysis.rds`, and checks that student identifiers and samples match. It writes `person_score_comparison.csv` and a separate `individual_input_manifest.csv` recording the hashes of those two inputs. It does not change either implementation's scores.

The `individual_scores_compared` field in `summary.json` records whether the latest invocation included this optional comparison. Individual output files from an earlier invocation are not refreshed by a tables-only invocation; their input manifest identifies the data used.
