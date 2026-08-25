"""F-B -- forgery x check hit matrix on the pilot2 base (34 forgeries, 11 bases).

PILOT2 REMAKE.  The forgery battery grew from 16 hand-built-base forgeries to 34
forgeries mutated from 11 REAL compiler certificates (every unmutated base
ACCEPTs, so each REJECT pins on the mutation itself), and gained the F4
disclosure family (10 forgeries against the k / mask / policy obligations that
did not exist on the old base) plus F5 (4 refusal-class / replay-variant
substitutions on a new CARD-Q2 base, added 2026-08-10).  45 columns no longer
fit a single column at a legible size, so this float is FULL WIDTH: include it
as a figure* with width=\\textwidth and NO rescaling.

WHAT IS DRAWN.  Rows = the nine checks in the verifier's own frozen order
(chk.py:CHECK_ORDER).  Columns = six bands: F1 coordinate/semantic swaps (6),
F2 field deletions (5), F3 semantic forgeries (9), F4 disclosure forgeries
(10), F5 refusal-class substitutions (4), then the 11 unmutated base
certificates.  Every cell carries the status the verifier actually reported
for that (column, check) pair:

  * solid        the check that rejected first (report["rejected_by"])
  * hatched      the check ALSO failed on this forgery, later in the order
  * flat light   the check ran and passed
  * dotted/empty the check does not apply to this certificate kind (SKIP)

A white ring marks the check the forgery was PRE-REGISTERED to trip
(forge_p2.py's expected_reject_by).  Ring and solid cell coincide on all 34;
had a forgery landed anywhere else, the disagreement would be visible without
reading a word.

THE CONCESSION BAND at the foot names what this round did NOT exercise: no
forgery is FIRST caught by V2 (V3 left that set when F5c/F5d arrived, since
that family is pre-registered to trip the clause-(iv) variant check), the
prior-guard clause of V6b carries zero of its
7 failures, and one declared boundary from the acceptance report: a PARTIALLY
omitted DB blocking set (non-empty, all registered) is not rejected -- only
emptied (F4f) or alien (F4g) sets are.

COLOUR SEMANTICS (unchanged, style.py): GREEN is our mechanism acting -- here,
a check firing; LIGHT is "nothing to report".  Every state carries a second,
redundant encoding (fill + hatch + glyph).  No type below 5.4 pt, and the PDF
is emitted at exactly \\textwidth so \\includegraphics applies scale 1.0.

DATA.  100% recomputed, nothing retyped: extract_p2.py reads the verifier's 34
run reports in impl/asof_verifier/forge_p2_out/, asserts every first rejection
against forge_p2.py's pre-registered target, and re-verifies the 11 unmutated
base certificates with the same chk.verify the forgeries ran under.

Run:  python3 extract_p2.py && python3 figB_forgery_matrix.py
"""

import json
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "fig_data_pilot2.json")))["forge"]

CHECKS = M["checks"]                      # V0 .. V6c, the verifier's own order
COLS = M["columns"]                       # the forgeries, then the base controls
FORG = [c for c in COLS if c["band"] != "ctl"]
# Pinned the same way extract_p2.py pins them, so a stale fig_data_pilot2.json
# fails here rather than silently drawing the wrong matrix.  F5 (4 forgeries on
# a new CARD-Q2 base) joined the battery on 2026-08-10: 34 forgeries, 11 bases.
FAMILY_SIZES = {"F1": 6, "F2": 5, "F3": 9, "F4": 10, "F5": 4}
N_FORG = sum(FAMILY_SIZES.values())       # 34
N_BASES = 11
assert len(FORG) == N_FORG and len(COLS) == N_FORG + N_BASES

