"""Repeat the 2022–2025 mathematics quartile analysis for a selected LATAM sample.

Run from the repository root with the existing Python environment. Unlike step 1,
this reads non-OECD participants too. The common-item model and ESCS are fitted
on the selected countries jointly across both cycles, using the same functions
as steps 3–5. Outputs and caches are separate from the main OECD analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

from lib import brr, config as C, irt
from lib.escs_rule import SEED as IMPUTATION_SEED, escs
from lib.io_utils import clean_id, find_sav
from lib.stats import cell_weights, zscore

NAMES = {
    "ARG": "Argentina", "BRA": "Brasil", "CHL": "Xile", "COL": "Colòmbia",
    "CRI": "Costa Rica", "DOM": "República Dominicana", "GTM": "Guatemala",
    "JAM": "Jamaica", "MEX": "Mèxic", "PAN": "Panamà", "PER": "Perú",
    "PRY": "Paraguai", "SLV": "El Salvador", "URY": "Uruguai",
}
ENGLISH = {**NAMES, "BRA": "Brazil", "CHL": "Chile", "COL": "Colombia",
           "DOM": "Dominican Republic", "MEX": "Mexico", "PAN": "Panama",
           "PER": "Peru", "PRY": "Paraguay", "URY": "Uruguay"}
DEFAULT = ["ARG", "BRA", "CHL", "COL", "MEX", "PER", "URY"]
LABELS = {
    "escs": "ESCS publicat", "escs_h": "ESCS harmonitzat",
    "homepos": "HOMEPOS publicat", "homepos_h": "HOMEPOS harmonitzat",
    "hisei_h": "Ocupació parental (HISEI)", "pared_h": "Educació parental (PARED)",
    "books_h": "Llibres a casa", "escs_pca": "ESCS, primer component principal",
    "escs_cc": "ESCS publicat, casos complets",
    "escs_h_cc": "ESCS harmonitzat, casos complets",
}
INDICES = list(LABELS)
PV = [f"pv{i}math" for i in range(1, 11)]
YEARS = (2022, 2025)
PAIRS = list(itertools.combinations(range(4), 2))
SOURCE_URLS = {
    "2022": "https://www.oecd.org/en/data/datasets/pisa-2022-database.html",
    "2025": "https://www.oecd.org/en/data/datasets/pisa-2025-database.html",
    "participants": "https://www.oecd.org/en/about/programmes/pisa/pisa-participants.html",
    "equity_tables": "https://stat.link/k68msa",
}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def extract(year, countries, cache, refresh):
    """Read data and replicate weights together, preserving their alignment."""
    raw = find_sav(year)
    if raw is None or not raw.is_file():
        raise FileNotFoundError(f"Missing {C.SAV[year]} in {C.RAW}; see data/README.md")
    info = {"file": raw.name, "bytes": raw.stat().st_size, "sha256": sha256(raw),
            "countries": countries, "source": SOURCE_URLS[str(year)]}
    path, manifest = cache / f"stu_{year}.parquet", cache / f"stu_{year}.json"
    if not refresh and path.exists() and manifest.exists() and json.loads(manifest.read_text()) == info:
        print(f"{year}: reading cached selected-country extract", flush=True)
        return pd.read_parquet(path), info
    wanted = (["CNT", "CNTSTUID", "CNTSCHID", "OECD", "W_FSTUWT"] + C.REPW
              + [p.upper() for p in PV] + ["ESCS", "HOMEPOS", "HISEI", "PAREDINT"] + C.COMMON)
    _, meta = pyreadstat.read_sav(raw, metadataonly=True)
    actual = {c.upper(): c for c in meta.column_names}
    absent = set(wanted) - actual.keys()
    if absent:
        raise ValueError(f"{year}: required columns missing: {sorted(absent)}")
    print(f"{year}: extracting {raw.name}, including non-OECD countries", flush=True)
    d, _ = pyreadstat.read_sav(raw, usecols=[actual[c] for c in wanted], user_missing=False)
    d.columns = d.columns.str.lower()
    d = d.loc[d.cnt.isin(countries)].copy().reset_index(drop=True)
    absent_countries = sorted(set(countries) - set(d.cnt))
    if absent_countries:
        print(f"{year}: no observations for {absent_countries}; no estimates for this cycle", flush=True)
    for key in ("cntstuid", "cntschid"):
        d[key] = clean_id(d[key])
    d.insert(0, "wave", year)
    if d.duplicated(["wave", "cnt", "cntstuid"]).any():
        raise ValueError("Duplicate country/student identifiers")
    d.to_parquet(path, index=False)
    write_json(manifest, info)
    print(d.groupby("cnt").size().to_string(), flush=True)
    return d, info


def harmonise(d, cache, refresh, calibration_countries):
    """Fit on the balanced panel; score one-cycle countries on that fixed scale."""
    # Keep all calibration cells before one-cycle cells so regression-imputation
    # random draws for the balanced panel do not depend on adding a one-cycle country.
    balanced = d.cnt.isin(calibration_countries)
    d = pd.concat([d.loc[balanced], d.loc[~balanced]], ignore_index=True).copy()
    calibration = d.cnt.isin(calibration_countries).to_numpy()
    for c in (s.lower() for s in C.BIN):
        d[c] = d[c].where(d[c].isin([1, 2])).map({1: 1.0, 2: 0.0})
    for c in (s.lower() for s in C.CNT4 + C.DEV):
        d[c] = d[c].where(d[c].between(1, 4))
    d["books7"] = d[C.BOOKS.lower()].where(d[C.BOOKS.lower()].between(1, 7))
    d[C.BOOKS.lower()] = d.books7
    items = [s.lower() for s in C.COMMON]
    X = np.full((len(d), len(items)), -1, dtype=np.int8)
    for j, name in enumerate(items):
        x = d[name].to_numpy(float)
        x = x if name in [c.lower() for c in C.BIN] else x - 1
        ok = np.isfinite(x)
        X[ok, j] = x[ok].astype(np.int8)
    d["n_common"] = (X >= 0).sum(axis=1)
    w = cell_weights(d) * calibration
    # The cache fingerprint covers all model inputs and the reused implementations.
    digest = hashlib.sha256(X[calibration].tobytes() + w[calibration].tobytes())
    for name in ("irt.py", "escs_rule.py", "stats.py"):
        digest.update((Path(__file__).parent / "lib" / name).read_bytes())
    fingerprint = digest.hexdigest()
    model_path = cache / "irt_model.json"
    model = json.loads(model_path.read_text()) if model_path.exists() else {}
    if not refresh and model.get("fingerprint") == fingerprint:
        A = np.array(model["a"])
        B = [np.array(x) for x in model["steps"]]
        print("Using cached regional IRT calibration", flush=True)
    else:
        print(f"Fitting common 16-item model on {len(calibration_countries)} countries present in both cycles", flush=True)
        A, B = irt.fit(X[calibration], w[calibration] / w.sum() * calibration.sum())
        model = {"fingerprint": fingerprint, "items": items, "a": A.tolist(),
                 "steps": [b.tolist() for b in B], "min_items": 10,
                 "max_iterations": 60, "tolerance": 0.001,
                 "calibration_countries": calibration_countries}
        write_json(model_path, model)
    scores = irt.wle(X, A, B, min_items=10)
    pared = d.paredint.replace({3.0: 6.0, 14.5: 14.0}).to_numpy(float)
    for name, x in [("hisei_h", d.hisei), ("pared_h", pared),
                    ("homepos_h", scores), ("books_h", d.books7)]:
        d[name] = zscore(x, w)
    raw = np.column_stack([d.hisei, pared, scores])
    groups = d.groupby(["cnt", "wave"], sort=False).ngroup().to_numpy()
    d["escs_h"], _, imputed_pct = escs(raw, groups, w)
    components = d[["hisei_h", "pared_h", "homepos_h"]].to_numpy(float)
    full = np.isfinite(components).all(axis=1) & calibration
    eig, vec = np.linalg.eigh(np.cov(components[full].T, aweights=w[full]))
    v = vec[:, -1] if vec[0, -1] > 0 else -vec[:, -1]
    d["escs_pca"] = zscore(np.where(np.isfinite(components).sum(axis=1) >= 2,
                                   np.nan_to_num(components) @ v, np.nan), w)
    d["complete"] = d[["escs", "hisei", "paredint", "homepos", "homepos_h"]].notna().all(axis=1)
    d.to_parquet(cache / "analysis.parquet", index=False)
    params = pd.DataFrame({"item": C.COMMON, "a": A,
                           "steps": [json.dumps(b.tolist()) for b in B]})
    return d, params, imputed_pct


def covariance(theta):
    """BRR + PV covariance, retaining covariance between groups/indices."""
    t0 = theta[:, 0, :]
    delta = theta[:, 1:, :] - t0[:, None, :]
    sampling = brr.FAY * np.einsum("krm,lrm->kl", delta, delta) / t0.shape[1]
    imputation = (1 + 1 / t0.shape[1]) * np.atleast_2d(np.cov(t0, ddof=1))
    return t0.mean(axis=1), sampling + imputation


def pool(thetas):
    """Equal country weights; independent national sampling and PV variances."""
    stats = [covariance(t) for t in thetas]
    n = len(stats)
    return np.mean([s[0] for s in stats], axis=0), sum(s[1] for s in stats) / n**2


def interval(value, se):
    return {"estimate": float(value), "se": float(se),
            "ci_low": float(value - 1.96 * se), "ci_high": float(value + 1.96 * se)}


def analyse(d, countries):
    th, checks, coverage, overall = {}, [], [], {}
    repcols = [c.lower() for c in C.REPW]
    for (cnt, year), g in d.groupby(["cnt", "wave"], sort=True):
        print(f"Quartiles and 80 BRR replicates: {cnt} {year}", flush=True)
        W = g[["w_fstuwt"] + repcols].to_numpy(float)
        P = g[PV].to_numpy(float)
        if not np.isfinite(W).all() or (W[:, 0] <= 0).any() or (W < 0).any():
            raise ValueError(f"Invalid weights in {cnt} {year}")
        ok = np.isfinite(P).all(axis=1)
        overall[cnt, year] = brr.theta_groups(np.zeros(ok.sum(), dtype=int), W[ok], P[ok], 1)
        for idx in INDICES:
            var = idx.removesuffix("_cc")
            mask = ok & g[var].notna().to_numpy()
            if idx.endswith("_cc"):
                mask &= g.complete.to_numpy()
            n = int(mask.sum())
            coverage.append({"cnt": cnt, "wave": year, "index": idx, "n_total": len(g),
                             "n_valid": n, "valid_weight_pct": 100 * W[mask, 0].sum() / W[:, 0].sum(),
                             "status": "estimated" if n >= 200 else "fewer than 200 valid students"})
            if n < 200:
                continue
            x, weights, pvs = g[var].to_numpy(float)[mask], W[mask], P[mask]
            theta = brr.theta_quartiles(x, weights, pvs)
            if not np.isfinite(theta).all():
                raise ValueError(f"Empty replicate quartile: {cnt} {year} {idx}")
            th[cnt, year, idx] = theta
            point, cov = covariance(theta)
            expected, se = brr.summarise(theta)
            np.testing.assert_allclose(point, expected, atol=1e-10)
            np.testing.assert_allclose(np.sqrt(np.diag(cov)), se, atol=1e-10)
            code = brr.quartile_codes(x, weights)
            row = {"cnt": cnt, "wave": year, "index": idx, "n": n}
            for k in range(4):
                row[f"weight_Q{k+1}"] = 100 * weights[code == k, 0].sum() / weights[:, 0].sum()
                row[f"n_Q{k+1}"] = int((code == k).sum())
            # A whole student crosses a boundary: imbalance is bounded by that weight.
            bound = 100 * weights[:, 0].max() / weights[:, 0].sum()
            assert max(abs(row[f"weight_Q{k}"] - 25) for k in range(1, 5)) <= bound + 1e-9
            weighted = sum(row[f"weight_Q{k+1}"] / 100 * point[k] for k in range(4))
            np.testing.assert_allclose(weighted, np.average(pvs.mean(axis=1), weights=weights[:, 0]), atol=1e-9)
            checks.append(row)

    levels, changes, wide, effects, means = [], [], [], [], []
    paired_countries = [c for c in countries if all((c, y) in overall for y in YEARS)]
    for cnt in countries:
        for year in YEARS:
            if (cnt, year) not in overall:
                for idx in INDICES:
                    coverage.append({"cnt": cnt, "wave": year, "index": idx, "n_total": 0,
                                     "n_valid": 0, "valid_weight_pct": np.nan,
                                     "status": "country absent from cycle"})
    contrasts = [(f"Q{k+1}", np.eye(4)[k], C.LINK_ERROR_2022_2025["math"]) for k in range(4)]
    for i, j in PAIRS:
        c = np.zeros(4)
        c[i], c[j] = -1, 1
        contrasts.append((f"Q{j+1}-Q{i+1}", c, 0.0))
    for idx in INDICES:
        paired = [cnt for cnt in countries if all((cnt, y, idx) in th for y in YEARS)]
        aggregate = f"LATAM{len(paired)}"
        for cnt in paired + ([aggregate] if paired else []):
            selected = paired if cnt == aggregate else [cnt]
            summaries = {y: pool([th[c, y, idx] for c in selected]) for y in YEARS}
            e22, v22 = summaries[2022]
            e25, v25 = summaries[2025]
            common = {"cnt": cnt, "index": idx, "n_systems": len(selected), "countries": ",".join(selected),
                      "status": "both cycles"}
            wr = dict(common)
            for group, contrast, link in contrasts:
                a, b = float(contrast @ e22), float(contrast @ e25)
                sa, sb = (np.sqrt(max(0, contrast @ v @ contrast)) for v in [v22, v25])
                for y, value, se in [(2022, a, sa), (2025, b, sb)]:
                    levels.append({**common, "wave": y, "group": group, **interval(value, se)})
                change_se = np.sqrt(sa**2 + sb**2 + link**2)
                changes.append({**common, "group": group, "mean_2022": a, "mean_2025": b,
                                "link_se": link, **interval(b - a, change_se)})
                wr.update({f"{group}_2022": a, f"{group}_2025": b,
                           f"{group}_change": b - a, f"{group}_se": change_se})
            wide.append(wr)

        for cnt in countries:
            if cnt in paired:
                continue
            available = [y for y in YEARS if (cnt, y, idx) in th]
            if not available:
                continue
            common = {"cnt": cnt, "index": idx, "n_systems": 1, "countries": cnt,
                      "status": "only " + ",".join(map(str, available))}
            wr = dict(common)
            for group, contrast, _ in contrasts:
                for year in YEARS:
                    wr[f"{group}_{year}"] = np.nan
                wr[f"{group}_change"], wr[f"{group}_se"] = np.nan, np.nan
                for year in available:
                    estimate, cov = covariance(th[cnt, year, idx])
                    value = float(contrast @ estimate)
                    se = np.sqrt(max(0, contrast @ cov @ contrast))
                    levels.append({**common, "wave": year, "group": group, **interval(value, se)})
                    wr[f"{group}_{year}"] = value
            wide.append(wr)

    aggregate = f"LATAM{len(paired_countries)}"
    for cnt in countries + [aggregate]:
        selected = paired_countries if cnt == aggregate else [cnt]
        s = [pool([overall[c, y] for c in selected]) if all((c, y) in overall for c in selected)
             else (np.array([np.nan]), np.array([[np.nan]])) for y in YEARS]
        a, b = (x[0][0] for x in s)
        sa, sb = (np.sqrt(x[1][0, 0]) for x in s)
        means.append({"cnt": cnt, "n_systems": len(selected), "mean_2022": a, "mean_2025": b,
                      "countries": ",".join(selected), "status": "both cycles" if np.isfinite([a,b]).all() else "one cycle only",
                      "se_2022": sa, "se_2025": sb, **interval(b-a, brr.mean_change_se(sa, sb, "math"))})

    # Paired contrasts preserve covariance of the two indices within a country/cycle.
    for published, harmonised in [("escs", "escs_h"), ("homepos", "homepos_h"), ("escs_cc", "escs_h_cc")]:
        paired = [c for c in countries if all((c, y, i) in th for y in YEARS for i in [published, harmonised])]
        if not paired:
            continue
        aggregate = f"LATAM{len(paired)}"
        for cnt in paired + [aggregate]:
            selected = paired if cnt == aggregate else [cnt]
            s = [pool([th[c, y, harmonised] - th[c, y, published] for c in selected]) for y in YEARS]
            contrast = np.array([-1, 0, 0, 1])
            value = contrast @ (s[1][0] - s[0][0])
            se = np.sqrt(max(0, contrast @ (s[0][1] + s[1][1]) @ contrast))
            effects.append({"cnt": cnt, "published": published, "harmonised": harmonised,
                            "n_systems": len(selected), "countries": ",".join(selected), **interval(value, se)})
    return {"quartile_levels_math": pd.DataFrame(levels), "quartile_changes_math": pd.DataFrame(changes),
            "quartiles_math": pd.DataFrame(wide), "coverage": pd.DataFrame(coverage),
            "quartile_check_math": pd.DataFrame(checks), "overall_math": pd.DataFrame(means),
            "harmonisation_effect_math": pd.DataFrame(effects)}, th


def compare_sources(tables, countries):
    """Compare raw-data estimates with existing Python results and OECD workbook."""
    q = tables["quartiles_math"]
    old = pd.read_csv(C.TABLES / "quartiles_math.csv")
    cols = [c for c in old.columns if c.startswith("Q")]
    matched = q[q["index"].isin(["escs", "homepos"])].merge(old, on=["cnt", "index"], suffixes=("_new", "_old"))
    rows = []
    for _, r in matched.iterrows():
        for col in cols:
            rows.append({"cnt": r.cnt, "index": r["index"], "field": col,
                         "new": r[col + "_new"], "existing": r[col + "_old"],
                         "difference": r[col + "_new"] - r[col + "_old"]})
    tables["existing_python_comparison"] = pd.DataFrame(rows)
    if rows:
        assert tables["existing_python_comparison"].difference.abs().max() < 1e-8

    official = []
    path = C.ROOT / "reference" / "oecd_2025_equity.xlsx"
    for idx, number in [("escs", 24), ("homepos", 38)]:
        sheet = f"Table I.B1.2b.{number}"
        data = pd.read_excel(path, sheet_name=sheet, header=None)
        names = data.iloc[:, 0].astype(str).str.replace("*", "", regex=False).str.strip()
        for cnt in countries:
            record = data.loc[names == ENGLISH[cnt]]
            if len(record) != 1:
                raise ValueError(f"Expected one OECD reference row for {cnt}, {sheet}")
            values = pd.to_numeric(record.iloc[0, 1:], errors="coerce").to_numpy()
            for k, group in enumerate(["Q1", "Q2", "Q3", "Q4", "Q4-Q1"]):
                for year, start in [(2022, 20), (2025, 30), ("change", 60)]:
                    source = tables["quartile_changes_math"] if year == "change" else tables["quartile_levels_math"]
                    match = source[(source.cnt == cnt) & (source["index"] == idx) & (source.group == group)]
                    if year != "change":
                        match = match[match.wave == year]
                    if match.empty:
                        continue
                    r = match.iloc[0]
                    for stat, offset in [("estimate", 0), ("se", 1)]:
                        published = values[start + 2 * k + offset]
                        official.append({"cnt": cnt, "index": idx, "wave": year, "group": group, "statistic": stat,
                                         "computed": r[stat], "official": published,
                                         "difference": r[stat] - published, "source_table": sheet})
    tables["official_comparison"] = pd.DataFrame(official)


def check_aggregates(tables):
    """Check reported means/SEs independently from the national CSV-ready rows."""
    count = 0
    for _, group in tables["quartile_changes_math"].groupby(["index", "group"]):
        national = group[~group.cnt.str.startswith("LATAM")]
        aggregate = group[group.cnt.str.startswith("LATAM")].iloc[0]
        n, link = len(national), aggregate.link_se
        np.testing.assert_allclose(aggregate.estimate, national.estimate.mean(), atol=1e-10)
        expected_se = np.sqrt((national.se**2 - link**2).sum() / n**2 + link**2)
        np.testing.assert_allclose(aggregate.se, expected_se, atol=1e-10)
        assert aggregate.n_systems == n
        count += 1
    return count


def figures(tables, countries, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for path in (C.ROOT / "assets" / "fonts").glob("*.ttf"):
        font_manager.fontManager.addfont(str(path))
    plt.rcParams.update({"font.family": "Source Sans 3", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "legend.frameon": False})
    colors = ["#2b5c8a", "#C0370C"]
    nrows = (len(countries) + 2) // 3
    def save(fig, name):
        fig.savefig(out / f"{name}.png", dpi=220, bbox_inches="tight")
        fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
        plt.close(fig)
    for family in ["escs", "homepos"]:
        fig, axes = plt.subplots(nrows, 3, figsize=(12, 3.3*nrows), sharex=True, sharey=True, squeeze=False)
        for ax, cnt in zip(axes.flat, countries):
            available = False
            for j, idx in enumerate([family, family + "_h"]):
                g = tables["quartile_changes_math"]
                g = g[(g.cnt == cnt) & (g["index"] == idx) & g.group.isin(["Q1", "Q2", "Q3", "Q4"])].sort_values("group")
                if len(g) == 4:
                    available = True
                    ax.errorbar(np.arange(1,5) + (j-.5)*.05, g.estimate, yerr=1.96*g.se,
                                color=colors[j], marker="o", lw=1.6, capsize=3, label=LABELS[idx])
            ax.axhline(0, color="0.45", lw=.8)
            ax.set_title(NAMES[cnt], loc="left", fontweight="semibold")
            ax.set_xticks(range(1,5), ["Q1", "Q2", "Q3", "Q4"])
            ax.tick_params(axis="x", labelbottom=True)
            ax.grid(axis="y", color=".9", lw=.6)
            if not available:
                ax.text(.5, .5, "Sense dades als dos cicles\nCanvi no disponible",
                        transform=ax.transAxes, ha="center", va="center", color=".4")
        for ax in list(axes.flat)[len(countries):]:
            ax.set_visible(False)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(.5,.015))
        fig.suptitle(f"Matemàtiques: canvi 2022–2025 per quartil d’{family.upper()}", fontsize=16, x=.07, ha="left")
        fig.supylabel("Canvi en punts PISA · IC del 95%", x=.015)
        fig.text(.5, -.012, "Q1: quartil inferior · Q4: superior. Harmonització recalibrada amb la mostra seleccionada.", ha="center", fontsize=10)
        fig.tight_layout(rect=(.035,.08,1,.96))
        save(fig, f"quartile_changes_{family}_math")
    for idx in ["escs", "escs_h"]:
        fig, axes = plt.subplots(nrows, 3, figsize=(12, 3.3*nrows), sharex=True, sharey=True, squeeze=False)
        for ax, cnt in zip(axes.flat, countries):
            available_years = []
            for j, year in enumerate(YEARS):
                g = tables["quartile_levels_math"]
                g = g[(g.cnt == cnt) & (g["index"] == idx) & (g.wave == year) & g.group.isin(["Q1", "Q2", "Q3", "Q4"])].sort_values("group")
                if len(g) == 4:
                    available_years.append(year)
                    ax.errorbar(np.arange(1,5) + (j-.5)*.05, g.estimate, yerr=1.96*g.se,
                                color=colors[j], marker="o", lw=1.6, capsize=3, label=str(year))
            ax.set_title(NAMES[cnt], loc="left", fontweight="semibold")
            ax.set_xticks(range(1,5), ["Q1", "Q2", "Q3", "Q4"])
            ax.tick_params(axis="x", labelbottom=True)
            ax.grid(axis="y", color=".9", lw=.6)
            if len(available_years) == 1:
                ax.text(.03, .94, f"Només {available_years[0]}", transform=ax.transAxes,
                        va="top", color=".4", fontsize=10)
        for ax in list(axes.flat)[len(countries):]:
            ax.set_visible(False)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(.5,.015))
        fig.suptitle(f"Matemàtiques per quartil · {LABELS[idx]}", fontsize=16, x=.07, ha="left")
        fig.supylabel("Punts PISA · IC del 95%", x=.015)
        fig.tight_layout(rect=(.035,.08,1,.96))
        save(fig, f"quartile_levels_{idx}_math")


def report(tables, countries, calibration_countries, out, validation):
    aggregate = f"LATAM{len(calibration_countries)}"
    q = tables["quartiles_math"].set_index(["cnt", "index"])
    def signed(x):
        if not np.isfinite(x):
            return "—"
        return f"{x:+.1f}".replace(".", ",").replace("-", "−")
    def ci(r, stem="Q4-Q1"):
        value, se = r[f"{stem}_change"], r[f"{stem}_se"]
        if not np.isfinite(value):
            return "Sense comparació 2022–2025"
        return f"{signed(value)} [{signed(value-1.96*se)}; {signed(value+1.96*se)}]"
    findings = []
    for pub, har, name in [("escs", "escs_h", "ESCS"), ("homepos", "homepos_h", "HOMEPOS")]:
        if (aggregate, pub) in q.index and (aggregate, har) in q.index:
            a, b = q.loc[aggregate, pub], q.loc[aggregate, har]
            findings.append(f"- **{name}:** canvi mitjà de la bretxa Q4−Q1 de {ci(a)} punts amb l’índex publicat "
                            f"i de {ci(b)} amb l’harmonitzat (IC del 95%).")
    if (aggregate, "escs_h") in q.index:
        r = q.loc[aggregate, "escs_h"]
        findings.append(f"- Amb l’ESCS harmonitzat, el canvi mitjà de Q1 és {signed(r.Q1_change)} punts "
                        f"i el de Q4 és {signed(r.Q4_change)} punts.")
        significant = [NAMES[c] for c in countries if (c, "escs_h") in q.index
                       and abs(q.loc[c, "escs_h"]["Q4-Q1_change"]) > 1.96*q.loc[c, "escs_h"]["Q4-Q1_se"]]
        findings.append("- Països amb un canvi de bretxa ESCS harmonitzada amb IC del 95% que exclou el zero: "
                        + (", ".join(significant) if significant else "cap") + ".")
    cov = tables["coverage"]
    low = cov[cov["index"] == "escs_h"].sort_values("valid_weight_pct").iloc[0]
    findings.append(f"- La menor cobertura de l’ESCS harmonitzat és a {NAMES[low.cnt]}, {int(low.wave)}: "
                    f"{str(round(low.valid_weight_pct, 1)).replace('.', ',')}% del pes de la mostra. "
                    "Les taules de casos complets permeten comparar els dos índexs sobre els mateixos alumnes, "
                    "però no corregeixen possibles biaixos per no-resposta.")
    lines = ["# Matemàtiques per quartil socioeconòmic a l’Amèrica Llatina", "",
             "Comparació PISA 2022–2025. Mostra: " + ", ".join(NAMES[c] for c in countries) + ".", "",
             "Aquests països són la selecció de l’anàlisi, no la llista completa de participants de la regió.", "",
             f"**Cobertura temporal:** {len(countries)} països als nivells disponibles; "
             f"{len(calibration_countries)} països a la comparació 2022–2025 i a la calibració: "
             + ", ".join(NAMES[c] for c in calibration_countries) + ".", "",
             "## Resultats principals", "", *findings, "",
             "## Canvi de la bretxa Q4−Q1", "",
             "Punts PISA; entre claudàtors, interval de confiança del 95%. Un valor negatiu indica que la bretxa es redueix.", "",
             "| País | ESCS publicat | ESCS harmonitzat |", "|---|---:|---:|"]
    for cnt in countries + [aggregate]:
        entries = [ci(q.loc[cnt, idx]) if (cnt, idx) in q.index else "No estimable" for idx in ["escs", "escs_h"]]
        lines.append(f"| {NAMES.get(cnt, 'Mitjana simple de la selecció')} | " + " | ".join(entries) + " |")
    lines += ["", "La mitjana dona el mateix pes a cada país amb dades als dos cicles. Les taules indiquen quants països entren en cada índex.", "",
              "## Canvis per quartil", "", "| País | Índex | Q1 | Q2 | Q3 | Q4 |", "|---|---|---:|---:|---:|---:|"]
    for cnt in countries + [aggregate]:
        for idx in ["escs", "escs_h", "homepos", "homepos_h"]:
            if (cnt, idx) in q.index and np.isfinite(q.loc[cnt, idx].Q1_change):
                r = q.loc[cnt, idx]
                lines.append(f"| {NAMES.get(cnt, 'Mitjana simple')} | {LABELS[idx]} | " + " | ".join(signed(r[f"Q{k}_change"]) for k in range(1,5)) + " |")
    lines += ["", "## Nivells de matemàtiques el 2025", "",
              "Punts PISA. Els errors estàndard i intervals de confiança es troben a l’Excel i a la taula de nivells.", "",
              "| País | Índex | Q1 | Q2 | Q3 | Q4 | Bretxa Q4−Q1 |", "|---|---|---:|---:|---:|---:|---:|"]
    for cnt in countries:
        for idx in ["escs", "escs_h"]:
            if (cnt, idx) in q.index:
                r = q.loc[cnt, idx]
                vals = [r[f"Q{k}_2025"] for k in range(1,5)] + [r["Q4-Q1_2025"]]
                lines.append(f"| {NAMES[cnt]} | {LABELS[idx]} | " + " | ".join(f"{x:.1f}".replace(".", ",") if np.isfinite(x) else "—" for x in vals) + " |")
    lines += ["", "## Gràfics", "",
              "![Canvi per quartil d’ESCS](figures/quartile_changes_escs_math.png)", "",
              "![Nivells per quartil d’ESCS harmonitzat](figures/quartile_levels_escs_h_math.png)", "",
              "## Mètode i interpretació", "",
              "S’han extret els estudiants dels fitxers originals, incloent-hi els països no membres de l’OCDE. "
              "Els quartils es defineixen dins de cada país i any, amb aproximadament el 25% del pes final per grup. "
              "Els empats es desfan amb llavor 7. Q1 i Q4 descriuen posicions relatives dins de cada país, no un mateix nivell de renda internacional. "
              "Les dues onades són mostres diferents d’estudiants; els canvis no són seguiments individuals.", "",
              "Les estimacions utilitzen els deu valors plausibles de matemàtiques i 80 rèpliques BRR amb Fay 0,5; "
              "els quartils es recalculen a cada rèplica. Les variàncies nacionals s’agreguen com a mostres independents, "
              "igual que en l’especificació principal en R del projecte. S’afegeix una sola vegada l’error d’enllaç "
              "d’1,220 punts als canvis de mitjanes, també a la mitjana internacional. Aquest error es cancel·la en "
              "els canvis de bretxa Q4−Q1. Els intervals són estimació ± 1,96 errors estàndard.", "",
              "HOMEPOS harmonitzat: model 2PL/GPCM amb els mateixos 16 ítems comuns, recodificacions i funcions Python "
              "del projecte; calibració conjunta 2022+2025 dels països amb dades als dos cicles, amb el mateix pes per país-any; puntuació WLE amb un mínim "
              "de deu respostes. ESCS harmonitzat: HISEI, PARED (3→6 i 14,5→14) i HOMEPOS comú, imputació per "
              "regressió d’un únic component absent dins del país-any, estandardització conjunta i mitjana de pes igual.", "",
              f"**La calibració i l’estandardització es refan amb els {len(calibration_countries)} països amb dades als dos cicles.** "
              "Per això l’índex harmonitzat "
              "és una extensió regional del mètode i no conserva exactament els resultats de la calibració OCDE del "
              "repositori. No és una escala de tendència oficial de l’OCDE. Els errors estàndard, com en el projecte, "
              "són condicionals als índexs reconstruïts: no recalibren l’IRT ni refan la imputació a cada rèplica.", "",
              "S’ofereixen també quartils d’HISEI, PARED i llibres, un compost per components principals, i la comparació "
              "ESCS publicat/harmonitzat restringida als mateixos casos complets. La taula `harmonisation_effect_math` "
              "contrasta els canvis de bretxa entre índexs conservant-ne la covariància. No s’han ajustat els intervals "
              "per comparacions múltiples; les diferències són descriptives i no identifiquen efectes causals.", "",
              "## Validació", "",
              f"- Identificadors únics, pesos vàlids i alineats amb els valors plausibles: comprovats.",
              f"- Desviació màxima del 25% de pes d’un quartil: {validation['max_quartile_weight_deviation_pp']:.3f} punts percentuals.",
              f"- Resultats publicats comparables amb el Python original: {validation['existing_comparison_cells']} cel·les; "
              f"diferència màxima {validation['existing_max_abs_difference']:.3g} punts.",
              f"- Mitjanes internacionals i errors estàndard: {validation['aggregate_checks']} comprovacions "
              "a partir dels resultats nacionals, incloent-hi l’aplicació de l’error d’enllaç una sola vegada.",
              f"- Comparació amb les taules OCDE I.B1.2b.24 i I.B1.2b.38: discrepància màxima de les estimacions "
              f"{validation['official_max_abs_estimate_difference']:.3f} punts i dels errors estàndard "
              f"{validation['official_max_abs_se_difference']:.3f} punts. Vegeu totes les diferències a `official_comparison.csv`.", "",
              "Les taules publicades i la reproducció poden diferir per empats als límits dels quartils, procediments "
              "de variància i revisions dels fitxers públics posteriors a la publicació. La comprovació informa de "
              "les diferències observades i no força una coincidència.", "",
              "## Fitxers i reproducció", "",
              "- [Llibre Excel](latam_mathematiques.xlsx): nivells, canvis, bretxes, cobertura i validacions.",
              "- [Taula principal](tables/quartiles_math.csv): mateix format ample que l’anàlisi del projecte.",
              "- [Nivells i intervals](tables/quartile_levels_math.csv) i [canvis i intervals](tables/quartile_changes_math.csv).",
              "- [Cobertura](tables/coverage.csv): alumnes i percentatge ponderat vàlid per índex, país i any.",
              "- [Disponibilitat per país](tables/country_availability.csv): observacions per cicle i inclusió a les tendències.",
              "- [Fonts i configuració](sources.json): SHA-256 dels originals, selecció i versions.", "",
              "```bash", ".venv/bin/python code/python/scripts/14_latam_quartiles.py --countries " + " ".join(countries), "```", "",
              "Els originals han de ser a `data/raw/` o `PISA_RAW_DIR`. `--refresh` refà l’extracció i la calibració. "
              "Les memòries cau són a `data/interim/python/latam/`; aquesta anàlisi no requereix executar la resta del pipeline.", "",
              "## Fonts", "",
              f"Microdades oficials: [PISA 2022]({SOURCE_URLS['2022']}) i [PISA 2025]({SOURCE_URLS['2025']}). "
              "S’han utilitzat les còpies locals ja documentades a `data/README.md`, descarregades el 18 de setembre de 2026; "
              "no ha calgut tornar-les a descarregar. Portals consultats el 23 de setembre de 2026.", "",
              f"[Participants]({SOURCE_URLS['participants']}); [taules oficials d’equitat]({SOURCE_URLS['equity_tables']}). "
              "Les constants d’enllaç i els documents tècnics es descriuen a `reference/README.md`.", ""]
    (out / "README.md").write_text("\n".join(lines))

    gaps = tables["quartile_changes_math"]
    gaps = gaps[(gaps.group == "Q4-Q1") & gaps["index"].isin(["escs", "escs_h", "homepos", "homepos_h", "escs_cc", "escs_h_cc"])]
    tables["gap_summary_math"] = gaps.reset_index(drop=True)
    with pd.ExcelWriter(out / "latam_mathematiques.xlsx", engine="openpyxl") as writer:
        pd.DataFrame({"nota": [line for line in lines if line and not line.startswith(("|", "![", "#"))]}).to_excel(writer, sheet_name="Notes", index=False)
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)
        for sheet in writer.book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cells in sheet.columns:
                width = min(52, max(12, max(len(str(c.value or "")) for c in list(cells)[:60]) + 2))
                sheet.column_dimensions[cells[0].column_letter].width = width
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    if isinstance(cell.value, float):
                        cell.number_format = "0.00"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", default=DEFAULT, choices=sorted(NAMES))
    parser.add_argument("--output", type=Path, default=C.RESULTS / "latam")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    countries = list(dict.fromkeys(args.countries))
    out = args.output.resolve()
    cache = C.INTERIM / "latam" / "_".join(countries)
    for path in [out, out / "tables", out / "figures", cache]:
        path.mkdir(parents=True, exist_ok=True)
    parts, sources = [], {}
    for year in YEARS:
        frame, info = extract(year, countries, cache, args.refresh)
        parts.append(frame)
        sources[str(year)] = info
    d = pd.concat(parts, ignore_index=True)
    del parts
    missing = set(countries) - set(d.cnt)
    if missing:
        raise ValueError(f"Requested countries absent from both cycles: {sorted(missing)}")
    calibration_countries = [c for c in countries if all(((d.cnt == c) & (d.wave == y)).any() for y in YEARS)]
    if not calibration_countries:
        raise ValueError("Harmonization needs at least one country with both cycles")
    availability = pd.DataFrame([{"cnt": c, "country": NAMES[c],
                                  **{f"n_{y}": int(((d.cnt == c) & (d.wave == y)).sum()) for y in YEARS},
                                  "in_trend": c in calibration_countries} for c in countries])
    d, params, imputed_pct = harmonise(d, cache, args.refresh, calibration_countries)
    tables, th = analyse(d, countries)
    tables["country_availability"] = availability
    np.savez_compressed(cache / "theta_quartiles_math.npz", **{"__".join(map(str, k)): v for k, v in th.items()})
    tables["irt_parameters"] = params
    compare_sources(tables, countries)
    checks = tables["quartile_check_math"]
    old = tables["existing_python_comparison"]
    official = tables["official_comparison"]
    validation = {"max_quartile_weight_deviation_pp": float((checks[[f"weight_Q{k}" for k in range(1,5)]] - 25).abs().max().max()),
                  "min_quartile_n": int(checks[[f"n_Q{k}" for k in range(1,5)]].min().min()),
                  "existing_comparison_cells": len(old),
                  "existing_max_abs_difference": float(old.difference.abs().max()) if len(old) else 0,
                  "official_max_abs_estimate_difference": float(official.loc[official.statistic == "estimate", "difference"].abs().max()),
                  "official_max_abs_se_difference": float(official.loc[official.statistic == "se", "difference"].abs().max()),
                  "total_students": len(d), "all_checks_passed": True}
    validation["aggregate_checks"] = check_aggregates(tables)
    validation["countries_requested"] = len(countries)
    validation["countries_in_trend"] = len(calibration_countries)
    validation["unavailable_country_cycles"] = [f"{r.cnt}/{y}" for r in availability.itertuples()
                                                for y in YEARS if getattr(r, f"n_{y}") == 0]
    for row in availability.itertuples():
        for year in YEARS:
            if getattr(row, f"n_{year}") == 0:
                levels = tables["quartile_levels_math"]
                assert not ((levels.cnt == row.cnt) & (levels.wave == year)).any()
                assert row.cnt not in set(tables["quartile_changes_math"].cnt)
                assert row.cnt not in set(tables["harmonisation_effect_math"].cnt)
                national = tables["quartiles_math"].query("cnt == @row.cnt")
                assert national[[f"Q{k}_change" for k in range(1,5)]].isna().all().all()
    metadata = {"generated_utc": datetime.now(timezone.utc).isoformat(), "countries": countries,
                "selection": ("User-confirmed original six countries, extended with Peru."
                              if countries == DEFAULT else "Country sample selected through --countries"),
                "cycles": YEARS, "domain": "math", "raw_files": sources, "urls": SOURCE_URLS,
                "calibration_countries": calibration_countries,
                "calibration": "Only countries present in both cycles; equal weight per country-cycle. One-cycle countries scored on that fixed scale.",
                "international_variance": "Sum independent national covariance matrices divided by n_systems squared",
                "link_se": C.LINK_ERROR_2022_2025["math"], "quartile_seed": C.SEED,
                "imputation_seed": IMPUTATION_SEED, "imputed_pct": imputed_pct,
                "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                "script_sha256": sha256(__file__), "equity_workbook_sha256": sha256(C.ROOT / "reference" / "oecd_2025_equity.xlsx")}
    figures(tables, countries, out / "figures")
    report(tables, countries, calibration_countries, out, validation)
    for name, table in tables.items():
        table.to_csv(out / "tables" / f"{name}.csv", index=False)
    write_json(out / "sources.json", metadata)
    write_json(out / "validation.json", validation)
    print(json.dumps(validation, indent=2), flush=True)
    print(tables["gap_summary_math"].to_string(index=False), flush=True)
    print(f"Saved report, Excel, CSV tables and PDF/PNG figures to {out}", flush=True)


if __name__ == "__main__":
    main()
