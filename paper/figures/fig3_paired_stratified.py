"""Fig.3 -- effects with uncertainty, and where the errors live (two panels).

NEW 2026-08-27 (FIGURE_REDESIGN_SPEC v1 §4): replaces the single-dimension
failure-taxonomy bar in the body (which moves to the technical report).  Left
panel: per-arm paired error reduction vs the pre-registered reference
(claude-opus-4-6) with cluster-bootstrap 95% CIs.  Right panel: accuracy
stratified by gold form (value / rewrite / refusal), the reviewer's
"where does the residue sit" view.

NUMBERS DISCIPLINE (assert before draw; exit non-zero on mismatch):
  * LEFT panel reads pilot2/poststudy2_20260823/s4/s4_summary.json AND NOTHING
    ELSE for the four paired arms -- means and CIs asserted equal to the JSON
    to 1e-12, and the drawn arm set equals the JSON key set.
  * mechanism 0/60 binds to fig_data_pilot2.json["error_counts"]["mechanism"].
  * RIGHT panel reads fig_data_pilot2.json["per_gold_form"] -- every printed
    correct/n cell is n - errors, asserted; the three strata sum to 60.

Footprint: figsize=(COL_W, 1.65) -- identical box to the taxonomy bar it
replaces.  No legend: row-label colours carry the arm class (established in
Table 3), which is what pays for the second panel inside the old footprint.

Run:  python3 fig3_paired_stratified.py
"""

import json
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACT_ROOT = os.path.dirname(os.path.dirname(HERE))


def _resolve(rel):
    local = os.path.join(ARTIFACT_ROOT, rel)
    return local if os.path.exists(local) else os.path.join(
        "/Volumes/SSD 1/explore_opportunity_cc", rel)


FD = json.load(open(os.path.join(HERE, "fig_data_pilot2.json")))
S4 = json.load(open(_resolve("pilot2/poststudy2_20260823/s4/s4_summary.json")))

ORDER = ["baseline_claude", "baseline_qwen", "baseline_deepseek", "baseline_minimax",
         "trivial_claude", "trivial_v2", "trivial_v3",
         "governance_informed", "mechanism"]
assert [s["id"] for s in FD["systems"]] == ORDER          # single source for order
CLS = {s["id"]: s["class"] for s in FD["systems"]}
CLASS_COL = {"plain": S.BLUE, "prompt": S.ORANGE, "governed": S.INK, "mechanism": S.GREEN}
SHORT = {
    "baseline_claude": "claude-opus-4-6", "baseline_qwen": "qwen3-coder-next",
    "baseline_deepseek": "deepseek-3.2", "baseline_minimax": "minimax-m2.5",
    "trivial_claude": "v1 one-line", "trivial_v2": "v2 registry-join",
    "trivial_v3": "v3 worked ex.", "governance_informed": "governance layer",
    "mechanism": "binding compiler",
}

# y positions: row 0 (top) = baseline_claude ... row 8 (bottom) = mechanism
YS = {sid: len(ORDER) - 1 - i for i, sid in enumerate(ORDER)}

# ---- LEFT-panel bindings (s4 only) -------------------------------------------
PD = S4["paired_differences"]
assert S4["reference_arm"] == "baseline_claude" and S4["reference_errors"] == 36
assert set(PD.keys()) == {"trivial_claude", "trivial_v2", "trivial_v3",
                          "governance_informed"}, set(PD.keys())
EXPECT = {
    "trivial_claude": (0.06666666666666667, [-0.046153846153846156, 0.1774193548387097], False),
    "trivial_v2": (0.016666666666666666, [-0.1016949152542373, 0.11666666666666667], False),
    "trivial_v3": (-0.06666666666666667, [-0.14285714285714285, -0.015151515151515152], True),
    "governance_informed": (0.13333333333333333, [-0.05, 0.3], False),
}
for k, (m, ci, excl) in EXPECT.items():
    assert abs(PD[k]["mean_paired_diff"] - m) < 1e-12, (k, PD[k]["mean_paired_diff"])
    assert abs(PD[k]["ci95_percentile"][0] - ci[0]) < 1e-12, (k, PD[k]["ci95_percentile"])
    assert abs(PD[k]["ci95_percentile"][1] - ci[1]) < 1e-12, (k, PD[k]["ci95_percentile"])
    assert PD[k]["ci_excludes_zero"] == excl, (k, PD[k]["ci_excludes_zero"])
