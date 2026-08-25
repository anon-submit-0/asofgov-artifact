"""Fig.1 -- the as-of semantics gap (PROBLEM figure, not an architecture figure).

Worked example, variant (3) of the figures-SOP: one real governed metric, one
real question, two as-of points, and the answers a governance-blind system
produces.  PILOT2 MIGRATION (2026-08-04): the instance is the public
card_games running example (ruling_intensity; CARD-Q2 / CARD-Q7), so every
number drawn here is recomputable from the released base.  The old enterprise
SKU instance survives only as provenance-marked motivation prose in Section 1.

SELF-CONTAINED AND CROSS-ASSERTED: every number is queried live from the
pilot2 card_games warehouse and asserted against the frozen artifacts before
anything is drawn --
  - T1 = 2016-11: ruling_intensity 320/796 = 40.20%, asserted equal to the
    frozen gold of CARD-Q2 and to its ACCEPTed certificate's decision;
  - T2 = 2017-02: numerator 2,161 rulings, same-window denominator 0 new
    printings -> bot_MC(ii); the certificate's own denominator-probe SQL is
    re-executed here and must return 0;
  - "6/8 evaluated LLM arms answered" is re-tallied from
    pilot2/pilot2_arms_summary.json per-question verdicts (CARD-Q7).
The script exits non-zero rather than draw a figure that disagrees with the
frozen evidence.  Values print as percentages, matching figA_partition.
"""

import json
import os

import duckdb
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # explore_opportunity_cc/
WH = os.path.join(ROOT, "pilot2", "domains", "card_games", "warehouse.duckdb")
QS = os.path.join(ROOT, "pilot2", "domains", "card_games", "questions.json")
ARMS = os.path.join(ROOT, "pilot2", "pilot2_arms_summary.json")
CERTS2 = os.path.join(ROOT, "impl", "certs2")

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

e7 = json.load(open(os.path.join(CERTS2, "CARD-Q7.json")))
assert e7["refusal"] == "missing-caliber"
wit = e7["certificate"]["refusal"]["witness"]
assert wit["type"] == "empty-denominator-probe" and wit["observed"] == 0.0
assert float(con.execute(wit["probe_sql"]).fetchone()[0]) == 0.0
e2 = json.load(open(os.path.join(CERTS2, "CARD-Q2.json")))
assert e2["certificate"]["disclosure"]["decision"] == "ANSWER"
con.close()

verdicts = json.load(open(ARMS))["per_question_verdicts"]["CARD-Q7"]
llm = [a for a in verdicts if a != "mechanism"]
assert len(llm) == 8 and verdicts["mechanism"] == "correct"
n_answered = sum(1 for a in llm if verdicts[a] == "answered_should_refuse")

naive_t1 = t1_num / ALLTIME_DEN
naive_t2 = t2_num / ALLTIME_DEN

# ------------------------------------------------------------------- drawing
SPAN = "#DCE6F0"
SPAN_INK = "#2B4C6F"

fig = plt.figure(figsize=(S.COL_W, 3.25))  # W14 (2026-08-06): the 6.0pt panel-a note and the 5.8pt witness note are
# raised to 6.5pt (canvas verified unchanged).  The 5.9pt footer is DEFERRED
# to camera-ready: savefig.bbox=tight makes its line width the page width,
# so raising it widens the page and scales the whole figure DOWN at
# \columnwidth -- a net readability loss.  Needs a reflow, not a font bump.
gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 1.0, 2.2], hspace=0.22)
ax_n = fig.add_subplot(gs[0])
ax_d = fig.add_subplot(gs[1], sharex=ax_n)
ax_b = fig.add_subplot(gs[2])

# --------------------------------------------- (a) the governed facts, monthly
for ax, vals, lab, col in (
        (ax_n, num, "numerator: rulings @ rulings.date", S.INK),
        (ax_d, den, "denominator: new printings @ sets.releaseDate", S.GREY)):
    for x in (i_t1, i_t2):                       # the two as-of windows under test
        ax.axvspan(x - 0.47, x + 0.47, color=SPAN, zorder=0)
    ax.bar(range(len(MONTHS)), vals, width=0.52, color=col,
           edgecolor=S.INK, linewidth=0.5, zorder=3)
    for x, v in enumerate(vals):
        if v:
            ax.annotate(f"{v:,}", (x, v), ha="center", va="bottom",
                        fontsize=6.4, xytext=(0, 1.2), textcoords="offset points")
    ax.set_ylim(0, max(vals) * (1.85 if ax is ax_n else 1.45))
    ax.set_title(lab, loc="left", fontsize=6.1, color=S.INK, pad=2.0)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)

for x, tag in ((i_t1, "$T_1$"), (i_t2, "$T_2$")):
    ax_n.text(x, max(num) * 1.78, tag, ha="center", va="top",
              fontsize=7.0, color=SPAN_INK)

