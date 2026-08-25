"""Fig.1 (combined) -- the as-of gap (left) and the pipeline that closes it (right).

PILOT2 MIGRATION.  The running example moved from the enterprise rma SKU536-EOL
case to the public card_games instance by author ruling (enterprise data is
motivation only; every number a figure carries must be recomputable from the
public base).  The structure of the float is unchanged -- problem on the left,
pipeline on the right -- and the new instance is strictly sharper: the metric is

    ruling_intensity = rulings issued in the month / new printings released
                       in the month              (BIRD card_games, 803,445 rows)

at T1 = 2016-11 both legs have mass (320/796 = 40.20%, CARD-Q2, certificate
ACCEPT); at T2 = 2017-02 a burst of 2,161 rulings arrives in a month with ZERO
set releases, so the same-window denominator has no mass and the governed
decision is REFUSE missing-caliber (MC(ii)) with the probe as witness (CARD-Q7,
certificate ACCEPT).  The blind row is OBSERVED, not constructed: the frozen
run cache shows 6/8 evaluated LLM arms answered at T2 -- the strongest
(governance-informed) arm assembled the right two legs and returned 2161/0 = "inf"
-- while at the benign T1 0/8 returned the governed value.

Style: figures/style.py is the single source of truth for colour semantics
(green = ours/correct-under-as-of-semantics, vermilion = answered-should-refuse
and the refusal lane, grey = governance-blind data).  Every colour-coded element
carries a redundant encoding (position, label text, glyph); no in-figure type
falls below 5.4 pt at print size.

Numbers come from figures/fig_data_pilot2.json (recomputed from the pilot2
warehouse, the frozen certificates and the frozen run cache by extract_p2.py --
run that first).
"""

import json
import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "fig_data_pilot2.json")))
R = D["running_example"]

MONTHS = R["months"]                                # 2016-11 .. 2017-04
SHORT = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
num = [R["rulings"][m] for m in MONTHS]
den = [R["printings"][m] for m in MONTHS]
i_t1 = MONTHS.index(R["t1"])
i_t2 = MONTHS.index(R["t2"])

SPAN = "#DCE6F0"
SPAN_INK = "#2B4C6F"
OURS_FILL = "#E6F4EF"
STORE_FILL = "#F4F1E8"
STORE_EDGE = "#B9A87A"
STORE_INK = "#5C5030"
STAGE_FILL = "#EEF3F8"
STAGE_EDGE = "#7F97AD"

FIG_W, FIG_H = S.FULL_W, 3.02
fig = plt.figure(figsize=(FIG_W, FIG_H))

# One overlay axes in figure coordinates for all hand-placed graphics.
ov = fig.add_axes([0, 0, 1, 1])
ov.set_xlim(0, 1)
ov.set_ylim(0, 1)
ov.axis("off")


def box(x, w, y, h, fill, edge, lw=0.7, r=0.010, z=2):
    ov.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0,rounding_size={r}",
                                facecolor=fill, edgecolor=edge, linewidth=lw,
                                zorder=z))


def arrow(x0, y0, x1, y1, color=S.INK, lw=0.8, ls="-", z=4):
    ov.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=6, color=color, lw=lw,
                                 linestyle=ls, zorder=z, shrinkA=0, shrinkB=0))


# =====================================================================
#  LEFT HALF -- the problem: one metric, one question, two as-of points
# =====================================================================
LX0, LX1 = 0.005, 0.393                       # left-half x band
ov.text((LX0 + LX1) / 2, 0.982,
        "(a) one governed question, two as-of points",
        ha="center", va="top", fontsize=6.8, color=S.INK, fontweight="bold")
ov.text((LX0 + LX1) / 2, 0.933,
        "“ruling_intensity of card_games, as of $T$?”",
        ha="center", va="top", fontsize=6.6, color=S.INK, style="italic")

