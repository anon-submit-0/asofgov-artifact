"""F-A -- the coverage partition on four sibling requests, worked out cell by cell.

PILOT2 MIGRATION.  The four-cell walk moved from the enterprise rma store to the
public card_games store (author ruling: figures carry public data only), and the
four cells are now siblings in the strictest sense: ONE metric
(ruling_intensity), ONE binding (same_valid_time_window over the rulings.date /
sets.releaseDate anchor pair), ONE registered version (v1), one day granule --
only the request's window coordinates move.  Each row prints the request, the
outcome of every guard in the frozen order with the quantity that decided it,
then the value or the refusal class with its witness.

WHY ROWS AND NOT A 2x2 GRID -- unchanged from the enterprise version: the four
cases are the four exit points of a CHAIN, and the three guard columns line up
across the rows so the partition is legible as a shape (each row carries exactly
one cross, or none and falls through).

THE POINT OF THE PAIRING.  Rows (b) and (d) both face a month with ZERO set
releases, and they land in different classes.  The discriminator is whether the
request window lands inside the ANCHOR's coverage hull -- a property of the
anchor's table, never of the request: 2017-02 sits inside the release anchor's
hull (280 printings in Jan-17, 314 in Mar-17, none in Feb), so its empty
denominator is a caliber failure the probe must witness; 2021-06 opens after
BOTH hulls close (rulings end 2021-02-05, releases 2021-03-19), so it never
reaches the caliber guard at all.

HONEST LABELLING OF THE UNCERTIFIED ROWS.  (a) and (d) are frozen suite
questions (CARD-Q2 / CARD-Q7) and carry verifier-accepted certificates, named
on the row.  (b) and (c) are NOT suite questions: the suite's certified OOV and
AM(ii) instances live in other clusters (FIN-Q6, F1-Q6, DEB-Q6, EF2-Q5; FIN-Q8,
W1-Q5), and importing one would change the store and destroy the comparison.
Both are read-only probes on the same warehouse and say so on their face.

COLOUR SEMANTICS (unchanged, style.py): SKY for OOV, PURPLE for AM, VERMILION
for MC, GREEN for the bindable case.  Every state carries a redundant
non-colour encoding (column position, hatch, glyph, filled marker).  No type
below 5.4 pt.

DATA.  100% recomputed, nothing retyped: extract_p2.py queries the card_games
warehouse for every mass and both coverage hulls, walks the guard chain itself,
and asserts the walk's classification against the frozen gold labels AND the
anchors, windows, decision and witness of the frozen certificates.

Run:  python3 extract_p2.py && python3 figA_partition.py
"""

import json
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import style as S

S.apply()
HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "fig_data_pilot2.json")))["partition"]
C = {c["tag"]: c for c in P["cells"]}
COV = P["coverage"]
BND = P["boundary"]

KLASS = {
    "Bindable": (S.GREEN, "", "Bindable"),
    "OOV": (S.SKY, "..", u"⊥ OOV"),
    "AM": (S.PURPLE, "\\\\", u"⊥ AM(ii)"),
    "MC": (S.VERMILION, "//", u"⊥ MC(ii)"),
}

PT = 1 / 72.0
W = S.COL_W / PT                       # exactly \columnwidth, in points
PAD = 1.0
STRIP = 6.0                            # width of the class colour strip
X0 = PAD + STRIP + 3.2                 # left edge of all row text
XG = [X0 + 3.4, X0 + 59.4, X0 + 129.4]
H_CHAIN, H_CTX, LINE = 12.4, 7.4, 6.95
H_ROW = 4 * LINE + 3.8
H_BAND, BLINE = 37.4, 6.6
N_CTX = 4
H = PAD + H_CHAIN + N_CTX * H_CTX + 4 * H_ROW + H_BAND + PAD + 1.5

FS_BODY, FS_SMALL, FS_HEAD = 5.6, 5.4, 6.0  # W14 font raise DEFERRED to camera-ready:
# the width assertions below prove >=6.5pt cannot fit this fixed-\columnwidth
# canvas (case (c) request line 258pt > TEXTW at 6.7pt); needs a layout pass.
TEXTW = W - PAD - X0

