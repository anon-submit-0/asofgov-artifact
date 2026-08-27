"""Fig.2 -- from question to independently checkable decision (METHOD figure).

NEW 2026-08-27 (FIGURE_REDESIGN_SPEC v1 §3): replaces figA_partition in the
body.  Both review rounds asked for the mechanism drawn: how a question becomes
either a certified answer or a typed refusal, and why the verifier's acceptance
is independent of the compiler.  The DOC(dagger)-grammar single-column dataflow
below carries it; the four-guard partition of the old figA survives here as the
guard-chain inset (its full four-request walk moves to the technical report).

TRUST BOUNDARY.  A full-width dashed rule separates the compiler side from the
verifier side; the certificate is the ONLY object that crosses it -- the
verifier shares no project-internal module with the compiler (CI import
assertion, INDEPENDENCE_REPORT).

NUMBERS DISCIPLINE.  Every number is read from a frozen JSON and asserted before
drawing (exit non-zero on mismatch); nothing is retyped:
  * guard-chain exit instances  -> fig_data_pilot2.json["partition"]
  * ACCEPT 60/60 -> poststudy3 v6aplus_summary.json
  * REJECT 78/78 forgeries (family battery 34 F1-F5 + 31 F6-F10 + 8 F11 + 5
    pinned; the round-2 F11 count) -> poststudy4 v6aplus_v4_summary.json
  * verifier re-derives 50/60 windows, fails closed on 10
                                -> fig_data_pilot2.json["ablation"]
  * certificate field list      -> keys of a real impl/certs2/*.json
  * cost 17.7x time / 10.2x bytes (a DEPLOYMENT TAX: verifying costs MORE than
    answering -- the honest direction the eval section reports, not "verify
    << answer")             -> impl/cost_p2.json (paired warm medians)

Run:  python3 fig2_certchain.py
"""

import json
import os
import statistics

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Polygon
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACT_ROOT = os.path.dirname(os.path.dirname(HERE))


def _resolve(rel):
    local = os.path.join(ARTIFACT_ROOT, rel)
    if os.path.exists(local):
        return local
    return os.path.join("/Volumes/SSD 1/explore_opportunity_cc", rel)


FD = json.load(open(os.path.join(HERE, "fig_data_pilot2.json")))
V6 = json.load(open(_resolve("pilot2/poststudy3_20260826/results/v6aplus_summary.json")))
V6_4 = json.load(open(_resolve("pilot2/poststudy4_20260827/results/v6aplus_v4_summary.json")))
COST = json.load(open(_resolve("impl/cost_p2.json")))
CERT2 = json.load(open(_resolve("impl/certs2/CARD-Q2.json")))["certificate"]
CERT7 = json.load(open(_resolve("impl/certs2/CARD-Q7.json")))["certificate"]

# ======================================================= bind + assert numbers ===
P = FD["partition"]
C = {c["tag"]: c for c in P["cells"]}
assert P["guard_chain"] == ["OOV", "AM", "MC"]
oov, am, mc, bnd = C["b"], C["c"], C["d"], C["a"]
assert oov["cls"] == "OOV" and oov["as_of"] == "2021-06"
assert am["cls"] == "AM" and abs(am["asked_value"] - 64.0) < 1e-9 \
    and abs(am["same_window_value"] - 0.4020100502512563) < 1e-12
assert mc["cls"] == "MC" and mc["num_mass"] == 2161 and mc["den_mass"] == 0 \
    and mc["qid"] == "CARD-Q7"
assert bnd["cls"] == "Bindable" and bnd["num_mass"] == 320 and bnd["den_mass"] == 796 \
    and abs(bnd["value"] - 0.4020100502512563) < 1e-12 and bnd["qid"] == "CARD-Q2"
am_asked_pct = int(round(am["asked_value"] * 100))       # 6400
am_sw_pct = 100 * am["same_window_value"]                # 40.20
bnd_pct = 100 * bnd["value"]                             # 40.20

# window re-derivation (verifier independence)
ABL = FD["ablation"]
assert ABL["window_source"]["derived"] == 50
b1 = next(r for r in ABL["rungs"] if r["id"] == "B1")
b2 = next(r for r in ABL["rungs"] if r["id"] == "B2")
assert b1["correct"] == 60 and b2["correct"] == 50 and b2["lost"] == 10
n_derived, n_failclosed = ABL["window_source"]["derived"], b2["lost"]   # 50, 10

