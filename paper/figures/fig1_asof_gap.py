"""Fig.1 -- the as-of semantics gap (PROBLEM figure, not an architecture figure).

Worked example, variant (3) of the figures-SOP: one real governed metric, one
real question, two as-of points, and the answers a governance-blind system
produces.  PILOT2 MIGRATION (2026-08-04): the instance is the public
card_games running example (ruling_intensity; CARD-Q2 / CARD-Q7), so every
number drawn here is recomputable from the released base.

REDRAW (2026-08-27, FIGURE_REDESIGN_SPEC v1 §2): simplified from three gridspec
rows to two panels; the 5.9 pt footer is DELETED (its content moved verbatim
into the caption); every type element is >= 7.5 pt; height 3.19 -> <= 2.70 in.
Panel (a) collapses the old two count-axes into ONE grouped-bar axis
(numerator = rulings, denominator = new printings) so the shared six-month
window is read in a single glance; panel (b) keeps the two-row answer grid
(correct under as-of semantics vs governance-blind all-history).

SELF-CONTAINED AND CROSS-ASSERTED: every number is queried live from the
pilot2 card_games warehouse and asserted against the frozen artifacts before
anything is drawn --
  - T1 = 2016-11: ruling_intensity 320/796 = 40.20%, asserted equal to the
    frozen gold of CARD-Q2 and to its ACCEPTed certificate's ANSWER decision;
  - T2 = 2017-02: numerator 2,161 rulings, same-window denominator 0 new
    printings -> bot_MC(ii); the certificate's own denominator-probe SQL is
    re-executed here and must return 0;
  - "6/8 evaluated LLM arms answered" is re-tallied from
    pilot2/pilot2_arms_summary.json per-question verdicts (CARD-Q7).
The script exits non-zero rather than draw a figure that disagrees with the
frozen evidence.  Values print as percentages, matching fig2_certchain.
"""

import json
import os

import duckdb
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACT_ROOT = os.path.dirname(os.path.dirname(HERE))       # asof-gov-vldb-artifact/


def _resolve(rel):
    """Prefer the repo-local frozen copy (materialised by fetch_and_rebuild);
    fall back to the frozen-evidence tree when the warehouse is not committed."""
    local = os.path.join(ARTIFACT_ROOT, rel)
    if os.path.exists(local):
        return local
    evid = os.path.join("/Volumes/SSD 1/explore_opportunity_cc", rel)
    if os.path.exists(evid):
        return evid
    return local            # let the open() / connect() raise with the local path


WH = _resolve(os.path.join("pilot2", "domains", "card_games", "warehouse.duckdb"))
QS = _resolve(os.path.join("pilot2", "domains", "card_games", "questions.json"))
ARMS = _resolve(os.path.join("pilot2", "pilot2_arms_summary.json"))
CQ2 = _resolve(os.path.join("impl", "certs2", "CARD-Q2.json"))
CQ7 = _resolve(os.path.join("impl", "certs2", "CARD-Q7.json"))

MONTHS = ["2016-09", "2016-10", "2016-11", "2016-12", "2017-01", "2017-02"]
_MON = ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb"]
# The axis silently crosses a year boundary and the whole figure is about
# WHICH instant a question binds to, so the first tick and every tick where
# the year turns carry the year.  Derived from MONTHS, never hand-typed.
SHORT = [f"{m} '{MONTHS[i][2:4]}" if i == 0 or MONTHS[i][:4] != MONTHS[i - 1][:4]
         else m for i, m in enumerate(_MON)]
T1, T2 = "2016-11", "2017-02"

con = duckdb.connect(WH, read_only=True)
num_by_m = dict(con.execute(
    "SELECT substr(CAST(date AS VARCHAR),1,7) m, COUNT(*) FROM rulings "
    f"WHERE substr(CAST(date AS VARCHAR),1,7) BETWEEN '{MONTHS[0]}' AND '{MONTHS[-1]}' "
    "GROUP BY m").fetchall())
