"""Figure F-D -- what certification costs, and what each layer buys.

PILOT2 REMAKE, TWO PANELS (single column).  The retired-to-prose ablation panel
returns: on the public base every rung is recomputed end to end (no transcribed
counterfactual survives), so the panel earns its space back as a drawn exhibit.

panel (a) COST -- the concession axis.  Four raw per-question samples, no
aggregation hiding a point, on two logarithmic axes:
  bottom axis, time  -- all 60 certificates' warm verification wall-clock
                        against all 45 answering queries' own execution time
                        (the 15 refusal certificates have no answering query and
                        are absent from that row by construction);
  top axis, bytes    -- every certificate's file size against the bytes of SQL
                        it certifies.
Median / p90 / max are marked on the verification sample, medians on the other
three; the bracket between each pair is the PAIRED per-question median ratio
(never a ratio of mismatched medians).  Verification is never cheaper than
answering (paired minimum 2.5x), so the panel is a falsification surface.  The
Prop 5.11 full-history escape class is NOT instantiated on this base -- every
AM(iv) certificate is window-bounded -- so no declared-exception marker
appears; the legacy corpus remains that class's cost reference.  The warm tail
(~0.18 s) is the disclosure-cell census replay on the largest self-join
(codebase_community posts), named on the panel.

panel (b) ABLATION LADDER -- five rungs, two bands, all recomputed by
extract_p2.py from the frozen certificates, warehouses and verifier:
  A1 full system            60/60  (gold re-executed, refusal reasons matched)
  A2 -- rewrite layer       48/60  (12 REWRITEs become over-refusals)
  A3 -- disclosure gate     50/60  (5 roll-ups + 2 masks answered fine-grained
                                    + 3 DISCLOSURE-BLOCKED answered)
  B1 verifier as shipped    60/60  ACCEPT
  B2 -- declared windows    50/60  (10 V0 fail-closed rejects: 8 range requests
                                    + 2 cross-window imperatives)
Bars stack to the true denominator 60; each lost segment keeps the failure
taxonomy's colour + hatch, so panel (b) reads in the same language as the
failure-taxonomy figure.

Data:  impl/cost_p2.json          (impl/measure_cost.py --pilot pilot2)
       figures/fig_data_pilot2.json (extract_p2.py)
Nothing below is typed by hand; every number is read out of those two files.

Run:  python3 extract_p2.py && python3 figD_cost_ablation.py
"""

import json
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import style as S

S.apply()
mpl.rcParams["figure.constrained_layout.use"] = False   # explicit axes below

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
COST = json.load(open(os.path.join(ROOT, "impl", "cost_p2.json"), encoding="utf-8"))
ABL = json.load(open(os.path.join(HERE, "fig_data_pilot2.json"),
                     encoding="utf-8"))["ablation"]

AGG, RECS = COST["aggregate"], COST["per_certificate"]
N = ABL["n_questions"]
MS = 1000.0

assert AGG["n_certificates"] == N == 60 and AGG["n_sql"] == 45
assert all(not r["symdiff_scan"] for r in RECS)   # no full-scan class on p2

t_ver = [(r["qid"], r["verify_warm_median_s"] * MS) for r in RECS]
t_ans = [(r["qid"], r["answer_warm_median_s"] * MS) for r in RECS
         if r["answer_warm_median_s"]]
b_cert = [(r["qid"], r["cert_bytes_file"]) for r in RECS]
b_sql = [(r["qid"], r["sql_bytes"]) for r in RECS if r["sql_bytes"]]
assert len(t_ver) == len(b_cert) == 60 and len(t_ans) == len(b_sql) == 45

v_med, v_p90, v_max = (AGG["verify_warm_s"][k] * MS for k in ("median", "p90", "max"))
a_med = AGG["answer_warm_s"]["median"] * MS
r_med, r_min, r_max = (AGG["ratio_warm"][k] for k in ("median", "min", "max"))
c_med = AGG["cert_bytes_file"]["median"]
s_med = AGG["sql_bytes"]["median"]
cold_tot = AGG["verify_cold_total_s"]
cold_med = AGG["verify_cold_s"]["median"]

