#!/usr/bin/env python3
"""Column-aware page cost of every section in the built PDF.

Same rule as tools/check_bodylength.py: a body position is
    (page-1) + (column*626 + y - 84) / 1252
so one whole two-column page counts as 1.000.  The delta between consecutive
headings is the page cost of a section -- the only measurement a cut may be
judged by, since sub-column trims are absorbed by \flushbottom glue and do not
convert into pages.

Usage: python3 tools/section_map.py <main.bbox>
"""
import re, sys

HEADS = ["INTRODUCTION", "BI-TEMPORAL", "BINDING", "DISCLOSURE-CONSTRAINED",
         "POINT-IN-TIME", "SYSTEM", "EVALUATION", "RELATED", "CONCLUSION,",
         "REFERENCES"]
W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
d = open(sys.argv[1], encoding='utf-8', errors='replace').read()
pages = re.split(r'<page ', d)[1:]

hits, seen = [], set()
for pi, p in enumerate(pages, 1):
    for a, b, c, dd, e in W.findall(p):
        if e in HEADS and e not in seen:
            seen.add(e)
            col = 0 if float(a) < 294 else 1
            hits.append(((pi - 1) + (col * 626.0 + float(b) - 84.0) / 1252.0, e, pi))
hits.sort()
for (p0, n0, pg), (p1, _, _) in zip(hits, hits[1:]):
    print(f"  {n0:<26s} starts p{pg:<3d} body {p0:6.3f}   costs {p1 - p0:6.3f} pages")
print(f"  {hits[-1][1]:<26s} starts p{hits[-1][2]:<3d} body {hits[-1][0]:6.3f}"
      f"   <-- BODY LENGTH (limit 12.000)")