# Row gloss: what each check consumes (<= the label gutter, asserted below).
GLOSS = {
    "V0": r"$\alpha$ re-derived", "V1": r"$\nu$ pin", "V2": r"$\alpha$ typed",
    "V3": "binding rule", "V4": r"$\rho$ routing", "V5": r"$\delta$ replay",
    "V6a": r"SQL $\subseteq$ cert", "V6b": r"$w$ replay", "V6c": r"$\neg$ guards",
}
# Column label = id + attack surface, abbreviated to fit a rotated label.  The
# F2 labels carry the DELETED FIELD (that band is the per-field experiment);
# the F4 labels name the disclosure obligation under attack.
CLAB = {
    "F1a": "F1a wrong year", "F1b": r"F1b den=0$\to$ANS",
    "F1c": "F1c shifted MC", "F1d": "F1d fake pair",
    "F1e": "F1e $-$offdiag mark", "F1f": "F1f version swap",
    "F2a": r"F2a $-\nu$ version", "F2b": r"F2b $-\alpha$ anchors",
    "F2c": r"F2c $-\rho$ routing", "F2d": r"F2d $-\delta$ disclos.",
    "F2e": r"F2e $-w$ witness",
    "F3a": r"F3a dangling $\nu$", "F3b": "F3b unmarked ungov.",
    "F3c": "F3c sum(rate)", "F3d": "F3d fake witness",
    "F3d2": r"F3d2 $|\triangle|$ tamper", "F3e": "F3e alien table",
    "F3f": "F3f self-override", "F3g": "F3g via tamper",
    "F3h": "F3h metric swap",
    "F4a": "F4a fine-grain ans.", "F4b": "F4b over-rollup",
    "F4c": "F4c fake SUPPMIN", "F4d": r"F4d $\Pi$ cleared",
    "F4e": "F4e claims ungov.", "F4f": r"F4f blocking $=\varnothing$",
    "F4g": "F4g alien policy", "F4h": "F4h $-$mask closure",
    "F4i": "F4i mask stripped", "F4j": "F4j mask downgrade",
    # F5 (2026-08-10): refusal-class / replay-variant substitution.  a and b
    # swap the refusal class across the OOV / AM(iv) boundary on the honest and
    # the covered leg; c and d swap the clause-(iv) replay variant.
    "F5a": "F5a OOV sub. honest", "F5b": "F5b OOV sub. covered",
    "F5c": "F5c fake AM(iv)", "F5d": "F5d variant swap",
}
for c in COLS:                              # controls: label by their base qid
    if c["band"] == "ctl":
        CLAB[c["id"]] = c["qid"]
BANDS = [("F1", "F1 swaps"), ("F2", "F2 delete"), ("F3", "F3 semantic"),
         ("F4", "F4 disclosure (new)"), ("F5", "F5 class sub. (new)"),
         ("ctl", "%d real bases, all ACCEPT" % N_BASES)]

# ------------------------------------------------------------------ geometry ---
PT = 1 / 72.0
W_IN = S.FULL_W                      # exactly \textwidth; do not rescale on use
GUT, LOADW = 53.0, 15.0              # pt: row-label gutter, right-hand load column
ROW_H, GAP = 7.6, 0.9                # pt per check row; blank col before controls
H_BAND, H_LAB, H_LEG, H_CONC = 11.0, 64.0, 9.0, 19.5      # pt, top to bottom
PADX, PADY = 1.0, 1.5

NCU = len(COLS) + GAP
GRID_W = W_IN / PT - GUT - LOADW - 2 * PADX
GRID_H = ROW_H * len(CHECKS)
H_IN = (H_BAND + H_LAB + GRID_H + H_LEG + H_CONC + 2 * PADY) * PT

fig = plt.figure(figsize=(W_IN, H_IN))
fig.set_constrained_layout(False)
ax = fig.add_axes([(PADX + GUT) * PT / W_IN,
                   (PADY + H_CONC + H_LEG) * PT / H_IN,
                   GRID_W * PT / W_IN, GRID_H * PT / H_IN])
ax.set_xlim(0, NCU)
ax.set_ylim(len(CHECKS), 0)
ax.set_xticks([])
ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)
COL_W_PT = GRID_W / NCU

XS, x = {}, 0.0
for c in COLS:
    if c["band"] == "ctl" and x < len(FORG) + 0.5:
        x += GAP
    XS[c["id"]] = x
    x += 1.0

# ------------------------------------------------------------------- cells -----
CELL = dict(FAIL1=dict(fc=S.GREEN, ec=S.INK, lw=0.6, hatch=None, al=1.0),
            FAILn=dict(fc=S.GREEN, ec=S.INK, lw=0.45, hatch="///", al=0.45),
            PASS=dict(fc=S.LIGHT, ec="white", lw=0.5, hatch=None, al=1.0),
            SKIP=dict(fc="none", ec=S.FAINT, lw=0.4, hatch=None, al=1.0))
IPAD = 0.085