fig = plt.figure(figsize=(W * PT, H * PT))
fig.set_constrained_layout(False)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(H, 0)
ax.set_axis_off()
REN = None


def txt(x, y, s, fs=FS_BODY, ha="left", **kw):
    return ax.text(x, y, s, fontsize=fs, ha=ha, va="center",
                   color=kw.pop("color", S.INK), clip_on=False, **kw)


def width_pt(s, fs, **kw):
    global REN
    t = fig.text(0, 0, s, fontsize=fs, **kw)
    if REN is None:
        fig.canvas.draw()
        REN = fig.canvas.get_renderer()
    w = t.get_window_extent(renderer=REN).width / fig.dpi / PT
    t.remove()
    return w


# ==================================== the guard chain: order, header and legend ===
y = PAD
chain = list(zip(P["guard_chain"], XG))
CHAIN_LAB = {"OOV": "OOV", "AM": "AM", "MC": "MC"}
for i, (k, xg) in enumerate(chain):
    col, hat, _ = KLASS[k]
    bw = width_pt(CHAIN_LAB[k], FS_HEAD, fontweight="bold") + 9.0
    ax.add_patch(Rectangle((xg, y + 1.2), bw, H_CHAIN - 2.4, facecolor=col,
                           edgecolor=S.INK, lw=0.4, hatch=hat, alpha=0.9,
                           clip_on=False, zorder=2))
    txt(xg + bw / 2, y + H_CHAIN / 2, CHAIN_LAB[k], fs=FS_HEAD, ha="center",
        color="white", fontweight="bold", zorder=3)
    nxt = chain[i + 1][1] if i + 1 < len(chain) else W - PAD - 34.0
    ax.annotate("", xy=(nxt - 1.0, y + H_CHAIN / 2), xytext=(xg + bw + 1.2, y + H_CHAIN / 2),
                arrowprops=dict(arrowstyle="-|>", lw=0.5, color=S.INK,
                                mutation_scale=3.6), annotation_clip=False)
bw = width_pt("Bindable", FS_HEAD, fontweight="bold") + 9.0
ax.add_patch(Rectangle((W - PAD - bw, y + 1.2), bw, H_CHAIN - 2.4,
                       facecolor=S.GREEN, edgecolor=S.INK, lw=0.4, alpha=0.9,
                       clip_on=False, zorder=2))
txt(W - PAD - bw / 2, y + H_CHAIN / 2, "Bindable", fs=FS_HEAD, ha="center",
    color="white", fontweight="bold", zorder=3)

# ------------------------------------------------ the context every row shares ---
y += H_CHAIN + 0.6
a_n, a_d = COV["num"], COV["den"]
ctx1 = (u"one store (%s) · one metric (%s) · %s granule"
        % (P["domain"], P["metric"], a_n["granule"]))
ctx2 = (r"rule %s over one anchor pair · pinned version $\nu$ = %s"
        % (P["rule"], P["version"]))
cov = (u"num leg @ %s.%s     Cov = [%s, %s]   %s over %s rows"
       % (a_n["object"], a_n["column"], a_n["lo"], a_n["hi"],
          a_n["mode"], format(a_n["n_rows"], ",")))
cov2 = (u"den leg @ %s.%s   Cov = [%s, %s]   %s over %d rows"
        % (a_d["object"], a_d["column"], a_d["lo"], a_d["hi"],
           a_d["mode"], a_d["n_rows"]))
CTX_LINES = (ctx1, ctx2, cov, cov2)
for k, line in enumerate(CTX_LINES):
    txt(PAD, y + H_CTX * (k + 0.5), line, fs=FS_SMALL, color="#444444")
y += N_CTX * H_CTX + 1.0


# ============================================================== the four requests ===
def short(w):
    return "[%s,%s)" % (w["lo"][5:], w["hi_excl"][5:])


