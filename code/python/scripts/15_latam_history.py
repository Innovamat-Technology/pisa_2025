"""Q4-Q1 mathematics gaps by published/harmonized indices, 2015–2025.

Each cycle's gap is computed, not a difference between cycles. A pooled 13-item
model harmonizes home possessions across all four cycles. Argentina 2015 is excluded
because OECD documents an incomplete sampling frame; Buenos Aires is not used as
a substitute for Argentina. Render the results with 16_latam_reports.py.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

from lib import brr, config as C, irt
from lib.escs_rule import escs
from lib.io_utils import clean_id, find_sav
from lib.stats import cell_weights, zscore

COUNTRIES = ["ARG", "BRA", "CHL", "COL", "MEX", "PER", "URY"]
YEARS = [2015, 2018, 2022, 2025]
PUBLISHED = ["escs", "homepos"]
INDICES = ["escs", "escs_h4", "homepos", "homepos_h4"]
PV = [f"pv{i}math" for i in range(1, 11)]
COLS = ["cnt", "cntstuid", "cntschid", "w_fstuwt"] + [x.lower() for x in C.REPW] + PV + PUBLISHED
ENGLISH = dict(ARG="Argentina", BRA="Brazil", CHL="Chile", COL="Colombia", MEX="Mexico", PER="Peru", URY="Uruguay")
ARGENTINA_SOURCE = "https://www.oecd.org/en/publications/pisa-2018-results-volume-i_5f07c754-en/full-report/component-9.html"
ITEMS = {
    "room":("st011q02ta","st250q01ja","binary"),
    "computer_school":("st011q04ta","st250q02ja","binary"),
    "software":("st011q05ta","st250q03ja","binary"),
    "internet":("st011q06ta","st250q05ja","binary"),
    "art":("st011q09ta","st251q07ja","art"),
    "instruments":("st012q09na","st251q06ja","count"),
    "cars":("st012q02ta","st251q01ja","count"),
    "bathrooms":("st012q03ta","st251q03ja","count"),
    "televisions":("st012q01ta","st254q01ja","band"),
    "tablets":("st012q07na","st254q04ja","band"),
    "ereaders":("st012q08na","st254q05ja","band"),
    "computers":("st012q06na","st254q02ja","computers"),
    "books":("st013q01ta","st255q01ja","books"),
}


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def extract(year, cache, refresh=False):
    raw = find_sav(year)
    if raw is None or not raw.is_file():
        raise FileNotFoundError(f"Required original file: {C.SAV[year]}")
    item_cols = [v[0 if year <= 2018 else 1] for v in ITEMS.values()]
    if year >= 2022:
        item_cols.append("st254q03ja")
    cols = list(dict.fromkeys(COLS + ["hisei", "hisced"] + ([] if year == 2015 else ["paredint"]) + item_cols))
    info = {"file": raw.name, "sha256": sha(raw), "bytes": raw.stat().st_size,
            "source": f"https://www.oecd.org/en/data/datasets/pisa-{year}-database.html",
            "countries": COUNTRIES, "columns": cols}
    p, manifest = cache / f"stu_{year}.parquet", cache / f"stu_{year}.json"
    if not refresh and p.exists() and manifest.exists() and json.loads(manifest.read_text()) == info:
        print(f"{year}: cached historical extract", flush=True)
        return pd.read_parquet(p), info
    recent = C.INTERIM / "latam" / "_".join(COUNTRIES)
    if not refresh and year >= 2022 and (recent / f"stu_{year}.json").exists() and (recent / f"stu_{year}.parquet").exists():
        previous = json.loads((recent / f"stu_{year}.json").read_text())
        if previous["sha256"] == info["sha256"] and previous["countries"] == COUNTRIES:
            print(f"{year}: reusing verified raw extract from the seven-country analysis", flush=True)
            # HISCED is needed only to reconstruct 2015 parental education from
            # its 2018 mapping; the recent analysis did not retain that column.
            d = pd.read_parquet(recent / f"stu_{year}.parquet", columns=["wave"] + [c for c in cols if c != "hisced"])
            d["hisced"] = np.nan
            d.to_parquet(p, index=False)
            write_json(manifest, info)
            return d, info
    print(f"{year}: extracting {raw.name} without an OECD-membership filter", flush=True)
    _, meta = pyreadstat.read_sav(raw, metadataonly=True)
    actual = {c.lower(): c for c in meta.column_names}
    absent = set(cols) - actual.keys()
    if absent:
        raise ValueError(f"{year}: missing required columns: {sorted(absent)}")
    d, _ = pyreadstat.read_sav(raw, usecols=[actual[c] for c in cols], user_missing=False)
    d.columns = d.columns.str.lower()
    d = d.loc[d.cnt.isin(COUNTRIES)].copy().reset_index(drop=True)
    for col in ["cntstuid", "cntschid"]:
        d[col] = clean_id(d[col])
    d.insert(0, "wave", year)
    assert not d.duplicated(["cnt", "cntstuid"]).any()
    d.to_parquet(p, index=False)
    write_json(manifest, info)
    print(d.groupby("cnt").size().to_string(), flush=True)
    return d, info


def harmonize(parts, cache):
    """Regional four-cycle specification, with the R workflow's missing-data fix."""
    recoded=[]
    for year, frame in parts.items():
        g=frame.copy()
        if year==2015:
            g=g.loc[g.cnt!="ARG"].copy()
            g["paredint"]=np.nan
        for name,(old,new,kind) in ITEMS.items():
            x=g[old if year<=2018 else new]
            valid=x.where(x.between(1,4))
            if kind=="binary" or (kind=="art" and year<=2018):
                value=x.where(x.isin([1,2])).map({1:1.0,2:0.0})
            elif kind=="art":
                value=(valid>1).astype(float).where(valid.notna())
            elif kind=="count":
                value=valid-1
            elif kind=="band":
                value=valid.map({1:0.0,2:1.0,3:1.0 if year<=2018 else 2.0,4:2.0})
            elif kind=="books":
                value=x.where(x.between(1,6))-1 if year<=2018 else (x.where(x.between(1,7))-1).clip(lower=1)-1
            elif year<=2018:
                value=(valid>=2).astype(float).where(valid.notna())
            else:
                other=g.st254q03ja.where(g.st254q03ja.between(1,4))
                value=pd.Series(np.nan,index=g.index)
                value.loc[(valid>=2)|(other>=2)]=1.0
                value.loc[(valid==1)&(other==1)]=0.0
                # None plus unknown is missing, as in the corrected R workflow.
                assert value.loc[(valid==1)&other.isna()].isna().all()
            g[name]=value
        recoded.append(g[["wave"]+COLS+["hisei","hisced","paredint"]+list(ITEMS)])
    d=pd.concat(recoded,ignore_index=True).copy()
    reference=d.loc[(d.wave==2018)&d.hisced.notna()&d.paredint.notna()]
    mapping=reference.groupby("hisced").paredint.agg(lambda x:x.mode().iloc[0]).to_dict()
    m=d.wave==2015
    assert set(d.loc[m,"hisced"].dropna().unique())<=set(mapping)
    d.loc[m,"paredint"]=d.loc[m,"hisced"].map(mapping)
    d["pared_c"]=d.paredint.replace({3.0:6.0,14.5:14.0})
    x=d[list(ITEMS)].to_numpy(float)
    X=np.where(np.isfinite(x),x,-1).astype(np.int8)
    w=cell_weights(d)
    digest=hashlib.sha256(X.tobytes()+w.tobytes())
    digest.update((Path(__file__).parent/"lib/irt.py").read_bytes())
    fingerprint=digest.hexdigest()
    path=cache/"irt13_model.json"
    model=json.loads(path.read_text()) if path.exists() else {}
    if model.get("fingerprint")!=fingerprint:
        print("Calibrating 13 common items across all 27 available country-cycle cells",flush=True)
        log=io.StringIO()
        with contextlib.redirect_stdout(log):
            A,B=irt.fit(X,w/w.sum()*len(d),max_iter=300)
        (cache/"irt13_fit.log").write_text(log.getvalue())
        trajectory=re.findall(r"iteration\s+(\d+): largest parameter change ([\d.]+)",log.getvalue())
        print(log.getvalue(),flush=True)
        if not trajectory or float(trajectory[-1][1])>=.001:
            raise RuntimeError("Four-cycle IRT did not converge; inspect irt13_fit.log")
        model={"fingerprint":fingerprint,"a":A.tolist(),"steps":[b.tolist() for b in B],
               "iterations":int(trajectory[-1][0])+1,"last_parameter_change":float(trajectory[-1][1]),
               "items":list(ITEMS),"min_items":8,"converged":True}
        write_json(path,model)
    else:
        A,B=np.array(model["a"]),[np.array(b) for b in model["steps"]]
    scores=irt.wle(X,A,B,min_items=8)
    assert np.isfinite(scores).sum()==((X>=0).sum(axis=1)>=8).sum()
    d["homepos_h4"]=zscore(scores,w)
    group=d.groupby(["cnt","wave"],sort=False).ngroup().to_numpy()
    d["escs_h4"],_,imputed=escs(np.column_stack([d.hisei,d.pared_c,scores]),group,w)
    d.to_parquet(cache/"analysis_four_cycles.parquet",index=False)
    parameters=pd.DataFrame({"item":list(ITEMS),"a":A,"steps":[json.dumps(b.tolist()) for b in B]})
    diagnostics={"country_cycle_cells":d.groupby(["cnt","wave"]).ngroups,"calibration_students":len(d),
                 "min_common_items":8,"irt_iterations":model["iterations"],"irt_converged":model["converged"],
                 "last_parameter_change":model["last_parameter_change"],"imputed_pct":imputed,
                 "parental_education_2015_mapping":{str(k):v for k,v in mapping.items()},
                 "computers_missing_rule":"None + unknown stays missing; any observed computer establishes presence"}
    return d,parameters,diagnostics