assert FD["error_counts"]["mechanism"] == 0

# ---- RIGHT-panel bindings (per_gold_form) ------------------------------------
PGF = FD["per_gold_form"]
n_val = FD["n_value_questions"]
n_rw = FD["n_rewrite_questions"]
n_rf = FD["n_refusal_questions"]
assert (n_val, n_rw, n_rf) == (33, 12, 15) and n_val + n_rw + n_rf == 60
STRATA = [("value", n_val), ("rewrite", n_rw), ("refusal", n_rf)]
CORRECT = {}
for sid in ORDER:
    row = {}
    for form, n in STRATA:
        cell = PGF[sid][form]
        assert cell["n"] == n, (sid, form, cell["n"])
        row[form] = cell["n"] - cell["errors"]           # correct = n - errors
    CORRECT[sid] = row
assert CORRECT["mechanism"] == {"value": 33, "rewrite": 12, "refusal": 15}


def ramp(acc):
    """4-step greyscale keyed to accuracy; numbers carry the information."""
    if acc < 0.25:
        return "#FFFFFF"
    if acc < 0.50:
        return "#EFEFEF"
    if acc < 0.75:
        return "#DCDCDC"
    return "#C4C4C4"


# ================================================================ drawing =======
FLOOR = 7.5
# Fixed canvas (width == \columnwidth): the shared style enables constrained
# layout, which would both ignore subplots_adjust and, with savefig bbox=tight,
# let long y-labels widen the page past \columnwidth.  Turn it off for this
# figure so the manual margins below govern placement.
mpl.rcParams["figure.constrained_layout.use"] = False
fig, (axL, axR) = plt.subplots(
    1, 2, figsize=(S.COL_W, 1.65), gridspec_kw={"width_ratios": [0.92, 1.28]},
    sharey=True)

# ---- LEFT panel --------------------------------------------------------------
axL.axvline(0.0, lw=0.6, ls=(0, (3, 2)), color=S.INK, zorder=1)
# the four paired arms: dot at mean, whisker = 95% CI
for k in EXPECT:
    y = YS[k]
    m = PD[k]["mean_paired_diff"]
    lo, hi = PD[k]["ci95_percentile"]
    col = CLASS_COL[CLS[k]]
    axL.errorbar([m], [y], xerr=[[m - lo], [hi - m]], fmt="o", color=col,
                 ecolor=col, elinewidth=1.0, capsize=2.0, markersize=3.4, zorder=4)
# reference arm: open marker at 0
axL.plot([0.0], [YS["baseline_claude"]], marker="o", mfc="white",
         mec=CLASS_COL["plain"], mew=1.0, markersize=4.0, zorder=4)
axL.annotate("ref", (0.0, YS["baseline_claude"]), xytext=(4, 0),
             textcoords="offset points", va="center", ha="left",
             fontsize=FLOOR, color=CLASS_COL["plain"])
# the three other plain baselines: not in the pre-registered paired set
for k in ("baseline_qwen", "baseline_deepseek", "baseline_minimax"):
    axL.annotate("–", (-0.185, YS[k]), va="center", ha="left", fontsize=FLOOR,
                 color=S.FAINT)
# mechanism: deterministic transcript, no interval -> diamond, exact tag
axL.plot([0.415], [YS["mechanism"]], marker="D", color=S.GREEN, markersize=3.6, zorder=5)
axL.annotate("0/60 exact", (0.415, YS["mechanism"]), xytext=(-4, 0),
             textcoords="offset points", va="center", ha="right",
             fontsize=FLOOR, color=S.GREEN, fontweight="bold")
# the two CI-annotations the spec calls out (negative result printed, not hidden).
# Both extend into empty space to the RIGHT of their marks so nothing overflows.
axL.annotate("excl. 0", (PD["trivial_v3"]["ci95_percentile"][1], YS["trivial_v3"]),
             xytext=(3, 0), textcoords="offset points", va="center", ha="left",
             fontsize=FLOOR, color=CLASS_COL["prompt"])
# governance CI includes 0 -> "n.s." on its own row, right of the whisker cap
# (the full "[-0.05, 0.30] straddles zero" reading lives in the caption)
axL.annotate("n.s.", (PD["governance_informed"]["ci95_percentile"][1],
             YS["governance_informed"]), xytext=(4, 0), textcoords="offset points",
             va="center", ha="left", fontsize=FLOOR, color=CLASS_COL["governed"])
