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

`scripts/` contains the thirteen numbered stages and `run_all.py`. Reusable functions and configuration live in `scripts/lib/`: BRR calculations in `brr.py`, IRT estimation in `irt.py`, the composite rule in `escs_rule.py`, and paths and item lists in `config.py`.

- Shared inputs: `data/extract/` and `reference/`.
- Working data: `data/interim/python/`, ignored by Git.
- Tables and figures: `results/python/tables/` and `results/python/figures/`.
- Shared fonts: `assets/fonts/`.

New specifications should write distinct output names. The [validation workflow](../../validation/README.md) compares the results of both implementations after they have been generated.

## Recorded versions

The environment recorded on 23 September 2026 used **Python 3.14.7**. [requirements.txt](requirements.txt) pins all 16 installed analysis packages, including transitive dependencies. The main packages were NumPy 2.5.3, pandas 3.0.6, SciPy 1.18.1, matplotlib 3.11.2, pyreadstat 1.3.6 and pyarrow 25.0.1.

[versions.txt](versions.txt) records the interpreter and operating system. The requirements file fixes package versions; it does not fix the operating system or numerical libraries supplied by it.