def estimates(d, year):
    levels, gaps, overall, coverage, checks, availability = [], [], [], [], [], []
    for cnt in COUNTRIES:
        g = d.loc[d.cnt == cnt]
        # The 2015 main PUF may omit ARG, although its value label is present.
        # The separately adjudicated QAR region must never replace national ARG.
        status = "not_comparable_sampling" if (cnt, year) == ("ARG", 2015) else "available" if len(g) else "absent_from_file"
        availability.append({"cnt": cnt, "wave": year, "n_raw": len(g), "included": status == "available",
                             "status": status, "source": ARGENTINA_SOURCE if status == "not_comparable_sampling" else ""})
        if status != "available":
            continue
        print(f"Estimating Q4-Q1 gaps and score levels: {cnt} {year}", flush=True)
        W = g[["w_fstuwt"] + [c.lower() for c in C.REPW]].to_numpy(float)
        P = g[PV].to_numpy(float)
        assert np.isfinite(W).all() and (W >= 0).all() and (W[:,0] > 0).all()
        assert (W.sum(axis=0) > 0).all()
        valid_pv = np.isfinite(P).all(axis=1)
        mean, se = brr.summarise(brr.theta_groups(np.zeros(valid_pv.sum(), dtype=int), W[valid_pv], P[valid_pv], 1))
        overall.append({"cnt": cnt, "wave": year, "n": int(valid_pv.sum()), "estimate": mean[0], "se": se[0],
                        "ci_low": mean[0]-1.96*se[0], "ci_high": mean[0]+1.96*se[0]})
        for idx in INDICES:
            mask = valid_pv & np.isfinite(g[idx].to_numpy(float))
            n = int(mask.sum())
            coverage.append({"cnt": cnt, "wave": year, "index": idx, "n_total": len(g), "n_valid": n,
                             "valid_weight_pct": 100*W[mask,0].sum()/W[:,0].sum()})
            if n < 200:
                continue
            x, weights, pvs = g[idx].to_numpy(float)[mask], W[mask], P[mask]
            theta = brr.theta_quartiles(x, weights, pvs)
            assert np.isfinite(theta).all()
            point, error = brr.summarise(theta)
            gap,gap_se=brr.contrast(theta,[-1,0,0,1])
            gaps.append({"cnt":cnt,"wave":year,"index":idx,"n":n,"estimate":gap,"se":gap_se,
                         "ci_low":gap-1.96*gap_se,"ci_high":gap+1.96*gap_se})
            np.testing.assert_allclose(gap,point[3]-point[0],atol=1e-10)
            codes = brr.quartile_codes(x, weights)
            shares = np.array([weights[codes == k,0].sum()/weights[:,0].sum() for k in range(4)])
            bound = weights[:,0].max()/weights[:,0].sum()
            assert np.max(np.abs(shares-.25)) <= bound+1e-10
            np.testing.assert_allclose(shares @ point, np.average(pvs.mean(axis=1), weights=weights[:,0]), atol=1e-9)
            for k in range(4):
                levels.append({"cnt": cnt, "wave": year, "index": idx, "quartile": f"Q{k+1}",
                               "n": int((codes == k).sum()), "estimate": point[k], "se": error[k],
                               "ci_low": point[k]-1.96*error[k], "ci_high": point[k]+1.96*error[k]})
                checks.append({"cnt": cnt, "wave": year, "index": idx, "quartile": f"Q{k+1}",
                               "n": int((codes == k).sum()), "weight_pct": shares[k]*100})
    return {"levels_math": levels, "gaps_math":gaps, "overall_math": overall, "coverage": coverage,
            "quartile_checks": checks, "availability": availability}