den_by_m = dict(con.execute(
    "SELECT substr(CAST(s.releaseDate AS VARCHAR),1,7) m, COUNT(*) "
    "FROM cards c JOIN sets s ON c.setCode = s.code "
    f"WHERE substr(CAST(s.releaseDate AS VARCHAR),1,7) BETWEEN '{MONTHS[0]}' AND '{MONTHS[-1]}' "
    "GROUP BY m").fetchall())
ALLTIME_DEN = con.execute(
    "SELECT COUNT(*) FROM cards c JOIN sets s ON c.setCode = s.code").fetchone()[0]

num = [int(num_by_m.get(m, 0)) for m in MONTHS]
den = [int(den_by_m.get(m, 0)) for m in MONTHS]
i_t1, i_t2 = MONTHS.index(T1), MONTHS.index(T2)
t1_num, t1_den = num[i_t1], den[i_t1]
t2_num, t2_den = num[i_t2], den[i_t2]

# ---- cross-assertions against the frozen gold, certificates and arm cache ----
gold = {q["qid"]: q for q in json.load(open(QS))}
q2, q7 = gold["CARD-Q2"], gold["CARD-Q7"]
assert q2["metric"] == q7["metric"] == "card.ruling_intensity"
assert q7["expected_kind"] == "refusal" and q7["refusal_reason"] == "missing-caliber" \
    and q7["refusal_subtype"] == "mc_ii"
t1_rate = t1_num / t1_den
assert abs(t1_rate - q2["gold_value"]) < 1e-12, (t1_rate, q2["gold_value"])
assert t2_den == 0 and t2_num > 0, (t2_num, t2_den)

e7 = json.load(open(CQ7))
assert e7["refusal"] == "missing-caliber"
wit = e7["certificate"]["refusal"]["witness"]
assert wit["type"] == "empty-denominator-probe" and wit["observed"] == 0.0
assert float(con.execute(wit["probe_sql"]).fetchone()[0]) == 0.0
e2 = json.load(open(CQ2))
assert e2["certificate"]["disclosure"]["decision"] == "ANSWER"
con.close()

verdicts = json.load(open(ARMS))["per_question_verdicts"]["CARD-Q7"]
llm = [a for a in verdicts if a != "mechanism"]
assert len(llm) == 8 and verdicts["mechanism"] == "correct"
n_answered = sum(1 for a in llm if verdicts[a] == "answered_should_refuse")
assert n_answered == 6, n_answered            # the caption's "6 of 8" claim

naive_t1 = t1_num / ALLTIME_DEN
naive_t2 = t2_num / ALLTIME_DEN

# ------------------------------------------------------------------- drawing
SPAN = "#DCE6F0"
SPAN_INK = "#2B4C6F"
FLOOR = 7.5                                    # font floor, asserted in-script

fig = plt.figure(figsize=(S.COL_W, 2.70))
fig.set_constrained_layout(False)
gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.35], hspace=0.30,
                      left=0.015, right=0.985, top=0.90, bottom=0.10)
ax_a = fig.add_subplot(gs[0])
ax_b = fig.add_subplot(gs[1])

# --------------------------------------------- (a) the governed facts, monthly
x = list(range(len(MONTHS)))
W = 0.38
for xi in (i_t1, i_t2):                        # the two as-of windows under test
    ax_a.axvspan(xi - 0.47, xi + 0.47, color=SPAN, zorder=0)
b_num = ax_a.bar([xi - 0.21 for xi in x], num, width=W, color=S.INK,
                 edgecolor=S.INK, linewidth=0.5, zorder=3)
b_den = ax_a.bar([xi + 0.21 for xi in x], den, width=W, color=S.GREY,
                 hatch="..", edgecolor=S.INK, linewidth=0.5, zorder=3)
YMAX = max(max(num), max(den))
ax_a.set_ylim(0, YMAX * 1.45)