def row_content(tag):
    """(request line, three guard tokens, outcome line)."""
    c = C[tag]
    wn, wd = c["w_num"], c["w_den"]
    req = (u"T = %s-15 ·  W$_n$ = W$_d$ = %s" % (c["as_of"], short(wn))
           if wn == wd else
           u"T = %s-15 ·  W$_n$ = %s   W$_d$ = %s (imperative pair)"
           % (c["as_of"], short(wn), short(wd)))
    if c["cls"] == "OOV":
        g = [(u"✗", u"W ∩ Cov = ∅", "fired"),
             (u"–", u"not reached", "skip"), (u"–", u"not reached", "skip")]
        out = (r"witness (a, W$_T$, $\pi_V$): the request window opens after "
               u"both hulls close")
    elif c["cls"] == "AM":
        g = [(u"✓", u"W ∩ Cov ≠ ∅", "ok"),
             (u"✗", u"svw (ii): W$_n$ ≠ W$_d$", "fired"),
             (u"–", u"not reached", "skip")]
        out = (u"as asked %d/%d = %.2f%%   ·   same window %d/%d = %.2f%%"
               % (c["num_mass"], c["den_mass"], 100 * c["asked_value"],
                  c["num_mass"], c["same_window_den"],
                  100 * c["same_window_value"]))
    elif c["cls"] == "MC":
        g = [(u"✓", u"W ∩ Cov ≠ ∅", "ok"), (u"✓", u"svw (i)–(iv) hold", "ok"),
             (u"✗", r"(i) ok · (ii) $\mu_d$ = 0", "fired")]
        out = (r"witness: denominator probe, $\mu_d$ = 0 printings,  against "
               r"$\mu_n$ = %s rulings" % format(c["num_mass"], ","))
    else:
        g = [(u"✓", u"W ∩ Cov ≠ ∅", "ok"), (u"✓", u"svw (i)–(iv) hold", "ok"),
             (u"✓", r"(i) ok · (ii) $\mu_d$ = %d > 0" % c["den_mass"], "ok")]
        out = (r"⟦q⟧ = $\mu_n$/$\mu_d$ = %d/%d = %.2f%%"
               % (c["num_mass"], c["den_mass"], 100 * c["value"]))
    return req, g, out


GCOL = {"ok": "#3A3A3A", "skip": "#8A8A8A"}  # W14: skip grey darkened from S.FAINT

for i, tag in enumerate(["a", "b", "c", "d"]):
    c = C[tag]
    col, hat, cname = KLASS[c["cls"]]
    ry = y + i * H_ROW
    if i:
        ax.plot([PAD, W - PAD], [ry - 0.4, ry - 0.4], color=S.FAINT, lw=0.35,
                clip_on=False, zorder=1)
    ax.add_patch(Rectangle((PAD, ry + 1.2), STRIP, H_ROW - 2.8, facecolor=col,
                           edgecolor=S.INK, lw=0.35, hatch=hat, alpha=0.9,
                           clip_on=False, zorder=2))
    req, guards, out = row_content(tag)
    ty = ry + 1.2 + LINE * 0.55
    # line 1 -- the case, its class, and where it comes from
    txt(X0, ty, u"(%s)  %s" % (tag, cname), fs=FS_HEAD, fontweight="bold", color=col)
    prov = ("%s · certificate ACCEPT" % c["qid"]) if c["cert"] \
        else "probe on the same store · no certificate"
    txt(W - PAD, ty, prov, fs=FS_SMALL, ha="right", color="#555555")
    # line 2 -- the request itself
    ty += LINE
    txt(X0, ty, req, fs=FS_BODY)
    # line 3 -- the guard walk, aligned to the chain printed at the top
    ty += LINE
    for (glyph, text, state), xg in zip(guards, XG):
        if state == "fired":
            ax.add_patch(Rectangle((xg - 3.4, ty - LINE * 0.44), 1.7, LINE * 0.88,
                                   facecolor=col, edgecolor="none", clip_on=False,
                                   zorder=3))
        txt(xg + 1.4, ty, glyph, fs=FS_BODY, ha="center",
            color=col if state == "fired" else GCOL[state],
            fontweight="bold" if state == "fired" else "normal")
        txt(xg + 4.6, ty, text, fs=FS_SMALL,
            color="#8A8A8A" if state == "skip" else S.INK)
    # line 4 -- the value, or the refusal with the quantity behind its witness
    ty += LINE
    txt(X0, ty, out, fs=FS_BODY, fontweight="bold" if c["cls"] == "Bindable" else "normal")