def cell(ax_, cid, row, kind):
    st = CELL[kind]
    x0, y0 = XS[cid], row
    r = Rectangle((x0 + IPAD, y0 + IPAD), 1 - 2 * IPAD, 1 - 2 * IPAD,
                  facecolor=st["fc"], edgecolor=st["ec"], linewidth=st["lw"],
                  hatch=st["hatch"], alpha=st["al"], zorder=2, clip_on=False)
    if kind == "SKIP":
        r.set_linestyle((0, (1.2, 1.2)))
    ax_.add_patch(r)
    if kind == "SKIP":            # second encoding for "does not apply here"
        ax_.plot([x0 + 0.5], [y0 + 0.5], marker=".", ms=1.4, color=S.FAINT,
                 zorder=3, clip_on=False)


for c in COLS:
    for i, chk_ in enumerate(CHECKS):
        st = c["status"][chk_]
        kind = ("FAIL1" if chk_ == c["rejected_by"] else "FAILn") if st == "FAIL" else st
        cell(ax, c["id"], i, kind)
    if c["expected"]:                       # pre-registered target, drawn on top
        ax.plot([XS[c["id"]] + 0.5], [CHECKS.index(c["expected"]) + 0.5],
                marker="o", ms=2.6, mfc="none", mec="white", mew=0.9, zorder=4)

# --------------------------------------------- row labels + per-row fail loads --
for i, chk_ in enumerate(CHECKS):
    ax.text(-(GUT - 14.5) / COL_W_PT, i + 0.5, chk_, ha="right", va="center",
            fontsize=6.0, fontweight="bold", color=S.INK)
    ax.text(-(GUT - 16) / COL_W_PT, i + 0.5, GLOSS[chk_], ha="left", va="center",
            fontsize=5.5, color="#555555")
    n = M["load"][chk_]["FAIL"]
    first = M["first_reject"].get(chk_, 0)
    ax.text(NCU + (LOADW / 2) / COL_W_PT, i + 0.5, str(n), ha="center",
            va="center", fontsize=6.0, color=S.INK if first else S.VERMILION,
            fontweight="normal" if first else "bold")
# the count is every forgery the check brings down, first or not; it sums to 53
# over the 34 forgeries -- the 19 extras live in the multi-fail cascades.
ax.text(NCU + (LOADW / 2) / COL_W_PT, -0.30, "fails", ha="center", va="bottom",
        fontsize=5.5, color="#555555")

# ------------------------------------------- rotated column labels + brackets ---
for c in COLS:
    ax.text(XS[c["id"]] + 0.5, -0.28, CLAB[c["id"]], rotation=90, ha="center",
            va="bottom", fontsize=5.5, color=S.INK)
ytop = -(H_LAB + 2.0) / ROW_H
for key, lab in BANDS:
    xs = [XS[c["id"]] for c in COLS if c["band"] == key]
    x0, x1 = min(xs) + 0.06, max(xs) + 0.94
    ax.plot([x0, x1], [ytop, ytop], color=S.INK, lw=0.5, clip_on=False)
    ax.text((x0 + x1) / 2, ytop - 0.26, lab, ha="center", va="bottom",
            fontsize=5.6, color=S.INK, clip_on=False)
    if key != "F1":                        # band rule inside the matrix as well
        ax.plot([x0 - 0.06, x0 - 0.06], [0, len(CHECKS)], color=S.FAINT, lw=0.4,
                zorder=1)

# ------------------------------------------------------------------- legend -----
LEG = [("FAIL1", "first reject"), ("FAILn", "also fails"),
       ("PASS", "passes"), ("SKIP", "n/a")]
fig.canvas.draw()
ren = fig.canvas.get_renderer()


def tw(s, size):
    t = fig.text(0, 0, s, fontsize=size)
    w = t.get_window_extent(renderer=ren).width / fig.dpi / PT
    t.remove()
    return w


ly = (PADY + H_CONC + H_LEG / 2) * PT / H_IN
lx = PADX * PT / W_IN
SW = 6.4 * PT / W_IN
axl = fig.add_axes([0, 0, 1, 1], zorder=5)
axl.set_axis_off()
axl.set_xlim(0, 1)
axl.set_ylim(0, 1)
axl.patch.set_alpha(0)
for kind, lab in LEG:
    st = CELL[kind]
    r = Rectangle((lx, ly - SW / 2 * W_IN / H_IN), SW, SW * W_IN / H_IN,
                  facecolor=st["fc"], edgecolor=st["ec"], linewidth=st["lw"],
                  hatch=st["hatch"], alpha=st["al"], transform=axl.transAxes)
    if kind == "SKIP":
        r.set_linestyle((0, (1.2, 1.2)))
    axl.add_patch(r)
    lx += SW + 2.0 * PT / W_IN
    axl.text(lx, ly, lab, ha="left", va="center", fontsize=5.5, color=S.INK,
             transform=axl.transAxes)
    lx += (tw(lab, 5.5) + 7.0) * PT / W_IN