# verdict ledger
assert V6["genuine60"]["accept"] == 60 and V6["genuine60"]["reject"] == 0
n_accept = V6["genuine60"]["accept"]
f15 = V6["old_forgeries_f1_f5"]["reject"]
f610 = V6["new_forgeries_f6_f10"]["total"]
assert V6["new_forgeries_f6_f10"]["reject"] == f610 == V6["new_forgeries_f6_f10"]["asserted_ok"]
pinned = V6["pinned_regressions"]["reject"]     # 5 round-1 pinned
# (2026-08-27, poststudy4 round 2) the F11 outer-row-filter family takes the
# forgery family battery 70 -> 78; the REJECT chip shows that family total.
f11 = V6_4["new_forgeries_f11"]["total"]
assert V6_4["new_forgeries_f11"]["reject"] == f11 == 8
assert f15 == 34 and f610 == 31 and pinned == 5
n_reject = f15 + f610 + pinned + f11
assert n_reject == V6_4["forgery_counts"]["task_formula_70_plus_f11"] == 78

# certificate field list -> real cert keys
need = {"anchors", "graph_pin", "routing", "disclosure", "probes"}
assert need <= set(CERT2.keys()), set(CERT2.keys())
assert "witness" in CERT7.get("refusal", {}), CERT7.get("refusal", {}).keys()

# cost: paired warm medians (verify / answer) -- the deployment tax direction
agg = COST["aggregate"]
sql_rows = [r for r in COST["per_certificate"] if r.get("output_kind") == "sql"]
time_ratio = agg["ratio_warm"]["median"]
byte_ratio = statistics.median([r["cert_bytes_file"] / r["sql_bytes"] for r in sql_rows])
assert round(time_ratio, 1) == 17.7, time_ratio
assert round(byte_ratio, 1) == 10.2, byte_ratio

# =========================================================== canvas (points) ===
PT = 1 / 72.0
W = S.COL_W / PT                       # exactly \columnwidth, in points
PAD = 1.5
UW = W - 2 * PAD                        # usable width
FLOOR, TITLE = 7.5, 8.0
INKC, GREY = S.INK, S.GREY

KLASS = {                              # guard-chip colour + hatch (figA semantics)
    "OOV": (S.SKY, ".."), "AM": (S.PURPLE, "\\\\"),
    "MC": (S.VERMILION, "//"), "Bindable": (S.GREEN, ""),
}

# --- vertical layout constants (y grows downward) -----------------------------
y_l1a, y_l1b = 2.0, 27.0               # lane 1 chips
y_ar1 = 39.0                           # arrows into compile
y_l2a, y_l2b = 39.0, 65.0             # lane 2 compile box
y_chip_a, y_chip_b = 70.0, 83.0       # lane 3 guard-chip row
y_exit0 = 88.0                         # lane 3 exit lines start
EXIT_H = 8.0
y_certa, y_certb = 121.0, 148.0       # lane 4 certificate
y_bound = 152.0                        # trust boundary
y_l5a, y_l5b = 154.0, 184.0          # lane 5 verifier box
y_cost_a, y_cost_b = 185.5, 194.5     # cost chip
H = y_cost_b + 1.2

fig = plt.figure(figsize=(W * PT, H * PT))
fig.set_constrained_layout(False)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(H, 0)
ax.set_axis_off()
REN = None


def txt(x, y, s, fs=FLOOR, ha="left", color=INKC, weight="normal", style_="normal", **kw):
    return ax.text(x, y, s, fontsize=fs, ha=ha, va="center", color=color,
                   fontweight=weight, fontstyle=style_, clip_on=False, **kw)


def width_pt(s, fs, **kw):
    global REN
    t = fig.text(0, 0, s, fontsize=fs, **kw)
    if REN is None:
        fig.canvas.draw()
        REN = fig.canvas.get_renderer()
    w = t.get_window_extent(renderer=REN).width / fig.dpi / PT
    t.remove()
    return w


def rbox(x, y0, y1, w, fill, edge=INKC, lw=0.6, hatch=None, r=2.2, z=2):
    p = FancyBboxPatch((x, y0), w, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                       facecolor=fill, edgecolor=edge, linewidth=lw, hatch=hatch,
                       clip_on=False, zorder=z)
    ax.add_patch(p)
    return p