# --- (a1) the governed facts, monthly ------------------------------------
AX_L, AX_W = 0.038, 0.340
for k, (vals, lab, col, ax_bottom) in enumerate((
        (num, "numerator: rulings @ rulings.date", S.INK, 0.742),
        (den, "denominator: new printings @ sets.releaseDate", S.GREY, 0.596))):
    ax = fig.add_axes([AX_L, ax_bottom, AX_W, 0.092])
    for x in (i_t1, i_t2):                      # the two as-of windows under test
        ax.axvspan(x - 0.47, x + 0.47, color=SPAN, zorder=0)
    ax.bar(range(len(MONTHS)), vals, width=0.52, color=col,
           edgecolor=S.INK, linewidth=0.5, zorder=3)
    for x, v in enumerate(vals):
        if v:
            ax.annotate(f"{v:,}", (x, v), ha="center", va="bottom", fontsize=5.8,
                        xytext=(0, 1.0), textcoords="offset points")
    ax.set_ylim(0, max(vals) * 2.60)
    ax.set_xlim(-0.70, len(MONTHS) - 0.30)
    ax.set_title(lab, loc="left", fontsize=5.9, color=S.INK, pad=1.6)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    if k == 0:
        ax.tick_params(labelbottom=False)
        for x, tag in ((i_t1, "$T_1$"), (i_t2, "$T_2$")):
            ax.text(x, max(vals) * 2.55, tag, ha="center", va="top",
                    fontsize=6.8, color=SPAN_INK)
    else:
        ax.set_xticks(range(len(MONTHS)))
        ax.set_xticklabels(SHORT, fontsize=6.2)
        ax.annotate("no set released in 2017-02;\nrulings still arrive",
                    (i_t2 - 0.08, 70), xytext=(0.98, max(den) * 2.02),
                    fontsize=5.7, color=S.INK, va="center", ha="left",
                    arrowprops=dict(arrowstyle="->", lw=0.6, color=S.INK,
                                    connectionstyle="arc3,rad=0.22"))

# --- (a2) the same question at T1 and T2, governed vs observed ------------
XL, XA, XB = LX0 + 0.006, 0.236, 0.342          # label col, T1 col, T2 col
HDR, R1, WIT, R2, FOOT = 0.520, 0.428, 0.328, 0.240, 0.100

ov.text(XA, HDR, f"$T_1$ = {R['t1']}", ha="center", va="center",
        fontsize=6.4, color=SPAN_INK)
ov.text(XB, HDR, f"$T_2$ = {R['t2']}", ha="center", va="center",
        fontsize=6.4, color=SPAN_INK)
ov.plot([XL, LX1], [HDR - 0.035] * 2, lw=0.6, color=S.INK, zorder=3)

t1_rate = R["t1_rate"]

# row 1 -- correct under the as-of semantics this paper defines (GREEN)
ov.add_patch(Rectangle((XL - 0.004, WIT - 0.052), LX1 - XL + 0.006,
                       R1 - WIT + 0.104, facecolor=OURS_FILL, edgecolor="none",
                       zorder=0))
ov.text(XL, R1, "correct under\nas-of semantics", ha="left", va="center",
        fontsize=6.1, color=S.GREEN, linespacing=1.05, zorder=3)
ov.text(XA, R1, f"{100*t1_rate:.2f}%", ha="center", va="center", fontsize=7.6,
        color=S.GREEN, fontweight="bold", zorder=3)
ov.text(XA, R1 - 0.048, f"{R['t1_num']}/{R['t1_den']}", ha="center",
        va="center", fontsize=5.9, color="#3C6E5E", zorder=3)
ov.text(XB, R1, "REFUSE", ha="center", va="center", fontsize=7.6,
        color=S.GREEN, fontweight="bold", zorder=3)
ov.text(XB, R1 - 0.048, "missing-caliber", ha="center", va="center",
        fontsize=5.9, color="#3C6E5E", zorder=3)
ov.text(0.316, WIT, f"witness ({R['t2_num']:,}, {R['t2_den']}):\n"
        "no same-window denominator", ha="center", va="center", fontsize=5.4,
        color="#3C6E5E", linespacing=1.10, zorder=3)