axl.plot([lx + 3.0 * PT / W_IN], [ly], marker="o", ms=2.6, mfc="none",
         mec=S.INK, mew=0.7, transform=axl.transAxes)
axl.text(lx + 7.0 * PT / W_IN, ly, "pre-registered target (coincides with the "
         "first reject on all 30)", ha="left", va="center", fontsize=5.5,
         color=S.INK, transform=axl.transAxes)

# ------------------------------------------------------- the concession band ----
band1 = ("no forgery is FIRST caught by %s (each fails only inside the "
         r"$-\nu$ / dangling-$\nu$ cascades)  ·  V6b prior-guard clause: "
         "0 of %d V6b failures"
         % (" or ".join(M["never_first"]), M["load"]["V6b"]["FAIL"]))
band2 = ("declared boundary: a PARTIALLY omitted DB blocking set (non-empty, "
         "all registered) is not rejected — only emptied (F4f) or alien (F4g) "
         "sets are")
axl.add_patch(Rectangle((PADX * PT / W_IN, PADY * PT / H_IN),
                        1 - 2 * PADX * PT / W_IN, (H_CONC - 1.5) * PT / H_IN,
                        facecolor="#F2F2F2", edgecolor=S.FAINT, lw=0.45,
                        transform=axl.transAxes, zorder=1))
for k, b in enumerate((band1, band2)):
    axl.text((PADX + 3.0) * PT / W_IN,
             (PADY + (H_CONC - 1.5) * (0.72 - 0.44 * k)) * PT / H_IN,
             b, ha="left", va="center", fontsize=5.5, color="#333333",
             transform=axl.transAxes, zorder=3)

out = os.path.join(HERE, "figB_forgery_matrix.pdf")
# Absolute point layout at exactly \textwidth; CreationDate=None keeps re-runs
# byte-reproducible.
with mpl.rc_context({"savefig.bbox": None}):
    fig.savefig(out, metadata={"CreationDate": None})
print("wrote", out)

# ---- what the figure asserts, printed so the caption can be checked against it --
assert M["n_expected_match"] == N_FORG and M["n_bases"] == N_BASES
assert M["families"] == FAMILY_SIZES
# V3 left the never-first set when F5 arrived: F5c/F5d are pre-registered to
# trip V3 (clause-(iv) variant swap), which is exactly what that family is for.
assert M["never_first"] == ["V2"] and M["never_fail"] == []
assert M["v6b_clause0_fails"] == 0
assert sum(M["first_reject"].values()) == N_FORG
for c in COLS:                                   # nothing overruns its allowance
    assert tw(CLAB[c["id"]], 5.5) < H_LAB - 2.4, (c["id"], tw(CLAB[c["id"]], 5.5))
for k, v in GLOSS.items():
    assert tw(k, 6.0) < 14.5 and tw(v, 5.5) < GUT - 18.0, (k, tw(v, 5.5))
for b in (band1, band2):
    assert tw(b, 5.5) < W_IN / PT - 2 * PADX - 6, (b, tw(b, 5.5))
f2 = [c for c in FORG if c["band"] == "F2"]
print("  %d forgeries rejected; first reject == pre-registered target in %d/%d"
      % (N_FORG, M["n_expected_match"], N_FORG))
print("  F2 band (per-field deletions): " + " | ".join(
    "%s->%s{%s}" % (c["id"], c["rejected_by"],
                    ",".join(k for k in CHECKS if c["status"][k] == "FAIL"))
    for c in f2))
print("  F4 band first rejects: %s" % {c["id"]: c["rejected_by"]
                                       for c in FORG if c["band"] == "F4"})
print("  never-first: %s ; V6b clause-0 fails: %d"
      % (M["never_first"], M["v6b_clause0_fails"]))
print("  >1 check fails: %s" % M["multi_fail"])
print("  bases: %s" % M["base_qids"])
print("  per-check fail loads: %s" % {c: M["load"][c]["FAIL"] for c in CHECKS})
print("  figure %.3f x %.3f in" % (W_IN, H_IN))