def arrow(x0, y0, x1, y1, lw=0.6, color=INKC, ms=4.0):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", lw=lw, color=color, mutation_scale=ms),
                annotation_clip=False, zorder=4)


# =============================================================== lane 1 ==========
gap = 6.0
w1 = (UW - gap) / 2.0
lx, rx = PAD, PAD + w1 + gap
rbox(lx, y_l1a, y_l1b, w1, "#F4F1E8")
# store named G (its version axis nu is labelled full-size on the arrow below
# and in the certificate); avoiding a mathtext subscript keeps every glyph >=7.5pt
txt(lx + w1 / 2, y_l1a + 8.0, "governed store  G", fs=TITLE, ha="center", weight="bold")
txt(lx + w1 / 2, y_l1a + 18.0, "registries · anchors · caliber", fs=FLOOR, ha="center", color="#4A4636")
rbox(rx, y_l1a, y_l1b, w1, "#EEF3F8")
txt(rx + w1 / 2, y_l1a + 8.0, "question q · instant T", fs=TITLE, ha="center", weight="bold")
txt(rx + w1 / 2, y_l1a + 18.0, "declared as-of point", fs=FLOOR, ha="center", color="#3A5063")

# arrows down into compile, each labelled on the arrow (DriftBench trick)
arrow(lx + w1 / 2, y_l1b, lx + w1 / 2, y_l2a - 0.5, ms=4.0)
arrow(rx + w1 / 2, y_l1b, rx + w1 / 2, y_l2a - 0.5, ms=4.0)
txt(lx + w1 / 2 + 3.0, (y_l1b + y_l2a) / 2, r"graph @ $\nu$", fs=FLOOR, ha="left", color="#4A4636")
txt(rx + w1 / 2 + 3.0, (y_l1b + y_l2a) / 2, "q, T", fs=FLOOR, ha="left", color="#3A5063")

# =============================================================== lane 2 ==========
rbox(PAD, y_l2a, y_l2b, UW, "#F0F0F0")
txt(PAD + 5, y_l2a + 7.5, "MLR-Compile  (§4–§5)", fs=TITLE, ha="left", weight="bold")
txt(PAD + 5, y_l2a + 16.0,
    r"bounded search over binding points b = ⟨α, w, v, g⟩;", fs=FLOOR, ha="left", color="#333333")
txt(PAD + 5, y_l2a + 22.5,
    r"answer from the ≼-maximal legal rewrite, else typed refuse", fs=FLOOR, ha="left", color="#333333")
arrow(W / 2, y_l2b, W / 2, y_chip_a - 0.5, ms=4.0)

# ===================================================== lane 3: guard-chain inset ==
chain = ["OOV", "AM", "MC", "Bindable"]
cw = {k: width_pt(k, FLOOR, fontweight="bold") + 10.0 for k in chain}
total = sum(cw.values())
sepn = (UW - total) / (len(chain) - 1)
cx = PAD
chip_x = {}
for i, k in enumerate(chain):
    col, hat = KLASS[k]
    chip_x[k] = cx
    rbox(cx, y_chip_a, y_chip_b, cw[k], col, edge=INKC, lw=0.4, hatch=hat, r=1.6, z=3)
    txt(cx + cw[k] / 2, (y_chip_a + y_chip_b) / 2, k, fs=FLOOR, ha="center",
        color="white", weight="bold")
    if i < len(chain) - 1:
        xa = cx + cw[k]
        xb = xa + sepn
        arrow(xa + 1.0, (y_chip_a + y_chip_b) / 2, xb - 1.0, (y_chip_a + y_chip_b) / 2,
              lw=0.5, ms=3.4)
    cx += cw[k] + sepn