# row 2 -- what the evaluated LLM arms actually returned (frozen run cache)
ov.text(XL, R2, "evaluated LLM arms\n(frozen runs)", ha="left", va="center",
        fontsize=6.1, color=S.VERMILION, linespacing=1.05)
ov.text(XA, R2, f"{R['n_correct_at_t1']}/{R['n_llm']}", ha="center",
        va="center", fontsize=7.6, color=S.VERMILION, fontweight="bold")
ov.text(XA, R2 - 0.048, "returned 40.20%", ha="center", va="center",
        fontsize=5.9, color=S.VERMILION)
ov.text(XB, R2, f"{R['n_answered_at_t2']}/{R['n_llm']}", ha="center",
        va="center", fontsize=7.6, color=S.VERMILION, fontweight="bold")
ov.text(XB, R2 - 0.048, "answered anyway", ha="center", va="center",
        fontsize=5.9, color=S.VERMILION)
for x in (XA + 0.050, XB + 0.050):
    ov.text(x, R2, "✗", ha="center", va="center", fontsize=7.8,
            color=S.VERMILION)

ov.text((LX0 + LX1) / 2, FOOT,
        f"at $T_2$ the governed answer is not a number at all —\n"
        f"yet {R['n_answered_at_t2']}/{R['n_llm']} evaluated LLM arms answered; "
        "the strongest\n(governance-informed) arm computed "
        f"{R['t2_num']:,}/0 and returned “inf”;\nat the benign $T_1$, "
        f"{R['n_correct_at_t1']}/{R['n_llm']} arms returned the governed 40.20%",
        ha="center", va="center", fontsize=5.5, color=S.INK, linespacing=1.22)

# separator between the two halves
ov.plot([0.412, 0.412], [0.115, 0.975], lw=0.6, color="#CCCCCC", zorder=1)

# =====================================================================
#  RIGHT HALF -- the pipeline: question -> binding -> gate -> certificate
# =====================================================================
RX0, RX1 = 0.430, 0.995
ov.text((RX0 + RX1) / 2, 0.982,
        "(b) the compile-time pipeline, traced on the same question",
        ha="center", va="top", fontsize=6.8, color=S.INK, fontweight="bold")

SPLIT = 0.735                                   # stage text | example trace
STAGES = [
    ("①", "question", "§2.1", False,
     "$\\langle q,T\\rangle$: metric, scope, one window per metric\n"
     "role, optionally a declared anchor $\\bar a$",
     "CARD-Q7: ruling_intensity, $T$=2017-02-15"),
    ("②", "binding compilation", "§2–3", True,
     "pin $\\nu=\\mathrm{ver}(T)$ (off-diagonal reads carry a mark);\n"
     "derive $\\alpha$, caliber routing $\\rho$; guards OOV$\\to$AM$\\to$MC",
     "$\\nu$=(card_games, v1)\n"
     "$\\alpha$(num)=(rulings.date, Feb)\n"
     "$\\alpha$(den)=(sets.releaseDate, Feb)\n"
     "probe $\\mu_{den}$=0 $\\Rightarrow$ MC(ii) fires"),
    ("③", "disclosure gate", "§4", True,
     "maximal legal rewriting: grain frontier $U_{\\min}$,\n"
     "mask closure $\\mu^{*}$; empty frontier $\\Rightarrow$ DB",
     "not reached: a binding guard fired first"),
    ("④", "decision + certificate", "§5", True,
     "ANSWER | REWRITE($q'$) | REFUSE($r$), with\n"
     "$C=(q,T,\\langle\\alpha,\\nu,\\rho,\\delta\\rangle,\\mathrm{out})$; refusals carry a witness",
     "REFUSE MC(ii), witness (2,161, 0)\n"
     "@sibling $T_1$=2016-11: ANSWER 40.20%"),
    ("⑤", "independent verifier", "§5–6", True,
     "$\\mathsf{Chk}(C,G_v,D,\\mathrm{ctx})\\to$ ACCEPT | REJECT; every claim\n"
     "re-derived from $(G_v,D)$; zero modules shared with ①–④",
     "ACCEPT (probe re-run on $D$: 0 rows)"),
]

