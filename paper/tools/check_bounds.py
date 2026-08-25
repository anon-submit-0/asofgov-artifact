#!/usr/bin/env python3
"""Physical bounds check on the two-column PVLDB PDF.

Geometry is DERIVED, not guessed:
  \\paperwidth  = 612.0pt      (US Letter, acmart default)
  \\textwidth   = 506.295pt    (reported by acmart v2.19 + pvldb.sty)
  \\columnsep   = 24.0pt
  => \\columnwidth = (506.295 - 24)/2 = 241.1475pt
  => left  column  x in [ 52.8525, 294.0000]
  => right column  x in [318.0000, 559.1475]

Two defects are reported:
  OUT-OF-BOUNDS  a word whose right edge passes 559.1475
  CROSS-COLUMN   a word starting inside the left column that reaches
                 past 318.0, i.e. into the right column's text area

Hits are classified against the full-width regions of the page (the
\\maketitle title/author block, and any figure*/table* float, located by
its caption baseline), because those legitimately span both columns.
Only unclassified hits are typesetting defects.

TOL absorbs pdftotext's glyph-bbox rounding: a line-final hyphen or
em-dash is routinely reported ~1.6pt wide of the measure it is actually
set inside.
"""
import re, sys

path = sys.argv[1]
TOL = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

L_LEFT, L_RIGHT = 52.8525, 294.0
R_LEFT, R_RIGHT = 318.0, 559.1475

d = open(path, encoding='utf-8', errors='replace').read()
pages = re.split(r'<page ', d)[1:]
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
                  r'xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')

print(f"geometry: left col [{L_LEFT}, {L_RIGHT}]  right col [{R_LEFT}, {R_RIGHT}]"
      f"  gutter {R_LEFT-L_RIGHT:.1f}pt   tolerance {TOL}pt")

oob, cross = [], []
for pi, p in enumerate(pages, 1):
    ws = [(float(a), float(b), float(c), float(dd), e)
          for a, b, c, dd, e in WORD.findall(p)]

    # --- full-width regions on this page -----------------------------
    spans = []
    if pi == 1:
        # \maketitle block: everything above the first line of two-column
        # body matter.  A body line starts at the LEFT column's left edge AND
        # stays inside that column; a full-width title line can also start
        # there (a long title fills the measure), so flush-left alone is not
        # enough to identify the body -- the line must also NOT reach past
        # the left column's right edge.
        lines = {}
        for w in ws:
            lines.setdefault(round(w[1], 1), []).append(w)
        starts = [y for y, ln in lines.items()
                  if any(L_LEFT - 0.5 <= q[0] <= L_LEFT + 1.5 for q in ln)
                  and max(q[2] for q in ln) <= L_RIGHT + TOL]
        end = min(starts) - 1.0 if starts else 250.0
        spans.append(('title/author block (\\maketitle, full width)', 0.0, end))
    for w in ws:
        if w[4] in ('Figure', 'Table'):
            # caption baseline; a full-width float's caption starts in the
            # left column and its body extends past the gutter.
            cap_y = w[1]
            rows = [q for q in ws if cap_y - 1 <= q[1] <= cap_y + 60]
            if any(q[2] > R_LEFT for q in rows if q[0] < L_RIGHT):
                spans.append((f'{w[4]} caption band (full-width float)',
                              cap_y - 220.0, cap_y + 60.0))

    # Full-width caption/table LINES: a line that has substantial text on BOTH
    # sides of the gutter is float matter set at \textwidth (a body-text defect
    # only pokes past the gutter with the tail of one word).  This catches the
    # caption of a table* whose caption stands ABOVE a tall body, where the
    # fixed ±(220,60) band around the 'Table'/'Figure' word falls short.
    fullwidth_lines = set()
    lines = {}
    for w in ws:
        lines.setdefault(round(w[1], 0), []).append(w)
    for y, ln in lines.items():
        left_text = sum(1 for q in ln if q[2] < L_RIGHT)
        right_text = sum(1 for q in ln if q[0] > R_LEFT)
        if left_text >= 3 and right_text >= 3:
            fullwidth_lines.add(y)

    def classify(y):
        for name, y0, y1 in spans:
            if y0 <= y <= y1:
                return name
        if round(y, 0) in fullwidth_lines:
            return 'full-width line (text on both sides of the gutter)'
        return None

    for xmin, ymin, xmax, ymax, txt in ws:
        if xmax > R_RIGHT + TOL:
            oob.append((pi, xmax - R_RIGHT, txt, xmin, xmax, ymin, classify(ymin)))
        if xmin < L_RIGHT and xmax > R_LEFT + TOL:
            cross.append((pi, xmax - R_LEFT, txt, xmin, xmax, ymin, classify(ymin)))


def report(name, hits, edge):
    real = [h for h in hits if h[6] is None]
    print(f"\n{name} (>{TOL}pt past {edge}): {len(hits)} hit(s), "
          f"{len(real)} in single-column body text")
    for pi, over, txt, a, b, y, cls in sorted(hits, key=lambda t: -t[1]):
        tag = cls if cls else '*** BODY TEXT DEFECT ***'
        print(f"  p{pi}  +{over:6.2f}pt  {txt[:44]!r}  x[{a:.1f},{b:.1f}] y{y:.1f}   {tag}")
    return len(real)


a = report("OUT-OF-BOUNDS", oob, R_RIGHT)
b = report("CROSS-COLUMN", cross, R_LEFT)
print(f"\nRESULT: body-text out-of-bounds = {a}, body-text cross-column = {b}")
sys.exit(1 if (a or b) else 0)
