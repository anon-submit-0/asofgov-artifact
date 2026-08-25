#!/usr/bin/env python3
"""Map Overfull \\hbox warnings in main.log back to the .tex file that produced them."""
import re, sys

log = sys.argv[1] if len(sys.argv) > 1 else 'main.log'
d = open(log, encoding='utf-8', errors='replace').read()
lines = d.split('\n')
filere = re.compile(r'\((\.?/?[^()\s]*\.(?:tex|sty|cls|def|cfg|clo|bbl|aux|out|fd))')
stack = []
out = []
for i, l in enumerate(lines):
    j = 0
    while j < len(l):
        c = l[j]
        if c == '(':
            m = filere.match(l, j)
            if m:
                stack.append(m.group(1)); j = m.end(); continue
            stack.append('?'); j += 1; continue
        if c == ')':
            if stack: stack.pop()
            j += 1; continue
        j += 1
    if 'Overfull' in l:
        f = [s for s in stack if s.endswith('.tex') and 'texmf' not in s]
        pts = re.search(r'\(([\d.]+)pt', l)
        rng = re.search(r'at lines (\d+)--(\d+)', l)
        ctx = ' '.join(lines[i+1:i+5])
        # strip font switches for readability
        ctx = re.sub(r'\\[A-Za-z0-9/.]+(/[A-Za-z0-9.()-]+)*', ' ', ctx)
        ctx = re.sub(r'\s+', ' ', ctx)[:170]
        out.append((float(pts.group(1)) if pts else 0.0,
                    f[-1] if f else '??',
                    rng.groups() if rng else ('?', '?'), ctx))
out.sort(key=lambda t: -t[0])
print(f"{len(out)} overfull hbox")
for pts, f, rng, ctx in out:
    print(f"{pts:8.2f}pt  {f}:{rng[0]}--{rng[1]}")
    print(f"           {ctx}")