def validate(tables):
    levels = tables["levels_math"]
    gaps = tables["gaps_math"]
    expected = {(c,y) for c in COUNTRIES for y in YEARS if (c,y)!=("ARG",2015)}
    assert not levels.duplicated(["cnt", "wave", "index", "quartile"]).any()
    assert not ((levels.cnt == "ARG") & (levels.wave == 2015)).any()
    assert set(levels.cnt) == set(COUNTRIES)
    assert set(zip(levels.cnt,levels.wave)) == expected
    assert (levels.groupby(["cnt", "wave", "index"]).size() == 4).all()
    assert (levels.groupby(["cnt", "wave"])["index"].nunique() == len(INDICES)).all()
    assert np.isfinite(levels[["estimate", "se", "ci_low", "ci_high"]]).all().all()
    assert len(gaps) == len(expected)*len(INDICES)
    assert not gaps.duplicated(["cnt","wave","index"]).any()
    assert np.isfinite(gaps[["estimate","se","ci_low","ci_high"]]).all().all()
    assert (gaps.se > 0).all()
    q = levels.pivot(index=["cnt","wave","index"],columns="quartile",values="estimate")
    gap_check = gaps.set_index(["cnt","wave","index"]).reindex(q.index)
    np.testing.assert_allclose(gap_check.estimate,q.Q4-q.Q1,atol=1e-10,rtol=0)
    np.testing.assert_array_equal(gap_check.n,levels.groupby(["cnt","wave","index"]).n.sum().reindex(q.index))
    np.testing.assert_allclose(gaps.ci_low,gaps.estimate-1.96*gaps.se,atol=1e-10,rtol=0)
    np.testing.assert_allclose(gaps.ci_high,gaps.estimate+1.96*gaps.se,atol=1e-10,rtol=0)
    existing = pd.read_csv(C.RESULTS / "latam/tables/quartile_levels_math.csv")
    old_gaps = existing[existing["index"].isin(PUBLISHED) & (existing.group=="Q4-Q1")]
    matched_gaps = gaps.merge(old_gaps,on=["cnt","wave","index"],suffixes=("_history","_existing"))
    assert len(matched_gaps)==len(COUNTRIES)*2*2
    for column in ["estimate","se","ci_low","ci_high"]:
        np.testing.assert_allclose(matched_gaps[column+"_history"],matched_gaps[column+"_existing"],atol=1e-9,rtol=0)
    tables["latest_gap_validation"] = matched_gaps[["cnt","wave","index","estimate_history","estimate_existing","se_history","se_existing"]].copy()
    existing = existing[existing["index"].isin(PUBLISHED) & existing.group.isin(["Q1", "Q2", "Q3", "Q4"])]
    matched = levels.merge(existing.rename(columns={"group": "quartile"}), on=["cnt", "wave", "index", "quartile"], suffixes=("_history", "_existing"))
    for column in ["estimate", "se", "ci_low", "ci_high"]:
        np.testing.assert_allclose(matched[column+"_history"], matched[column+"_existing"], atol=1e-9, rtol=0)
    assert len(matched) == len(COUNTRIES)*2*2*4
    tables["latest_validation"] = matched[["cnt", "wave", "index", "quartile", "estimate_history", "estimate_existing", "se_history", "se_existing"]].copy()
    official = []
    for idx, sheet in [("escs", "Table I.B1.2b.24"), ("homepos", "Table I.B1.2b.38")]:
        x = pd.read_excel(C.ROOT / "reference/oecd_2025_equity.xlsx", sheet_name=sheet, header=None)
        names = x.iloc[:,0].astype(str).str.replace("*", "", regex=False).str.strip()
        for cnt in COUNTRIES:
            row = x.loc[names == ENGLISH[cnt]]
            assert len(row) == 1
            nums = pd.to_numeric(row.iloc[0,1:], errors="coerce").to_numpy()
            for j, year in enumerate(YEARS):
                for k in range(4):
                    found = levels[(levels.cnt == cnt) & (levels.wave == year) & (levels["index"] == idx) & (levels.quartile == f"Q{k+1}")]
                    if found.empty:
                        continue
                    for statistic, offset in [("estimate",0), ("se",1)]:
                        value = nums[j*10+k*2+offset]
                        computed = found.iloc[0][statistic]
                        official.append({"cnt":cnt, "wave":year, "index":idx, "quartile":f"Q{k+1}",
                                         "statistic":statistic, "computed":computed, "official":value,
                                         "difference":computed-value, "source_table":sheet})
    tables["official_comparison"] = pd.DataFrame(official)
    # Earlier workbook values can use retrospectively rescaled indices. They are
    # a reference check, not an equality target for original-cycle quartiles.
    comp = tables["official_comparison"]
    return {"all_checks_passed": True, "country_cycles": len(tables["overall_math"]),
            "level_rows":len(levels), "matched_recent_level_rows":len(matched),
            "recent_max_abs_estimate_difference":float(abs(matched.estimate_history-matched.estimate_existing).max()),
            "max_quartile_weight_deviation_pp":float(abs(tables["quartile_checks"].weight_pct-25).max()),
            "official_max_abs_estimate_difference_by_cycle": {
                str(y):float(comp.loc[(comp.wave == y) & (comp.statistic == "estimate"), "difference"].abs().max()) for y in YEARS},
            "gap_rows":len(tables["gaps_math"]), "no_between_cycle_change_statistics":True,
            "matched_recent_gap_rows":len(matched_gaps),
            "recent_gap_max_abs_se_difference":float(abs(matched_gaps.se_history-matched_gaps.se_existing).max()),
            "argentina_2015_excluded":True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    out = C.RESULTS / "latam/history"
    cache = C.INTERIM / "latam/history"
    for p in [out / "tables", cache]:
        p.mkdir(parents=True, exist_ok=True)
    outputs, sources, parts = {}, {}, {}
    for year in YEARS:
        d, info = extract(year, cache, args.refresh)
        sources[str(year)] = info
        parts[year]=d
    d,parameters,diagnostics=harmonize(parts,cache)
    for year in YEARS:
        for name, rows in estimates(d.loc[d.wave==year], year).items():
            outputs.setdefault(name, []).extend(rows)
    tables = {name:pd.DataFrame(rows) for name, rows in outputs.items()}
    tables["irt_parameters"]=parameters
    validation = validate(tables)
    levels = tables["levels_math"]
    tables["levels_wide_math"] = levels.pivot(index=["cnt","index","quartile"], columns="wave", values="estimate").reset_index()
    tables["gap_series_math"]=tables["gaps_math"].pivot(index=["cnt","index"],columns="wave",values="estimate").reset_index()
    for name, table in tables.items():
        table.to_csv(out / "tables" / f"{name}.csv", index=False)
    write_json(out / "validation.json", validation)
    write_json(out / "sources.json", {
        "generated_utc":datetime.now(timezone.utc).isoformat(), "countries":COUNTRIES, "cycles":YEARS,
        "indices":INDICES, "index_version":"Original published indices versus pooled four-cycle harmonization with 13 common items",
        "statistic":"Q4-Q1 mathematics gaps in each cycle, with quartile score levels as supporting data; no changes between cycles",
        "harmonization":diagnostics,
        "variance":"10 plausible values, 80 BRR replicates, Fay 0.5, quartiles recomputed in each replicate",
        "link_error":"Not added: linking location error cancels in within-cycle Q4-Q1 contrasts",
        "index_uncertainty":"Conditional on reconstructed indices; IRT and component imputation are not re-estimated in BRR replicates",
        "quartile_seed":C.SEED, "argentina_2015_exclusion_source":ARGENTINA_SOURCE,
        "raw_files":sources, "script_sha256":sha(__file__), "brr_sha256":sha(Path(__file__).parent / "lib/brr.py")})
    print(json.dumps(validation, indent=2), flush=True)
    print(f"Historical numerical tables saved to {out}; run 16_latam_reports.py to render languages and figures", flush=True)


if __name__ == "__main__":
    main()
