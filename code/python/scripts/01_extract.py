"""Step 1. Pull the variables the analysis needs out of the OECD public-use files.

For 2022 and 2025: identifiers, final and replicate weights, plausible values, the published
indices and every home-possessions item. For 2015 and 2018 (used for the four-cycle series): the
same, with the possessions items of the ST011, ST012 and ST013 questions.
Only OECD members are kept. Output: data/extract/stu_<year> and wts_<year>. A cycle whose raw file is
not found is skipped, so the versioned extract is used as it is.
"""
import sys

import numpy as np

from lib import config as C
from lib.io_utils import clean_id, find_sav, read_sav, sav_columns, save_table, table_exists

KEYS = ["CNT", "CNTSCHID", "CNTSTUID", "OECD", "W_FSTUWT"]
INDICES = ["ESCS", "HOMEPOS", "HISEI", "PAREDINT", "HISCED", "IMMIG"]
WANT = {
    2025: KEYS + C.PV + INDICES + C.COMMON + C.NATIONAL,
    2022: KEYS + C.PV + INDICES + C.COMMON + C.BOOKTYPES + C.DROPPED_OTHER,
    2018: KEYS + C.PV + ["ESCS", "HOMEPOS", "HISEI", "HISCED", "PARED", "PAREDINT"] + C.ITEMS_2015_2018,
    2015: KEYS + C.PV + ["ESCS", "HOMEPOS", "HISEI", "HISCED", "PARED", "PAREDINT"] + C.ITEMS_2015_2018,
}

years = [int(a) for a in sys.argv[1:]] or [2025, 2022, 2018, 2015]
for year in years:
    path = find_sav(year)
    if path is None:
        print(f"{year}: {C.SAV[year]} not found in {C.RAW} - "
              + ("using the extract in data/extract" if table_exists(f"stu_{year}") else "no extract either, cycle skipped"))
        continue
    have = sav_columns(path)
    cols = [c for c in WANT[year] if c in have]
    print(f"{year}: reading {len(cols)} columns from {path.name}"
          + (f" (absent: {sorted(set(WANT[year]) - have)})" if set(WANT[year]) - have else ""))
    d = read_sav(path, cols)
    if "PAREDINT" not in d.columns:                 # 2015: only country-specific years of schooling
        d["PAREDINT"] = np.nan
    d = d.rename(columns={"PARED": "PARED_PUBLISHED", "ST013Q01TA": "BOOKS6"})
    d.columns = [c.lower() for c in d.columns]
    d["cntstuid"], d["cntschid"] = clean_id(d.cntstuid), clean_id(d.cntschid)
    d.insert(0, "wave", year)
    print(f"      {len(d):,} students in {d.cnt.nunique()} OECD systems")
    save_table(d.drop(columns="oecd"), f"stu_{year}")
    w = read_sav(path, ["CNTSTUID"] + C.REPW)
    assert (clean_id(w.CNTSTUID).to_numpy() == d.cntstuid.to_numpy()).all()
    np.save(C.EXTRACT / f"wts_{year}.npy", w[C.REPW].to_numpy("float64"))