ax_n.tick_params(labelbottom=False)
ax_d.set_xticks(range(len(MONTHS)))
ax_d.set_xticklabels(SHORT)
ax_d.set_xlim(-0.70, len(MONTHS) - 0.30)
ax_d.annotate("no release in Feb 2017:\nneighbours 01-21 and 03-17",
              (i_t2, max(den) * 0.06),
              xytext=(2.95, max(den) * 0.92), fontsize=6.5, color=S.INK,
              va="center", ha="left", linespacing=1.05,
              arrowprops=dict(arrowstyle="->", lw=0.6, color=S.INK,
                              connectionstyle="arc3,rad=-0.25"))

# ------------------------------ (b) same question, two as-of points, 3 answers
ax_b.set_xlim(0, 1); ax_b.set_ylim(0, 1); ax_b.axis("off")
XL, XA, XB = 0.005, 0.545, 0.845            # label col, T1 col, T2 col
HDR, R1, WIT, R2, FOOT = 0.960, 0.780, 0.500, 0.255, 0.020

ax_b.text(0.5, 1.10, "“ruling_intensity of card_games, as of T?”",
          ha="center", va="center", fontsize=7.0, color=S.INK, style="italic")
ax_b.text(XA, HDR, f"$T_1$ = {T1}", ha="center", va="center",
          fontsize=6.8, color=SPAN_INK)
ax_b.text(XB, HDR, f"$T_2$ = {T2}", ha="center", va="center",
          fontsize=6.8, color=SPAN_INK)
ax_b.plot([XL, 0.995], [HDR - 0.080] * 2, lw=0.6, color=S.INK)

# row 1 -- the as-of correct answers (GREEN: the semantics this paper defines)
ax_b.add_patch(Rectangle((XL, WIT - 0.105), 0.995 - XL, R1 - WIT + 0.215,
                         facecolor="#E6F4EF", edgecolor="none", zorder=0))
ax_b.text(XL + 0.008, R1, "correct under\nas-of semantics", ha="left", va="center",
          fontsize=6.3, color=S.GREEN, linespacing=1.05)
ax_b.text(XA, R1, f"{100*t1_rate:.2f}%", ha="center", va="center",
          fontsize=8.0, color=S.GREEN, fontweight="bold")
ax_b.text(XA, R1 - 0.105, f"{t1_num}/{t1_den}", ha="center", va="center",
          fontsize=6.1, color="#3C6E5E")
ax_b.text(XB, R1, "REFUSE", ha="center", va="center",
          fontsize=8.0, color=S.GREEN, fontweight="bold")
ax_b.text(XB, R1 - 0.105, "missing-caliber", ha="center", va="center",
          fontsize=6.1, color="#3C6E5E")
ax_b.text(XB, WIT, f"witness ({t2_num:,}, {t2_den}): no\n"
          "same-window denominator", ha="center", va="center",
          fontsize=6.5, color="#3C6E5E", linespacing=1.05)

# row 2 -- what a governance-blind system returns (VERMILION: the failure mode)
ax_b.text(XL + 0.008, R2, "governance-blind\n(all-history)", ha="left", va="center",
          fontsize=6.3, color=S.VERMILION, linespacing=1.05)
for x, r, frac in ((XA, naive_t1, f"{t1_num}/{ALLTIME_DEN:,}"),
                   (XB, naive_t2, f"{t2_num:,}/{ALLTIME_DEN:,}")):
    ax_b.text(x, R2, f"{100*r:.2f}%", ha="center", va="center",
              fontsize=8.0, color=S.VERMILION, fontweight="bold")
    ax_b.text(x, R2 - 0.105, frac, ha="center", va="center",
              fontsize=6.1, color=S.VERMILION)
    ax_b.text(x + 0.125, R2, "✗", ha="center", va="center",
              fontsize=8.5, color=S.VERMILION)

ax_b.text(0.5, FOOT,
          f"the all-history denominator ({ALLTIME_DEN:,}) is blind to the "
          f"as-of window; at $T_2$ the\ngoverned answer is not a number at all \u2014 yet "
          f"{n_answered}/{len(llm)} evaluated LLM arms answered",
          ha="center", va="center", fontsize=5.9, color=S.INK, linespacing=1.25)

out = os.path.join(HERE, "fig1_asof_gap.pdf")
fig.savefig(out, metadata={"CreationDate": None})  # byte-reproducible re-runs
print("wrote", out)
print(f"  T1 {t1_num}/{t1_den}={100*t1_rate:.2f}%  |  "
      f"blind {t1_num}/{ALLTIME_DEN}={100*naive_t1:.2f}%")
print(f"  T2 gold=missing-caliber ({t2_num},{t2_den})  |  "
      f"blind {t2_num}/{ALLTIME_DEN}={100*naive_t2:.2f}%  |  "
      f"answered {n_answered}/{len(llm)}")
