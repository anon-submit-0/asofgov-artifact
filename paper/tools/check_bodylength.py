#!/usr/bin/env python3
"""Column-aware body length, and the verdict against the 12-page limit.

Body = everything except the reference list (PVLDB hard rules: appendices and
acknowledgements count, references do not).  A body position is

    (page - 1) + (column * 626 + y - 84) / 1252

so one whole two-column page counts as 1.000.  The body length is the position
of the REFERENCES heading.

CAVEAT, and why the number bottoms out at ~12.001: a heading's baseline sits a
little below the top of its column, so when REFERENCES is the first thing on a
page the metric still reads a fraction over the whole-page value.  That residual
is the heading's own offset, not body text.  This script therefore reports the
raw figure AND the page the body actually ends on, and passes when the body
occupies at most 12 pages with nothing but references after it.

Usage: pdftotext -bbox main.pdf main.bbox && python3 tools/check_bodylength.py main.bbox
"""
import re, sys

LIMIT = 12
COL_TOP, COL_H = 84.0, 626.0
TOL = 6.0          # pt; a heading baseline this close to the top counts as "at the top"

W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
d = open(sys.argv[1], encoding='utf-8', errors='replace').read()
pages = re.split(r'<page ', d)[1:]

for pi, p in enumerate(pages, 1):
    for a, b, c, dd, e in W.findall(p):
        if e not in ('REFERENCES', 'References'):
            continue
        x, y = float(a), float(b)
        col = 0 if x < 294 else 1
        body = (pi - 1) + (col * COL_H + y - COL_TOP) / (2 * COL_H)
        at_top = (col == 0 and y - COL_TOP <= TOL)
        # pages the body actually occupies: if REFERENCES opens page pi, the body
        # ends on page pi-1; otherwise it runs into page pi.
        body_pages = pi - 1 if at_top else pi
        ok = body_pages <= LIMIT
        print(f"pages={len(pages)}  REFERENCES p{pi}{'L' if col == 0 else 'R'} "
              f"y={y:.1f}  =>  BODY = {body:.3f} pages  (limit {LIMIT})")
        note = ("  [REFERENCES opens p%d at the column top; the %.1f pt residual "
                "in the figure above is the heading's own baseline offset, not "
                "body text]" % (pi, y - COL_TOP)) if at_top else ""
        print(f"  body occupies pages 1-{body_pages}{note}")
        print(f"  VERDICT: {'PASS' if ok else 'FAIL'} "
              f"({body_pages} body page{'s' if body_pages != 1 else ''} of {LIMIT})")
        sys.exit(0 if ok else 1)

print("REFERENCES heading not found; pages =", len(pages))
sys.exit(2)