# paired per-question byte ratio over the 45 SQL-emitting certificates (the
# 60-certificate byte median over the 45-question SQL median describes no
# question; the bracket prints the paired statistic, as the time bracket does)
_bpairs = sorted(r["cert_bytes_file"] / r["sql_bytes"] for r in RECS if r["sql_bytes"])
b_ratio = _bpairs[(len(_bpairs) - 1) // 2] if len(_bpairs) % 2 else \
    0.5 * (_bpairs[len(_bpairs) // 2 - 1] + _bpairs[len(_bpairs) // 2])

# the warm tail, named on the panel: the two slowest verifications
tail = sorted(t_ver, key=lambda t: -t[1])[:2]
assert {q for q, _ in tail} == {"CODE-Q1", "CODE-Q2"}, tail

# ---------------------------------------------------------------- geometry ---
FW, FH = S.COL_W, 3.42
fig = plt.figure(figsize=(FW, FH))


def rect(x_in, y_in, w_in, h_in):
    return [x_in / FW, y_in / FH, w_in / FW, h_in / FH]


L, W = 0.84, 2.46                       # left margin (row labels) and plot width

# ========================================================== panel (a) cost ===
ax = fig.add_axes(rect(L, 2.18, W, 0.80))            # time  (bottom axis)
tx = ax.twiny()                                      # bytes (top axis)

Y_CERT, Y_SQL, Y_VER, Y_ANS = 3.0, 2.0, 1.0, 0.0
for a in (ax, tx):
    a.set_ylim(-0.74, 3.76)


def jitter(n, amp=0.115):
    """Deterministic symmetric jitter -- no RNG, no run-to-run drift."""
    return [amp * (((i * 37) % 11) / 5.0 - 1.0) for i in range(n)]


ax.scatter([v for _, v in t_ver], [Y_VER + d for d in jitter(len(t_ver))],
           s=6.0, marker="o", facecolor=S.GREEN, edgecolor="none", alpha=0.85,
           zorder=3)
ax.scatter([v for _, v in t_ans], [Y_ANS + d for d in jitter(len(t_ans))], s=6.0,
           marker="o", facecolor="none", edgecolor=S.INK, linewidth=0.42,
           alpha=0.9, zorder=3)
tx.scatter([v for _, v in b_cert], [Y_CERT + d for d in jitter(len(b_cert))],
           s=6.0, marker="D", facecolor=S.GREEN, edgecolor="none", alpha=0.85,
           zorder=3)
tx.scatter([v for _, v in b_sql], [Y_SQL + d for d in jitter(len(b_sql))], s=6.0,
           marker="D", facecolor="none", edgecolor=S.INK, linewidth=0.42,
           alpha=0.9, zorder=3)


def qtick(a, x, y, lab, ly, ha="center"):
    a.plot([x, x], [y - 0.22, y + 0.22], lw=0.85, color=S.INK, zorder=6)
    if lab:
        a.annotate(lab, (x, ly), ha=ha, va="bottom" if ly > y else "top",
                   fontsize=5.4, color=S.INK, zorder=6)


qtick(ax, v_med, Y_VER, "", 1.22)
qtick(ax, v_p90, Y_VER, "", 1.22)
qtick(ax, v_max, Y_VER, "", 1.22)
ax.annotate("med %.1f · p90 %.0f · max %.0f ms" % (v_med, v_p90, v_max),
            ((v_med * v_max) ** 0.5, 1.30), ha="center", va="bottom", fontsize=5.4,
            color=S.INK, zorder=6)
qtick(ax, a_med, Y_ANS, "med %.2f ms" % a_med, -0.28)
qtick(tx, c_med, Y_CERT, "med %.1f kB" % (c_med / 1000.0), 3.26)
qtick(tx, s_med, Y_SQL, "med %d B" % s_med, 1.82)


def bracket(a, x0, x1, y, mult, lo, hi):
    a.annotate("", xy=(x1, y), xytext=(x0, y),
               arrowprops=dict(arrowstyle="<|-|>", lw=0.8, color=S.INK,
                               shrinkA=0, shrinkB=0, mutation_scale=4.5))
    a.annotate(r"$\bf{\times%.1f}$  (%.1f–%.0f)" % (mult, lo, hi),
               ((x0 * x1) ** 0.5, y), ha="center", va="center", fontsize=6.0,
               color=S.INK, zorder=7,
               bbox=dict(boxstyle="square,pad=0.12", fc="#FFFFFF", ec="none"))


bracket(tx, s_med, c_med, 2.55, b_ratio, _bpairs[0], _bpairs[-1])
bracket(ax, a_med, v_med, 0.52, r_med, r_min, r_max)

ax.set_xscale("log")
ax.set_xlim(0.09, 300)
ax.set_xticks([0.1, 1, 10, 100])
ax.set_xticklabels(["0.1", "1", "10", "100"])
ax.set_xlabel("wall-clock per question (ms, log; warm)", fontsize=5.8, labelpad=0.8)
tx.set_xscale("log")
tx.set_xlim(55, 9000)
tx.set_xticks([100, 1000])
tx.set_xticklabels(["100", "1k"])
tx.set_xlabel("artifact size (bytes, log)", fontsize=5.8, labelpad=1.0)
ax.set_yticks([Y_CERT, Y_SQL, Y_VER, Y_ANS])
ax.set_yticklabels(["certificate\n$n$=%d" % len(b_cert),
                    "its SQL\n$n$=%d" % len(b_sql),
                    "verify\n$n$=%d" % len(t_ver),
                    "answer\n$n$=%d" % len(t_ans)],
                   fontsize=5.5, linespacing=0.95)
for t, o in zip(ax.get_yticklabels(), (True, False, True, False)):
    if o:
        t.set_color(S.GREEN)
ax.tick_params(axis="y", length=0, pad=1.0)
for a in (ax, tx):
    a.tick_params(axis="x", labelsize=5.6, pad=1.0)
    a.spines["left"].set_visible(False)
ax.spines["top"].set_visible(False)
tx.spines["right"].set_visible(False)
tx.spines["left"].set_visible(False)
ax.grid(axis="x", lw=0.3, color=S.FAINT, zorder=0)
ax.axhline(1.74, lw=0.4, ls=(0, (2, 2)), color=S.FAINT, zorder=1)
fig.text(0.04 / FW, (FH - 0.09) / FH,
         "(a) cost: the certified path loses on both axes",
         fontsize=6.3, ha="left", va="baseline", fontweight="bold")
NOTE = ("warm tail: %s/%s (%.2f/%.2f s) replay the disclosure-cell census on the "
        "largest\nself-join; the full-history escape class (Prop 5.11) has no "
        "instance on this base" % (tail[0][0], tail[1][0],
                                   tail[0][1] / MS, tail[1][1] / MS))
fig.text(0.04 / FW, 1.80 / FH, NOTE, fontsize=5.4, ha="left", va="baseline",
         color=S.INK, linespacing=1.25)

# ================================================== panel (b) ablation ladder ===
axb = fig.add_axes(rect(L, 0.44, W, 1.06))
fig.text(0.04 / FW, 1.59 / FH,
         "(b) ablation ladder: every rung recomputed ($n$ = 60)",
         fontsize=6.3, ha="left", va="baseline", fontweight="bold")

RUNGS = ABL["rungs"]
assert [r["id"] for r in RUNGS] == ["A1", "A2", "A3", "B1", "B2"]
LOST_STYLE = {  # taxonomy colours + hatches, same language as the taxonomy figure
    "refused_should_answer": (S.SKY, "..", "over-refusal"),
    "wrong_value": (S.PURPLE, "\\\\", "wrong value"),
    "answered_should_refuse": (S.VERMILION, "//", "answered-should-refuse"),
    "fail_closed_reject": (S.GREY, "xx", "fail-closed REJECT"),
}
RLAB = {"A1": "A1 full system", "A2": "A2 $-$ rewrite layer",
        "A3": "A3 $-$ disclosure gate", "B1": "B1 as shipped",
        "B2": "B2 $-$ decl. windows"}
YSB = {"A1": 5.35, "A2": 4.35, "A3": 3.35, "B1": 1.85, "B2": 0.85}

for r in RUNGS:
    y = YSB[r["id"]]
    axb.barh(y, r["correct"], height=0.72, color=S.LIGHT, edgecolor=S.INK,
             linewidth=0.4, zorder=3)
    lx = r["correct"]
    for cls, n in sorted(r["lost_classes"].items()):
        col, hat, _ = LOST_STYLE[cls]
        axb.barh(y, n, left=lx, height=0.72, color=col, hatch=hat,
                 edgecolor=S.INK, linewidth=0.4, zorder=3)
        dark = col in (S.VERMILION, S.GREY)
        axb.annotate(f"{n}", (lx + n / 2, y), ha="center", va="center",
                     fontsize=5.6, color="#FFFFFF" if dark else S.INK, zorder=5)
        lx += n
    axb.annotate("%d/%d" % (r["correct"], N), (N + 1.2, y), ha="left",
                 va="center", fontsize=5.8, color=S.INK,
                 fontweight="bold" if r["lost"] == 0 else "normal")

axb.axvline(N, lw=0.6, ls=(0, (3, 2)), color=S.INK, zorder=4)
# band brackets: compiler rungs vs verifier rungs
for y0, y1, lab in ((YSB["A3"] - 0.5, YSB["A1"] + 0.5, "compiler"),
                    (YSB["B2"] - 0.5, YSB["B1"] + 0.5, "verifier")):
    axb.plot([-27.5, -27.5], [y0, y1], lw=0.9, color=S.INK, clip_on=False,
             zorder=5)
    axb.annotate(lab, (-29.4, (y0 + y1) / 2), ha="center", va="center",
                 rotation=90, fontsize=5.6, color=S.INK, annotation_clip=False)

axb.set_yticks([YSB[r["id"]] for r in RUNGS])
axb.set_yticklabels([RLAB[r["id"]] for r in RUNGS], fontsize=5.8)
axb.set_ylim(0.25, 5.95)
axb.set_xlim(0, 69.5)
axb.set_xticks([0, 15, 30, 45, 60])
axb.set_xlabel("questions kept correct (of 60)", fontsize=5.8, labelpad=1.0)
axb.tick_params(axis="x", labelsize=5.6, pad=1.0)
axb.tick_params(axis="y", length=0, pad=1.5)
axb.spines["left"].set_visible(False)

# mini-legend for the three lost classes that actually occur
items = [("refused_should_answer", "over-refusal"),
         ("wrong_value", "wrong value"),
         ("answered_should_refuse", "ans.-should-refuse"),
         ("fail_closed_reject", "fail-closed")]
lx = 0.06
for cls, lab in items:
    col, hat, _ = LOST_STYLE[cls]
    fig.patches.append(mpl.patches.Rectangle(
        (lx / FW, 0.050 / FH), 0.072 / FW, 0.072 / FH, facecolor=col,
        hatch=hat, edgecolor=S.INK, linewidth=0.4,
        transform=fig.transFigure, figure=fig))
    fig.text((lx + 0.095) / FW, 0.086 / FH, lab, fontsize=5.4, ha="left",
             va="center", color=S.INK)
    lx += 0.095 + 0.0455 * len(lab) + 0.065

out = os.path.join(HERE, "figD_cost_ablation.pdf")
fig.savefig(out, bbox_inches="tight", pad_inches=0.01,
            metadata={"CreationDate": None})  # byte-reproducible re-runs
print("wrote", out)
print("(a) verify ms med/p90/max = %.2f/%.2f/%.2f | answer ms med = %.3f | "
      "paired warm ratio med/min/max = %.1f/%.1f/%.1fx"
      % (v_med, v_p90, v_max, a_med, r_med, r_min, r_max))
print("    cert med %d B vs SQL med %d B | paired byte ratio med/min/max = "
      "%.1f/%.1f/%.1fx | 60 cold processes total %.2f s (med %.3f s)"
      % (c_med, s_med, b_ratio, _bpairs[0], _bpairs[-1], cold_tot, cold_med))
print("    warm tail: %s" % (tail,))
for r in RUNGS:
    print("(b) %-3s %-28s %2d/%d  lost %2d %s  [%s]"
          % (r["id"], r["label"], r["correct"], N, r["lost"],
             r["lost_classes"] or "-", r["provenance"]))