# exit lines: colour square + bold class tag + bound instance (one per chip,
# in the frozen chip order so line i corresponds to chip i above)
TAGDISP = {"OOV": "OOV", "AM": "AM", "MC": "MC", "Bindable": "Bind"}
EXITS = [
    ("OOV", "⊥", f"{oov['as_of']} · opens after both hulls close"),
    ("AM", "⊥", f"as-asked {am_asked_pct}% vs same-window {am_sw_pct:.2f}%"),
    ("MC", "⊥", f"witness ({mc['num_mass']:,}, {mc['den_mass']}) · CARD-Q7"),
    ("Bindable", "✓", f"{bnd['num_mass']}/{bnd['den_mass']} = {bnd_pct:.2f}% · CARD-Q2"),
]
x_sq, x_tag = PAD + 2.0, PAD + 8.0
x_inst = x_tag + max(width_pt(f"{g} {TAGDISP[k]}", FLOOR, fontweight="bold")
                     for k, g, _ in EXITS) + 5.0
for i, (k, glyph, s) in enumerate(EXITS):
    col = KLASS[k][0]
    yy = y_exit0 + i * EXIT_H
    ax.add_patch(Rectangle((x_sq, yy - 2.0), 4.0, 4.0, facecolor=col,
                           edgecolor=INKC, lw=0.3, clip_on=False, zorder=3))
    txt(x_tag, yy, f"{glyph} {TAGDISP[k]}", fs=FLOOR, ha="left", color=col, weight="bold")
    txt(x_inst, yy, s, fs=FLOOR, ha="left", color=INKC)
arrow(W / 2, y_exit0 + len(EXITS) * EXIT_H - 3.0, W / 2, y_certa - 0.5, ms=4.0)

# ===================================================== lane 4: the certificate ====
cw_doc = UW * 0.86
cx0 = (W - cw_doc) / 2
fold = 7.0
# document body with a folded top-right corner
ax.add_patch(Polygon([(cx0, y_certb), (cx0, y_certa), (cx0 + cw_doc - fold, y_certa),
                      (cx0 + cw_doc, y_certa + fold), (cx0 + cw_doc, y_certb)],
                     closed=True, facecolor="#FFFFFF", edgecolor=INKC, lw=0.7,
                     clip_on=False, zorder=3))
ax.add_patch(Polygon([(cx0 + cw_doc - fold, y_certa), (cx0 + cw_doc - fold, y_certa + fold),
                      (cx0 + cw_doc, y_certa + fold)], closed=True, facecolor="#E8E8E8",
                     edgecolor=INKC, lw=0.5, clip_on=False, zorder=4))
txt(cx0 + cw_doc / 2, y_certa + 7.5, "certificate", fs=TITLE, ha="center", weight="bold", zorder=5)
txt(cx0 + cw_doc / 2, y_certa + 16.0, r"anchor assignment · version pin $\nu$ · routing path",
    fs=FLOOR, ha="center", color="#333333", zorder=5)
txt(cx0 + cw_doc / 2, y_certa + 22.5, "disclosure decision · witnesses · probe records",
    fs=FLOOR, ha="center", color="#333333", zorder=5)

# the one object that crosses the trust boundary
arrow(W / 2, y_certb, W / 2, y_l5a - 0.5, lw=0.9, ms=5.0)

# ===================================================== the trust boundary =========
ax.plot([PAD, W - PAD], [y_bound, y_bound], lw=0.7, ls=(0, (3, 2)), color=INKC,
        clip_on=False, zorder=2)
txt(W - PAD, y_bound - 3.0, "no shared module — CI import assertion (§6)", fs=FLOOR,
    ha="right", color="#555555", style_="italic")

# ===================================================== lane 5: the verifier =======
vw = UW * 0.48
rbox(PAD, y_l5a, y_l5b, vw, "#EAF3EF")
v_title = "Chk — verifier (§6)"
v_body = ["re-executes probes vs",
          "(store, certificate);",
          f"re-derives {n_derived}/60 windows,",
          f"fails closed on {n_failclosed}"]
txt(PAD + 5, y_l5a + 5.5, v_title, fs=TITLE, ha="left", weight="bold")
for j, ln in enumerate(v_body):
    txt(PAD + 5, y_l5a + 11.5 + j * 5.3, ln, fs=FLOOR, ha="left", color="#2E4A40")