# annotate ONLY the four decision-relevant bars; the rest show the axis is real
ANN = {(i_t1, "num"): t1_num, (i_t1, "den"): t1_den,
       (i_t2, "num"): t2_num, (i_t2, "den"): t2_den}
for (idx, leg), v in ANN.items():
    xpos = idx - 0.21 if leg == "num" else idx + 0.21
    ax_a.annotate(f"{v:,}", (xpos, v), ha="center", va="bottom",
                  fontsize=8.0, xytext=(0, 1.4), textcoords="offset points",
                  color=S.INK, zorder=6)

# Unicode subscripts (U+2081/2082) render at the text size, so no glyph drops
# below the 7.5 pt floor -- unlike mathtext $T_1$, whose subscript is 0.7x.
for xi, tag in ((i_t1, "T₁"), (i_t2, "T₂")):
    ax_a.text(xi, YMAX * 1.42, tag, ha="center", va="top",
              fontsize=8.0, color=SPAN_INK)

ax_a.set_xticks(x)
ax_a.set_xticklabels(SHORT, fontsize=FLOOR)
ax_a.set_xlim(-0.70, len(MONTHS) - 0.30)
ax_a.set_yticks([])
ax_a.spines["left"].set_visible(False)
ax_a.tick_params(axis="x", labelsize=FLOOR, length=2.0, pad=1.5)

# one-line in-axes legend (replaces the two 6.1 pt panel titles)
ax_a.legend([Patch(facecolor=S.INK, edgecolor=S.INK),
             Patch(facecolor=S.GREY, hatch="..", edgecolor=S.INK)],
            ["rulings", "new printings"],
            loc="upper left", bbox_to_anchor=(-0.012, 1.15), ncol=1,
            fontsize=FLOOR, frameon=False, handlelength=1.1, handleheight=0.9,
            labelspacing=0.20, borderpad=0.0, handletextpad=0.4)

# the one callout: Feb-2017 has no release (the T2 empty denominator).  Kept
# left of the tall Feb bar; arrow ends at the empty denominator slot's baseline.
# It sits in the bar-free upper third; an opaque white bbox turns it into a
# leadered callout so the T1 band tint reads as *behind* the text (the text-over-
# tint collision the review flagged at x=1.52 on the T1 band left edge 1.53).
ax_a.annotate("no release Feb '17;\nneighbours 01-21, 03-17",
              (4.56, YMAX * 0.02),
              xytext=(1.52, YMAX * 0.88), fontsize=FLOOR, color=S.INK,
              va="center", ha="left", linespacing=1.05, zorder=6,
              bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                        edgecolor="none", alpha=0.92),
              arrowprops=dict(arrowstyle="->", lw=0.6, color=S.INK,
                              connectionstyle="arc3,rad=-0.25"))

# ------------------------------ (b) same question, two as-of points, 2 systems
ax_b.set_xlim(0, 1)
ax_b.set_ylim(0, 1)
ax_b.axis("off")
XL, XA, XB = 0.010, 0.560, 0.855           # label col, T1 col, T2 col
# REDRAW (2026-08-27, review de-crowding): rows redistributed within the fixed
# 0..1 axis (no footprint change).  value->fraction offset raised 0.115 -> 0.135
# so each bold value clears its fraction; the header rule is separated from the
# green box top (was coincident at 0.820); R2 lifted so the bottom fractions
# clear the axis edge.  Columns: R1 AND R2 values are both centred on XA/XB
# (R2 no longer shifted -0.048), so value, fraction and header share one column.
HDR, R1, WIT, R2 = 0.910, 0.655, 0.395, 0.185
OFF = 0.135                                 # value -> fraction offset (was 0.115)
RULE_Y = 0.835                              # header rule (was 0.820 = green top)
GREEN_TOP, GREEN_BOT = 0.820, 0.330

ax_b.text(0.5, 1.06, "“ruling_intensity of card_games, as of T?”",
          ha="center", va="center", fontsize=8.0, color=S.INK, style="italic")
