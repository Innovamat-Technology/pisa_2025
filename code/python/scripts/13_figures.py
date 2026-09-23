"""Step 13. Figures, from the tables written by the previous steps.

Paper style: no titles or notes inside the image (they go in the caption of the manuscript), built at the width of
the text block so the font sizes are the printed ones, vector PDF with editable text plus a 300 dpi PNG.

One color per version of the indices across every figure: blue for the indices as published by the OECD, orange
for the harmonized ones. The line style tells the index apart: solid for ESCS, dashed for HOMEPOS. HISEI and PARED,
which have no published counterpart, are gray. Uncertainty is shown as 95% error bars (1.96 s.e.).
Mean-change intervals include the OECD link error; gap intervals exclude the canceling component.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

from lib import config as C

# The paper is typeset in Source Sans (innovamat-paper.cls, simfonts); the TTFs travel with the repo.
for _f in (C.ROOT / "assets" / "fonts").glob("SourceSans3-*.ttf"):
    font_manager.fontManager.addfont(str(_f))

plt.rcParams.update({
    "pdf.fonttype": 42, "svg.fonttype": "none",  # text stays text in the exported file
    "font.family": "sans-serif", "font.sans-serif": ["Source Sans 3", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.linewidth": .8, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "text.color": "black", "axes.labelcolor": "black", "axes.edgecolor": "black",
    "xtick.color": "black", "ytick.color": "black",
})
W = 5.5  # inches, the width of the text block of the paper
INK, GREY, GREY_TEXT = "black", "#9a9a9a", "#707070"
PUB, HAR = "#2b5c8a", "#C0370C"  # published index (OECD): blue; harmonized index: orange
COL = {"escs": PUB, "homepos": PUB, "escs_h": HAR, "homepos_h": HAR, "hisei_h": GREY, "pared_h": GREY}
LS = {"escs": "-", "homepos": (0, (4, 2)), "hisei": "-", "pared": (0, (1, 1.5))}  # by index, whatever the version
NAME = {"escs": "ESCS", "escs_h": "ESCS", "homepos": "HOMEPOS", "homepos_h": "HOMEPOS", "hisei_h": "HISEI",
        "pared_h": "PARED"}
VERSION = {PUB: "Published index (OECD)", HAR: "Harmonized index (this paper)"}
EB = dict(elinewidth=.7, capsize=1.8, capthick=.7)  # error-bar style shared by every figure


def style(idx):
    """Line and marker style of an index: color by version, line style by index, gray for the single components."""
    col, ls = COL[idx], LS[idx.replace("_h", "")]
    if col == GREY:
        return dict(color=col, lw=1.0, ls=ls, marker="o", ms=2.8, mfc=col, mec=col, mew=1.2, zorder=3)
    return dict(color=col, lw=1.8, ls=ls, marker="o", ms=4, mfc=col, mec=col, mew=1.2, zorder=5 if col == HAR else 4)


def label(ax, idx, xy):
    """Direct label at the right end of a line: the name of the index, in the color of the line."""
    grey = COL[idx] == GREY
    ax.annotate(NAME[idx], xy, xytext=(6, 0), textcoords="offset points", va="center",
                color=GREY_TEXT if grey else COL[idx], fontsize=7.5 if grey else 8)


def version_handles(ls="-"):
    """Legend entries for the two versions of the indices."""
    return [plt.Line2D([], [], color=c, ls=ls, lw=1.8, marker="o", ms=3.5, label=VERSION[c]) for c in (PUB, HAR)]


def version_legend(ax, y=.2, **kw):
    """Legend of versions inside the axes, at height `y` (fraction of the axes) on the left."""
    ax.legend(handles=version_handles(), loc="center left", bbox_to_anchor=(0, y), fontsize=9.5, handlelength=1.6,
              **kw)


def tidy(ax, axis="y"):
    ax.grid(axis=axis, color="#ededed", lw=.6, zorder=0)


def spread(values, gap):
    """Label positions: the values, pushed apart so that consecutive labels are at least `gap` apart."""
    order = np.argsort(values)
    pos = np.array(values, dtype=float)[order]
    for i in range(1, len(pos)):
        pos[i] = max(pos[i], pos[i - 1] + gap)
    pos -= (pos.mean() - np.mean(values))
    out = np.empty(len(values)); out[order] = pos
    return out


def save(fig, name):
    fig.savefig(C.FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(C.FIGURES / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


o = pd.read_csv(C.TABLES / "quartiles_math.csv")
o = o[o.cnt == "OECD"].set_index("index")

# Quartile profiles ---------------------------------------------------------------------------------
SER = ["homepos_h", "homepos", "escs_h", "escs", "hisei_h", "pared_h"]
for dom, dname in (("math", "mathematics"), ("scie", "science"), ("read", "reading")):
    q = pd.read_csv(C.TABLES / f"quartiles_{dom}.csv")
    q = q[q.cnt == "OECD"].set_index("index")
    fig, ax = plt.subplots(figsize=(W, 3.5))
    ends = [q.loc[idx, "Q4_change"] for idx in SER]
    for idx, ylab in zip(SER, spread(ends, 2.4)):
        v = np.array([q.loc[idx, f"Q{i}_change"] for i in range(1, 5)])
        e = 1.96 * np.array([q.loc[idx, f"Q{i}_se"] for i in range(1, 5)])
        ax.errorbar(range(4), v, yerr=e, **style(idx), **EB)
        label(ax, idx, (3, ylab))
    ax.axhline(0, color=INK, lw=.9, zorder=2)
    vals = q.loc[SER, [f"Q{k}_change" for k in range(1, 5)]].to_numpy()
    errors = 1.96 * q.loc[SER, [f"Q{k}_se" for k in range(1, 5)]].to_numpy()
    lo = np.floor(min(vals.min() - 4, (vals - errors).min() - 1) / 5) * 5
    hi = np.ceil(max(vals.max() + 4, (vals + errors).max() + 1) / 5) * 5
    ax.set_xticks(range(4)); ax.set_xticklabels([f"Q{i}" for i in range(1, 5)])
    ax.set_xlim(-.25, 3.8); ax.set_ylim(lo, hi)
    ax.set_xlabel("Quartile of the index")
    ax.set_ylabel(f"Change in {dname}, 2022–2025 (score points)")
    version_legend(ax)
    tidy(ax); fig.tight_layout(); save(fig, f"fig_quartile_profiles_{dom}")

# Six pairwise differences ----------------------------------------------------------------------------
P = ["Q2-Q1", "Q3-Q1", "Q3-Q2", "Q4-Q1", "Q4-Q2", "Q4-Q3"]
SER = ["escs", "escs_h", "homepos_h", "pared_h"]
x, wd = np.arange(len(P)), .2
fig, ax = plt.subplots(figsize=(W, 3.2))
for i, idx in enumerate(SER):
    v = [o.loc[idx, f"{p}_change"] for p in P]
    e = [1.96 * o.loc[idx, f"{p}_se"] for p in P]
    ax.bar(x + (i - 1.5) * wd, v, wd * .88, color=COL[idx], hatch="///" if idx.startswith("homepos") else None,
           edgecolor="white", lw=0, label=NAME[idx] + {PUB: ", published (OECD)", HAR: ", harmonized (this paper)", GREY: ""}[COL[idx]],
           zorder=3)
    ax.errorbar(x + (i - 1.5) * wd, v, yerr=e, fmt="none", ecolor=INK, zorder=4, **EB)
ax.axvline(2.5, color="#cccccc", lw=.8, ls=":", zorder=1)
ax.text(1.0, 16.5, "Not involving Q4", ha="center", fontsize=8)
ax.text(4.5, 16.5, "Involving Q4", ha="center", fontsize=8)
ax.axhline(0, color=INK, lw=.8)
ax.set_xticks(x); ax.set_xticklabels([p.replace("-", " − ") for p in P]); ax.set_ylim(-23, 19)
ax.set_ylabel("Change in the difference, 2022–2025 (score points)")
ax.set_xlabel("Difference between quartiles")
ax.legend(ncol=2, loc="lower left")
tidy(ax); fig.tight_layout(); save(fig, "fig_pairwise_differences")

# Gap series 2015-2025, published versus harmonized ---------------------------------------------------
for dom, dname in (("math", "mathematics"), ("scie", "science"), ("read", "reading")):
    s = pd.read_csv(C.TABLES / f"gap_series_{dom}.csv").set_index("index")
    yrs = [int(c[1:]) for c in s.columns if c.startswith("y")]
    fig, ax = plt.subplots(figsize=(W, 3.3))
    for row, idx in (("escs", "escs"), ("escs_h4", "escs_h"), ("homepos", "homepos"), ("homepos_h4", "homepos_h")):
        v = np.array([s.loc[row, f"y{y}"] for y in yrs])
        e = 1.96 * np.array([s.loc[row, f"se{y}"] for y in yrs])
        ax.errorbar(yrs, v, yerr=e, **style(idx), **EB)
        label(ax, idx, (yrs[-1], v[-1]))
    ax.set_xticks(yrs); ax.set_xlim(yrs[0] - .6, 2027.8)
    lo, hi = ax.get_ylim(); ax.set_ylim(lo, hi + .14 * (hi - lo))  # room for the legend above the lines
    ax.set_ylabel(f"Q4 − Q1 gap in {dname} (score points)")
    ax.legend(handles=version_handles(), loc="upper left", ncol=2, fontsize=9.5, handlelength=1.6)
    tidy(ax); fig.tight_layout(); save(fig, f"fig_gap_series_{dom}")

# Item correlations with achievement, by item status ---------------------------------------------------
GRP = {"2022 only": ("Dropped in 2025", PUB, 0), "common": ("Common to both cycles", HAR, 1),
       "2025 only": ("New in 2025", GREY, 2)}
GRP_TEXT = {g: (GREY_TEXT if c == GREY else c) for g, (_, c, _) in GRP.items()}
for dom, dname in (("math", "mathematics"), ("scie", "science")):
    t = pd.read_csv(C.TABLES / f"items_validation_{dom}.csv")
    t = t[(t.wave == 2022) | (t.group == "2025 only")].copy()
    t["order"] = t.group.map(lambda g: GRP[g][2])
    t = t.sort_values(["order", "r_score"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(W, 7.0))
    y = np.arange(len(t))
    ax.barh(y, t.r_score, color=[GRP[g][1] for g in t.group], height=.72, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels(t.label, fontsize=7)
    ax.axvline(0, color=INK, lw=.8)
    for g, (name, col, _) in GRP.items():
        m = (t.group == g).to_numpy()
        ax.text(0.46, y[m].mean(), f"{name}\nMean r = {t.r_score[m].mean():.2f}", color=GRP_TEXT[g], fontsize=8,
                va="center", ha="left")
        ax.axhline(y[m].max() + .5, color="#dddddd", lw=.6)
    ax.set_xlim(-0.12, 0.66); ax.set_ylim(-.7, len(t) - .3)
    ax.set_xlabel(f"Correlation with {dname}")
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False); ax.grid(axis="x", color="#ededed", lw=.6, zorder=0)
    fig.tight_layout(); save(fig, f"fig_item_correlations_{dom}")

# Item content: social origin (x) against achievement net of social origin (y) ----------------------
t = pd.read_csv(C.TABLES / "items_validation_math.csv")
t = t[(t.wave == 2022) | (t.group == "2025 only")]
OFF = {"Televisions": (0, 5, "center"), "Mopeds/motorcycles": (-3, -14, "left"), "Own tablet": (10, -12, "left"),
       "Swimming pool/jacuzzi": (4, -7, "left"), "Domestic workers": (4, -2, "left"),
       "Screen devices (number)": (-4, 2, "right")}  # label offsets (points) where the default would overlap
fig, ax = plt.subplots(figsize=(W, 3.9))
for g, (name, col, _) in GRP.items():
    x = t[t.group == g]
    ax.scatter(x.r_hisei, x.partial_r, s=16, color=col, label=name, zorder=3)
    for _, r in x.iterrows():
        if abs(r.partial_r) > .17 or r.r_hisei > .27 or r.partial_r < -.05:
            dx, dy, ha = OFF.get(r.label, (4, 2, "left"))
            ax.annotate(r.label, (r.r_hisei, r.partial_r), xytext=(dx, dy), textcoords="offset points", fontsize=6.5,
                        color=GRP_TEXT[g], ha=ha)
ax.axhline(0, color=INK, lw=.8); ax.axvline(0, color=INK, lw=.8)
ax.set_ylim(-.135, .38)
ax.set_xlabel("Correlation with parental occupation (HISEI)")
ax.set_ylabel("Partial correlation with mathematics")
ax.legend(loc="upper left", bbox_to_anchor=(.14, 1))
tidy(ax, "both"); fig.tight_layout(); save(fig, "fig_item_content")

# Decile profile -------------------------------------------------------------------------------------------
dec = pd.read_csv(C.TABLES / "deciles_math.csv")
fig, ax = plt.subplots(figsize=(W, 3.1))
for idx in ("escs", "escs_h"):
    x = dec[(dec["index"] == idx) & (dec.decile != "D10-D1")]
    d = x.decile.astype(int)
    ax.errorbar(d, x.change, yerr=1.96 * x.se, **style(idx), **EB)
ax.axhline(0, color=INK, lw=.9, zorder=2); ax.set_xticks(range(1, 11)); ax.set_xticklabels([f"D{i}" for i in range(1, 11)])
ax.set_xlabel("Decile of the index")
ax.set_ylabel("Change in mathematics, 2022–2025 (score points)")
version_legend(ax)
tidy(ax); fig.tight_layout(); save(fig, "fig_decile_profile")

# Quartile profile by system ---------------------------------------------------------------------------------
for dom, dname in (("math", "mathematics"), ("scie", "science"), ("read", "reading")):
    q = pd.read_csv(C.TABLES / f"quartiles_{dom}.csv")
    q = q[q.cnt != "OECD"]
    pub, har = q[q["index"] == "escs"].set_index("cnt"), q[q["index"] == "escs_h"].set_index("cnt")
    order = pub["Q4-Q1_change"].sort_values().index
    fig, axes = plt.subplots(6, 6, figsize=(W, 5.7), sharex=True, sharey=True)
    for ax, cnt in zip(axes.ravel(), order):
        for tab, idx in ((pub, "escs"), (har, "escs_h")):
            s = style(idx)
            ax.plot(range(4), [tab.loc[cnt, f"Q{k}_change"] for k in range(1, 5)], "-o", color=s["color"], lw=1.1,
                    ms=2.2, zorder=s["zorder"])
        ax.axhline(0, color=INK, lw=.5)
        ax.set_title(cnt, fontsize=7, loc="left", pad=2)
        ax.set_xticks(range(4)); ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4"], fontsize=6)
        ax.tick_params(axis="y", labelsize=6); ax.tick_params(length=2)
        tidy(ax)
    fig.supylabel(f"Change in {dname}, 2022–2025 (score points)", fontsize=8.5)
    fig.legend(handles=version_handles(), ncol=2, loc="upper center")
    fig.tight_layout(rect=(0, 0, 1, .96), h_pad=.6, w_pad=.4); save(fig, f"fig_systems_{dom}")

print("figures written to", C.FIGURES)