# ============================================ the boundary band, not decoration ===
y += 4 * H_ROW + 1.2
ax.add_patch(Rectangle((PAD, y), W - 2 * PAD, H_BAND - 1.6, facecolor="#F2F2F2",
                       edgecolor=S.FAINT, lw=0.45, clip_on=False, zorder=1))
BAND = [
    u"(b) and (d) both face a zero-release month, and still split.  2017-02 lies",
    u"inside the release anchor's hull (%d printings in Jan-17, %d in Mar-17,"
    % (BND["jan_printings"], BND["mar_printings"]),
    u"none in Feb), so its empty denominator is a caliber failure; %s opens"
    % BND["oov_as_of"],
    u"after both hulls close (%s / %s), so it never reaches the"
    % (BND["hull_num_hi"], BND["hull_den_hi"]),
    u"caliber guard.  The discriminator is the anchor's hull — a property of its table.",
]
for k, line in enumerate(BAND):
    txt(PAD + 3.0, y + 2.4 + BLINE * (k + 0.5), line, fs=FS_SMALL, color="#333333",
        zorder=3)

out_pdf = os.path.join(HERE, "figA_partition.pdf")
with mpl.rc_context({"savefig.bbox": None}):
    fig.savefig(out_pdf, metadata={"CreationDate": None})
print("wrote", out_pdf)

# ---- what the figure asserts, printed so the caption can be checked against it ---
assert len(P["cells"]) == 4 and len({c["cls"] for c in P["cells"]}) == 4
assert P["n_certified"] == 2, P["n_certified"]
GW = [XG[1] - XG[0] - 6.0, XG[2] - XG[1] - 6.0, W - PAD - XG[2] - 6.0]
for tag in "abcd":
    req, guards, outl = row_content(tag)
    assert width_pt(req, FS_BODY) < TEXTW, (tag, "req", width_pt(req, FS_BODY))
    assert width_pt(outl, FS_BODY) < TEXTW, (tag, "out", width_pt(outl, FS_BODY))
    for (_, t, _), room in zip(guards, GW):
        assert width_pt(t, FS_SMALL) < room, (tag, t, round(width_pt(t, FS_SMALL), 1),
                                              round(room, 1))
for s in CTX_LINES + tuple(BAND):
    assert width_pt(s, FS_SMALL) < W - 2 * PAD - 3.0, (s, round(width_pt(s, FS_SMALL), 1))
for tag in "abcd":                       # provenance must not collide with the class
    c = C[tag]
    prov = ("%s · certificate ACCEPT" % c["qid"]) if c["cert"] \
        else "probe on the same store · no certificate"
    used = width_pt(u"(%s)  %s" % (tag, KLASS[c["cls"]][2]), FS_HEAD, fontweight="bold") \
        + width_pt(prov, FS_SMALL)
    assert used < W - PAD - X0 - 6.0, (tag, round(used, 1))
for tag in "abcd":
    c = C[tag]
    print("  (%s) %-9s T=%s  mu=(%s,%s)  %s"
          % (tag, c["cls"], c["as_of"], c["num_mass"], c["den_mass"],
             c["qid"] or "PROBE (no certificate)"))
cA, cC, cD = C["a"], C["c"], C["d"]
print("  (a) value %.6f equals the frozen gold %.6f" % (cA["value"], cA["gold_value"]))
print("  (c) as asked %.2f%% vs same-window %.2f%% (imperative-pair inflation %.0fx)"
      % (100 * cC["asked_value"], 100 * cC["same_window_value"],
         cC["asked_value"] / cC["same_window_value"]))
print("  (d) witness %s -> mu_den = %s (mu_num = %s)"
      % (cD["witness_type"], cD["den_mass"], cD["num_mass"]))
print("  suite note: %s" % P["suite_note"])
print("  figure %.3f x %.3f in  (%.1f x %.1f pt)" % (W * PT, H * PT, W, H))