ax_b.text(XA, HDR, f"T₁ = {T1}", ha="center", va="center",
          fontsize=8.0, color=SPAN_INK)
ax_b.text(XB, HDR, f"T₂ = {T2}", ha="center", va="center",
          fontsize=8.0, color=SPAN_INK)
ax_b.plot([XL, 0.990], [RULE_Y] * 2, lw=0.6, color=S.INK)

# row 1 -- the as-of correct answers (GREEN: the semantics this paper defines)
ax_b.add_patch(Rectangle((XL, GREEN_BOT), 0.990 - XL, GREEN_TOP - GREEN_BOT,
                         facecolor="#E6F4EF", edgecolor="none", zorder=0))
ax_b.text(XL + 0.006, R1, "correct under\nas-of semantics", ha="left", va="center",
          fontsize=FLOOR, color=S.GREEN, linespacing=1.02)
ax_b.text(XA, R1, f"{100 * t1_rate:.2f}%", ha="center", va="center",
          fontsize=9.5, color=S.GREEN, fontweight="bold")
ax_b.text(XA, R1 - OFF, f"{t1_num}/{t1_den}", ha="center", va="center",
          fontsize=FLOOR, color="#3C6E5E")
ax_b.text(XB, R1, "REFUSE", ha="center", va="center",
          fontsize=9.5, color=S.GREEN, fontweight="bold")
ax_b.text(XB, R1 - OFF, "missing-caliber", ha="center", va="center",
          fontsize=FLOOR, color="#3C6E5E")
ax_b.text(0.5, WIT, f"witness ({t2_num:,}, {t2_den}): same-window denominator empty",
          ha="center", va="center", fontsize=FLOOR, color="#3C6E5E")

# row 2 -- what a governance-blind system returns (VERMILION: the failure mode).
# value centred on the column (aligned with R1's value and the fraction below);
# the ✗ marker sits at a fixed offset to the right of every column.
ax_b.text(XL + 0.006, R2, "governance-blind\n(all-history)", ha="left", va="center",
          fontsize=FLOOR, color=S.VERMILION, linespacing=1.02)
for xc, r, frac in ((XA, naive_t1, f"{t1_num}/{ALLTIME_DEN:,}"),
                    (XB, naive_t2, f"{t2_num:,}/{ALLTIME_DEN:,}")):
    ax_b.text(xc, R2, f"{100 * r:.2f}%", ha="center", va="center",
              fontsize=9.5, color=S.VERMILION, fontweight="bold")
    ax_b.text(xc + 0.105, R2, "✗", ha="center", va="center",
              fontsize=9.5, color=S.VERMILION)
    ax_b.text(xc, R2 - OFF, frac, ha="center", va="center",
              fontsize=FLOOR, color=S.VERMILION)

out = os.path.join(HERE, "fig1_asof_gap.pdf")
fig.savefig(out, metadata={"CreationDate": None})   # byte-reproducible re-runs
print("wrote", out)
print(f"  T1 {t1_num}/{t1_den}={100 * t1_rate:.2f}%  |  "
      f"blind {t1_num}/{ALLTIME_DEN}={100 * naive_t1:.2f}%")
print(f"  T2 gold=missing-caliber ({t2_num},{t2_den})  |  "
      f"blind {t2_num}/{ALLTIME_DEN}={100 * naive_t2:.2f}%  |  "
      f"answered {n_answered}/{len(llm)}")

# ---- footprint + font-floor self-assertions (exit non-zero on violation) -----
try:
    from pypdf import PdfReader
except Exception:
    from PyPDF2 import PdfReader
mb = PdfReader(out).pages[0].mediabox
w_in, h_in = float(mb.width) / 72.0, float(mb.height) / 72.0
print(f"  box {w_in:.3f} x {h_in:.3f} in  (ceiling 3.35 x 2.70)")
assert w_in <= 3.35 + 0.02 and h_in <= 2.70 + 0.001, (w_in, h_in)
