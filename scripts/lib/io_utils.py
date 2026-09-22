"""Reading the SPSS files and caching intermediate tables."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from lib import config as C


def find_sav(year: int) -> Path | None:
    """Locate the student file of a cycle in the raw-data folder (case-insensitive)."""
    want = C.SAV[year].lower()
    if C.RAW.exists():
        for p in C.RAW.iterdir():
            if p.name.lower() == want:
                return p
    return None


def read_sav(path, cols, row_filter=("OECD", 1)) -> pd.DataFrame:
    """Selected columns (upper-cased names), user-missing codes as NaN, optionally one row filter."""
    import pyreadstat
    cols = [c.upper() for c in cols]
    load = list(cols)
    if row_filter is not None and row_filter[0].upper() not in load:
        load.append(row_filter[0].upper())
    _, meta = pyreadstat.read_sav(str(path), metadataonly=True)
    actual = {n.upper(): n for n in meta.column_names}
    df, _ = pyreadstat.read_sav(str(path), usecols=[actual[c] for c in load])
    df.columns = [c.upper() for c in df.columns]
    df = df[load]
    if row_filter is not None:
        df = df[df[row_filter[0].upper()] == row_filter[1]].reset_index(drop=True)
    return df[cols]


def sav_columns(path) -> set:
    import pyreadstat
    _, meta = pyreadstat.read_sav(str(path), metadataonly=True)
    return {n.upper() for n in meta.column_names}


def _folder(name: str) -> Path:
    """The per-cycle extracts (stu_<year>) live in data/extract, every other table in data/interim."""
    return C.EXTRACT if name.startswith("stu_") else C.INTERIM


def save_table(df: pd.DataFrame, name: str) -> Path:
    p = _folder(name) / f"{name}.parquet"
    df.to_parquet(p, index=False)
    return p


def load_table(name: str, columns=None) -> pd.DataFrame:
    return pd.read_parquet(_folder(name) / f"{name}.parquet", columns=columns)


def table_exists(name: str) -> bool:
    return (_folder(name) / f"{name}.parquet").exists()


def clean_id(s: pd.Series) -> pd.Series:
    """Student and school identifiers as strings, whatever type the file stores them in."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype("int64").astype(str)
    return s.astype(str).str.strip()


def load_base(columns, all_rows=False) -> pd.DataFrame:
    """The working file. Rows of the analysis sample come first, so their positions also index
    base_weights.npy and the tables of indices; all_rows=True adds the systems in config.EXCLUDE."""
    d = load_table("base", list(dict.fromkeys(list(columns) + ["in_sample"])))
    return d if all_rows else d[d.in_sample == 1].drop(columns="in_sample")