TOP, BOTM = 0.905, 0.150
ROW_H = 0.132
gap = ((TOP - BOTM) - len(STAGES) * ROW_H) / (len(STAGES) - 1)
for i, (cnum, title, sec, ours, body, trace) in enumerate(STAGES):
    y = TOP - ROW_H - i * (ROW_H + gap)
    box(RX0, RX1 - RX0, y, ROW_H, OURS_FILL if ours else STAGE_FILL,
        S.GREEN if ours else STAGE_EDGE, lw=0.9 if ours else 0.7)
    ov.text(RX0 + 0.006, y + ROW_H - 0.014, cnum, fontsize=7.0, va="top",
            ha="left", color=S.GREEN if ours else STAGE_EDGE, zorder=5)
    ov.text(RX0 + 0.023, y + ROW_H - 0.016, title, fontsize=6.6, va="top",
            ha="left", color=S.INK, fontweight="bold", zorder=5)
    ov.text(SPLIT - 0.008, y + ROW_H - 0.016, sec, fontsize=6.0, va="top",
            ha="right", color=S.GREEN if ours else STAGE_EDGE, zorder=5)
    ov.text(RX0 + 0.006, y + ROW_H - 0.058, body, fontsize=5.8, va="top",
            ha="left", color=S.INK, linespacing=1.28, zorder=5)
    ov.plot([SPLIT, SPLIT], [y + 0.006, y + ROW_H - 0.006], lw=0.5,
            color="#C8D4DE", zorder=5)
    lane_col = S.GREEN if trace.startswith("ACCEPT") else S.VERMILION
    for j, line in enumerate(trace.split("\n")):
        col = S.GREEN if line.startswith("@sibling") else lane_col
        ov.text(SPLIT + 0.008, y + ROW_H - 0.028 - j * 0.026,
                line.replace("@sibling", "sibling"), fontsize=5.6, va="top",
                ha="left", color=col, zorder=5,
                fontweight="bold" if i >= 3 else "normal")
    if i < len(STAGES) - 1:
        arrow((RX0 + SPLIT) / 2, y - 0.004, (RX0 + SPLIT) / 2,
              y - gap + 0.004)

ov.text(SPLIT + 0.008, TOP + 0.012, "running example (panel a), traced:",
        fontsize=5.9, va="bottom", ha="left", color=S.INK, style="italic")

# --- the versioned governed store, feeding both halves -------------------
SBY, SBH = 0.014, 0.088
box(RX0, RX1 - RX0, SBY, SBH, STORE_FILL, STORE_EDGE, lw=0.7)
ov.text((RX0 + RX1) / 2, SBY + SBH / 2,
        "versioned governed semantic layer $G_v$: anchors $A_v$, bindings "
        "$\\beta_v$, caliber routing $R_v$,\ndisclosure policies $\\mathcal{D}$"
        "   +   warehouse $D$ (9 public DBs, 3.83M real rows)",
        fontsize=5.8, va="center", ha="center", color=STORE_INK, zorder=5,
        linespacing=1.30)
for x in (0.53, 0.72, 0.90):
    arrow(x, SBY + SBH + 0.002, x, SBY + SBH + 0.048, lw=0.7, ls=(0, (2.2, 1.6)),
          color="#8C7B4E")

out = os.path.join(HERE, "fig1_combined.pdf")
fig.savefig(out, metadata={"CreationDate": None})  # byte-reproducible re-runs
print("wrote", out)
print(f"  T1 {R['t1_num']}/{R['t1_den']}={100*t1_rate:.2f}%  "
      f"({R['n_correct_at_t1']}/{R['n_llm']} LLM arms correct: {R['t1_qid']})")
print(f"  T2 gold=REFUSE {R['t2_gold_refusal']} ({R['t2_num']},{R['t2_den']})  "
      f"{R['n_answered_at_t2']}/{R['n_llm']} answered ({R['t2_qid']}); "
      f"gov arm returned {R['gov_arm_t2_value']}")