# shared note for the en-dash rows: placed in the whisker-free gap between two
# of the dashed baseline rows so it collides with nothing.
axL.annotate("– not in paired set",
             (-0.17, (YS["baseline_qwen"] + YS["baseline_deepseek"]) / 2),
             va="center", ha="left", fontsize=FLOOR, color="#777777")

axL.set_xlim(-0.20, 0.45)
axL.set_xticks([-0.1, 0.0, 0.1, 0.2, 0.3, 0.4])
axL.set_xticklabels(["-.1", "0", ".1", ".2", ".3", ".4"], fontsize=FLOOR)
axL.set_xlabel("Δerror vs claude-opus-4-6  (→ fewer)",
               fontsize=FLOOR, labelpad=1.5)
axL.set_ylim(-0.9, len(ORDER) - 0.4)
axL.set_yticks(list(range(len(ORDER))))
axL.set_yticklabels([SHORT[sid] for sid in
                     sorted(ORDER, key=lambda s: YS[s])], fontsize=FLOOR)
for t, sid in zip(axL.get_yticklabels(), sorted(ORDER, key=lambda s: YS[s])):
    t.set_color(CLASS_COL[CLS[sid]])
    if CLS[sid] == "mechanism":
        t.set_fontweight("bold")
axL.tick_params(axis="y", length=0, pad=1.5)
axL.tick_params(axis="x", pad=1.2)
axL.spines["left"].set_visible(False)

# ---- RIGHT panel: 9x3 stratified-accuracy matrix -----------------------------
axR.set_xlim(-0.5, len(STRATA) - 0.5)
for ci, (form, n) in enumerate(STRATA):
    for sid in ORDER:
        y = YS[sid]
        c = CORRECT[sid][form]
        acc = c / n
        axR.add_patch(Rectangle((ci - 0.44, y - 0.42), 0.88, 0.84, facecolor=ramp(acc),
                                edgecolor="#BBBBBB", lw=0.3, zorder=1))
        bold = (sid == "mechanism")
        axR.text(ci, y, f"{c}/{n}", ha="center", va="center", fontsize=FLOOR, zorder=3,
                 color=S.GREEN if bold else S.INK,
                 fontweight="bold" if bold else "normal")
# column headers at the TOP (bind the three n; assert done above)
axR.set_xticks(range(len(STRATA)))
axR.set_xticklabels([f"value\nn={n_val}", f"rewrite\nn={n_rw}", f"refusal\nn={n_rf}"],
                    fontsize=FLOOR)
axR.xaxis.tick_top()
axR.xaxis.set_label_position("top")
axR.tick_params(axis="x", length=0, pad=2.0)
axR.tick_params(axis="y", length=0)
for sp in ("left", "right", "top", "bottom"):
    axR.spines[sp].set_visible(False)

fig.subplots_adjust(left=0.315, right=0.995, top=0.845, bottom=0.190, wspace=0.06)

out = os.path.join(HERE, "fig3_paired_stratified.pdf")
with mpl.rc_context({"savefig.bbox": None}):     # canvas IS \columnwidth exactly
    fig.savefig(out, metadata={"CreationDate": None})
print("wrote", out)
for k in EXPECT:
    lo, hi = PD[k]["ci95_percentile"]
    print(f"  {SHORT[k]:18s} Δ={PD[k]['mean_paired_diff']:+.3f} "
          f"[{lo:+.3f},{hi:+.3f}] excl0={PD[k]['ci_excludes_zero']}")
print("  strata correct (value/rewrite/refusal):")
for sid in ORDER:
    r = CORRECT[sid]
    print(f"    {SHORT[sid]:18s} {r['value']:2d}/{n_val} {r['rewrite']:2d}/{n_rw} {r['refusal']:2d}/{n_rf}")

# ---- footprint self-assertion -------------------------------------------------
try:
    from pypdf import PdfReader
except Exception:
    from PyPDF2 import PdfReader
mb = PdfReader(out).pages[0].mediabox
w_in, h_in = float(mb.width) / 72.0, float(mb.height) / 72.0
print(f"  box {w_in:.3f} x {h_in:.3f} in  (ceiling 3.35 x 1.65)")
assert w_in <= 3.35 + 0.02 and h_in <= 1.65 + 0.001, (w_in, h_in)
