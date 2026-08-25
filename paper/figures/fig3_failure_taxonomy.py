"""Failure taxonomy, stacked to the TRUE denominator (60 public-base questions).

PILOT2 REMAKE.  Nine arms, one row each, horizontal stacked bars inside a
3.35 in (= \\columnwidth) figure.  The six taxonomy classes of the frozen
pilot2 scorer stack to the same true denominator of 60 on every row; EVERY
non-empty segment is annotated with its count (a single-question segment still
holds its own digit at 6 pt with a white halo), and the ROW ORDER IS THE MAIN
TABLE'S ROW ORDER: the four plain baselines (claude the pre-registered
reference first), the three prompt variants, the governance-informed arm, then
the compiler.  The governance-informed arm sits in its own class band: it is
the only LLM arm that saw the governance layer, so pooling it with either
neighbour would hide the single comparison a reviewer asks for first.

Bars stack to 60 so the denominator is visible on the figure itself -- no
conditional rate is shown without the population it is conditioned on.

Data: figures/fig_data_pilot2.json (extract_p2.py), which cross-asserts the scored
matrix of pilot2_arms_summary.json against pilot2_summary.json and re-derives
every elimination fraction from the per-question verdicts.  The mechanism row
is the frozen certs2 acceptance anchor (0/60), not a re-run.
"""

import json
import os
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "fig_data_pilot2.json")))
N = D["n_questions"]
TAX = D["taxonomy"]

# row order == main results table row order (top to bottom)
ORDER = ["baseline_claude", "baseline_qwen", "baseline_deepseek", "baseline_minimax",
         "trivial_claude", "trivial_v2", "trivial_v3",
         "governance_informed", "mechanism"]
assert [s["id"] for s in D["systems"]] == ORDER   # single source for the order
LAB = {s["id"]: s["label"] for s in D["systems"]}
CLS = {s["id"]: s["class"] for s in D["systems"]}
SHORT = {
    "baseline_claude": "claude-opus-4-6", "baseline_qwen": "qwen3-coder-next",
    "baseline_deepseek": "deepseek-3.2", "baseline_minimax": "minimax-m2.5",
    "trivial_claude": "v1 one-line", "trivial_v2": "v2 registry-join",
    "trivial_v3": "v3 worked ex.", "governance_informed": "governance layer",
    "mechanism": "binding compiler",
}
CLASS_COL = {"plain": S.BLUE, "prompt": S.ORANGE,
             "governed": S.INK, "mechanism": S.GREEN}

# y positions, top to bottom, with a gap between the four system classes
YS = {"baseline_claude": 10.0, "baseline_qwen": 9.0, "baseline_deepseek": 8.0,
      "baseline_minimax": 7.0, "trivial_claude": 5.6, "trivial_v2": 4.6,
      "trivial_v3": 3.6, "governance_informed": 2.2, "mechanism": 0.75}
ys = [YS[s] for s in ORDER]

fig, ax = plt.subplots(figsize=(S.COL_W, 1.52 * (11.40 - 0.05) / 10.05))

left = [0.0] * len(ORDER)
# Per-row count of narrow segments already annotated, so that consecutive
# narrow segments alternate their digit above / below the row centreline.
narrow_seen = {}
for key, col, hatch, label in S.TAXONOMY:
    vals = [TAX[s].get(key, 0) for s in ORDER]
    ax.barh(ys, vals, left=left, height=0.74, color=col, hatch=hatch,
            edgecolor=S.INK, linewidth=0.4, label=label, zorder=3)
    for y, v, l in zip(ys, vals, left):
        if v <= 0:
            continue
        dark = col in (S.VERMILION, S.GREY)
        # A segment narrower than ~2/60 of the bar cannot hold its digit with
        # any separation from its neighbour: two adjacent 1-wide segments put
        # "5" and "1" a hairline apart and the row reads as "51".  Those counts
        # are lifted into the gap above the bar on a short leader instead; the
        # axes limits are fixed above, so nothing about the figure box moves.
        # A segment narrower than ~2/60 of the bar is about 3 pt wide, so two
        # adjacent narrow segments put their digits a hairline apart and the
        # row reads as one number ("5" then "1" as "51").  Narrow counts
        # therefore alternate above / below the row centreline -- still inside
        # the bar, so no label can collide with a neighbouring row or with the
        # header, and two adjacent digits never share a baseline.
        dy = 0.0
        if v <= 2:
            k = narrow_seen.get(y, 0)
            narrow_seen[y] = k + 1
            dy = 0.165 if k % 2 == 0 else -0.165
        ax.annotate(f"{v}", (l + v / 2, y + dy), ha="center", va="center",
                    fontsize=6.0 if dy == 0.0 else 5.6, zorder=5,
                    color="#FFFFFF" if dark else S.INK,
                    path_effects=[pe.withStroke(
                        linewidth=1.1, foreground=S.INK if dark else "#FFFFFF")])
    left = [l + v for l, v in zip(left, vals)]
assert all(abs(x - N) < 1e-9 for x in left), left      # every bar closes on 60

# true-denominator rule
ax.axvline(N, lw=0.6, ls=(0, (3, 2)), color=S.INK, zorder=4)
ax.annotate(f"n = {N} (true denominator), {D['n_refusal_questions']} refusal Qs",
            (0, 10.85), ha="left", va="bottom", fontsize=6.0, color=S.INK)

# class brackets on the right, outside the bars
for s0, s1, txt in (("baseline_claude", "baseline_minimax", "plain"),
                    ("trivial_claude", "trivial_v3", "prompt"),
                    ("governance_informed", "governance_informed", "gov."),
                    ("mechanism", "mechanism", "ours")):
    col = CLASS_COL[CLS[s0]]
    y0, y1 = YS[s1] - 0.42, YS[s0] + 0.42
    ax.plot([62.6, 62.6], [y0, y1], lw=1.1, color=col, clip_on=False, zorder=5)
    if s0 == s1:
        ax.annotate(txt, (64.0, (y0 + y1) / 2), ha="left", va="center",
                    fontsize=6.0, color=col, annotation_clip=False)
    else:
        ax.annotate(txt, (64.2, (y0 + y1) / 2), ha="center", va="center",
                    rotation=90, fontsize=6.0, color=col, annotation_clip=False)

ax.set_yticks(ys)
ax.set_yticklabels([SHORT[s] for s in ORDER], fontsize=6.1)
for t, s in zip(ax.get_yticklabels(), ORDER):
    t.set_color(CLASS_COL[CLS[s]])
    if CLS[s] == "mechanism":
        t.set_fontweight("bold")
ax.set_xlabel("questions", labelpad=1.5, fontsize=6.2)
ax.set_xlim(0, 68.9)
ax.set_ylim(0.05, 11.40)
ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
ax.tick_params(axis="x", labelsize=6.0, pad=1.2)
ax.tick_params(axis="y", length=0, pad=1.5)
ax.spines["left"].set_visible(False)

ax.legend(loc="lower center", bbox_to_anchor=(0.46, 1.03), ncol=3, fontsize=6.0,
          handlelength=1.1, handleheight=0.9, columnspacing=0.7,
          labelspacing=0.25, borderpad=0.0, handletextpad=0.35)

out = os.path.join(HERE, "fig3_failure_taxonomy.pdf")
fig.savefig(out, metadata={"CreationDate": None})  # byte-reproducible re-runs
print("wrote", out)
for s in ORDER:
    t = TAX[s]
    print(f"  {LAB[s]:28s} err={1 - t.get('correct',0)/N:.3f}  "
          f"answered-should-refuse={t.get('answered_should_refuse',0)}  "
          f"sum={sum(t.values())}")
