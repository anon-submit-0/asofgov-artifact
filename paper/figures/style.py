"""Project-wide figure style sheet (PVLDB Vol.20 submission).

Single source of truth for: colour semantics, hatch/marker encodings, font sizes,
figure widths.  Imported by every fig*.py so a colour never drifts between
figures (figures-SOP hard convention #1).

Colour semantics -- FIXED for the whole paper, never reassign:
  * plain LLM baseline           -> BLUE      (#0072B2)
  * prompt-engineered baseline   -> ORANGE    (#E69F00)
  * governance-informed baseline -> INK       (#222222)   <- B6 arm; see note below
  * our mechanism (compiler)     -> GREEN     (#009E73)   <- ours, most saturated,
                                                             thickest stroke
  * "answered-should-refuse"     -> VERMILION (#D55E00)   headline failure mode
  * wrong value                  -> PURPLE    (#CC79A7)
  * execution error              -> GREY      (#8C8C8C)
  * over-refusal                 -> SKY       (#56B4E9)
  * correct                      -> LIGHT     (#E4E4E4)

Palette is Okabe-Ito (colour-vision-deficiency safe).  Every colour-coded mark
carries a second, redundant encoding (hatch for bars, linestyle+marker for
lines) so the figures survive greyscale printing (hard convention #2).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl

# ---------------------------------------------------------------- palette ---
BLUE = "#0072B2"   # plain baseline (LLM, no governance)
ORANGE = "#E69F00"   # prompt-engineered baseline
GREEN = "#009E73"   # OURS: binding compiler + disclosure gate
VERMILION = "#D55E00"   # failure: answered-should-refuse
PURPLE = "#CC79A7"   # failure: wrong value
GREY = "#8C8C8C"   # failure: execution error
SKY = "#56B4E9"   # failure: over-refusal (refused-should-answer)
LIGHT = "#E4E4E4"   # correct
INK = "#222222"
FAINT = "#BFBFBF"

# system-class -> (colour, hatch, marker, linestyle, linewidth, zorder-boost)
CLASS_STYLE = {
    "plain":     dict(color=BLUE,   hatch="",     marker="o", ls="--", lw=1.2),
    "prompt":    dict(color=ORANGE, hatch="//",   marker="s", ls=":",  lw=1.2),
    "governed":  dict(color=INK,    hatch="\\\\", marker="^", ls="-.", lw=1.2),
    "mechanism": dict(color=GREEN,  hatch="",     marker="D", ls="-",  lw=1.8),
}
# Why INK for the governance-informed class, rather than a fifth hue: the four
# remaining Okabe-Ito colours (VERMILION/PURPLE/GREY/SKY) are each already bound
# to a FAILURE class, and the system-class key and the taxonomy segments appear
# inside the same axes in Fig.3 -- reusing one would make a bracket colour and a
# bar colour mean two different things in one figure.  Okabe-Ito's remaining
# unused members are yellow (#F0E442, illegible as small type on white) and
# black, so black is the only admissible addition.  No existing binding moved.

# failure taxonomy -> (colour, hatch, display label)  [order = stacking order]
# no_sql is the sixth class of the pilot2 frozen scorer (an empty or SQL-free
# response on a value question; empty responses on refusal questions score as
# answered-should-refuse).  White fill + dense cross-hatch keeps it legible in
# greyscale and unmistakable next to the grey execution-error class.
TAXONOMY = [
    ("answered_should_refuse", VERMILION, "//",  "answered-should-refuse"),
    ("wrong_value",            PURPLE,    "\\\\", "wrong value"),
    ("execution_error",        GREY,      "xx",  "execution error"),
    ("refused_should_answer",  SKY,       "..",  "over-refusal"),
    ("no_sql",                 "#FFFFFF", "++",  "no SQL"),
    ("correct",                LIGHT,     "",    "correct"),
]

# refusal-class colours (used in Fig.1/Fig.2 and the certificate table legend)
REFUSAL = {"MC": VERMILION, "AM": PURPLE, "OOV": SKY, "DB": GREY}

# ------------------------------------------------------------------ sizes ---
COL_W = 3.35    # PVLDB single-column width (inch)
FULL_W = 7.00    # PVLDB two-column (full) width (inch)


def apply():
    """Install the shared rcParams.  Call once at the top of every figure script."""
    mpl.rcParams.update({
        # vector output, embedded Type-42 (TrueType) fonts -- no bitmaps
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "figure.dpi": 300,
        "savefig.format": "pdf",
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.01,
        # in-figure type ~= body type after placement; >= 7.5pt everywhere.
        # Floor raised 2026-08-27 (FIGURE_REDESIGN_SPEC v1 §6.1): the body
        # figures are reflowed so 7.5pt fits at \columnwidth; this default is
        # the single source of truth for that floor.  The three body scripts
        # (fig1_asof_gap, fig2_certchain, fig3_paired_stratified) additionally
        # set every literal fontsize>=7.5.  Legacy/TR scripts pass explicit
        # fs= for their small type and are unaffected by this default.
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 7.5,
        "axes.titlesize": 8.0,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5,
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.columnspacing": 1.0,
        "legend.handletextpad": 0.5,
        # strong-paper look: no top/right spines, thin axes
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "axes.edgecolor": INK,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "lines.linewidth": 1.2,
        "lines.markersize": 3.0,
        "hatch.linewidth": 0.5,
        "grid.linewidth": 0.4,
        "grid.color": FAINT,
        "errorbar.capsize": 2.0,
        "figure.constrained_layout.use": True,
    })


def pct(x, digits=1):
    """Format a rate in [0,1] as a percentage string."""
    return f"{100.0 * x:.{digits}f}%"