rxb = PAD + vw + 6.0
rww = W - PAD - rxb
# ACCEPT chip
rbox(rxb, y_l5a, y_l5a + 11.0, rww, "#E3F2EC", edge=S.GREEN, lw=0.7)
acc_s = f"✓ ACCEPT  {n_accept}/60 genuine"
txt(rxb + rww / 2, y_l5a + 5.5, acc_s, fs=FLOOR, ha="center", color=S.GREEN, weight="bold")
arrow(PAD + vw, y_l5a + 5.5, rxb - 0.5, y_l5a + 5.5, lw=0.5, ms=3.4)
# REJECT chip (two lines)
rbox(rxb, y_l5a + 13.5, y_l5b, rww, "#FBEAE0", edge=S.VERMILION, lw=0.7)
rej_s = f"✗ REJECT  {n_reject}/{n_reject} forgeries"
# family breakdown 34+31+8+5 does not fit the chip at 7.5pt; the pre/post
# split (matching E5's "34 pre-registered ... 44 post-registered") sums to the
# same 78 and fits.  The full F1-F11 + pinned breakdown is in E5 and the TR.
rej_sub = f"{f15} pre-reg · {f610 + pinned + f11} post-reg"
txt(rxb + rww / 2, y_l5a + 18.7, rej_s, fs=FLOOR, ha="center", color=S.VERMILION, weight="bold")
txt(rxb + rww / 2, y_l5a + 25.5, rej_sub, fs=FLOOR, ha="center", color=S.VERMILION)
arrow(PAD + vw, y_l5a + 20.0, rxb - 0.5, y_l5a + 20.0, lw=0.5, ms=3.4)

# ===================================================== the cost chip ==============
rbox(PAD, y_cost_a, y_cost_b, UW, "#F2F2F2", edge=GREY, lw=0.5, r=1.6)
cost_s = (f"cost (warm): verify {time_ratio:.1f}× answer time · "
          f"cert {byte_ratio:.1f}× SQL bytes")
txt(W / 2, (y_cost_a + y_cost_b) / 2, cost_s, fs=FLOOR, ha="center", color="#333333")

out = os.path.join(HERE, "fig2_certchain.pdf")
with mpl.rc_context({"savefig.bbox": None}):
    fig.savefig(out, metadata={"CreationDate": None})
print("wrote", out)

# ---- width self-assertions (prove 7.5pt fits at \columnwidth) -----------------
for k, glyph, s in EXITS:
    tagw = width_pt(f"{glyph} {TAGDISP[k]}", FLOOR, fontweight="bold")
    assert x_tag + tagw < x_inst, (k, "tag collides", round(tagw, 1))
    assert x_inst + width_pt(s, FLOOR) < W - PAD, (k, round(width_pt(s, FLOOR), 1))
assert width_pt(cost_s, FLOOR) < UW - 4, round(width_pt(cost_s, FLOOR), 1)
# lane-5 text must fit its box / chip
assert width_pt(v_title, TITLE, fontweight="bold") < vw - 8, round(width_pt(v_title, TITLE, fontweight="bold"), 1)
for ln in v_body:
    assert width_pt(ln, FLOOR) < vw - 8, (ln, round(width_pt(ln, FLOOR), 1))
for s in (acc_s, rej_s, rej_sub):
    assert width_pt(s, FLOOR, fontweight="bold") < rww - 4, (s, round(width_pt(s, FLOOR, fontweight="bold"), 1))
print(f"  guards: OOV {oov['as_of']} | AM {am_asked_pct}%/{am_sw_pct:.2f}% | "
      f"MC ({mc['num_mass']},{mc['den_mass']}) | Bindable {bnd['num_mass']}/{bnd['den_mass']}={bnd_pct:.2f}%")
print(f"  verdicts: ACCEPT {n_accept}/60 · REJECT {n_reject}/{n_reject} = {f15}+{f610}+{f11}+{pinned}")
print(f"  windows: derived {n_derived}/60 · fail-closed {n_failclosed}")
print(f"  cost: {time_ratio:.1f}x time · {byte_ratio:.1f}x bytes (verify > answer)")

# ---- footprint self-assertion -------------------------------------------------
try:
    from pypdf import PdfReader
except Exception:
    from PyPDF2 import PdfReader
mb = PdfReader(out).pages[0].mediabox
w_in, h_in = float(mb.width) / 72.0, float(mb.height) / 72.0
print(f"  box {w_in:.3f} x {h_in:.3f} in  (ceiling 3.35 x 2.75)")
assert w_in <= 3.35 + 0.02 and h_in <= 2.75 + 0.001, (w_in, h_in)
