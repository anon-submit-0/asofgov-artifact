# -*- coding: utf-8 -*-
"""authored 内容确定性生成规则（DESIGN_SPEC §6.2）。
- world_1.country_history: 84 月 x 239 国；population(code,m)=half_up(P0*(1+g)^dm)，
  g 由 sha1(code) 前 8 hex 映射到 [-0.4%, +0.8%] 月增长率；GNP 同法(sha1(code+':gnp'))。
  population_resident: Continent='Asia' 行 population x1.06 半上取整（v2 常住口径重定基），其余等值。
- formula_1.points_scheme: PS2009 / PS2010 两套积分映射（真实历史口径）。
全部合成行 authored=true；随机性为零（SHA1 确定），种子标注 20260731。
"""
import hashlib

SEED_NOTE = "seed=20260731; deterministic via sha1, no RNG state"

def _rate(key, lo=-0.004, hi=0.008):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return lo + (hi - lo) * (int(h, 16) / 0xFFFFFFFF)

def half_up(x):
    import math
    return int(math.floor(x + 0.5))

def months(start="2020-01", n=84):
    y, m = int(start[:4]), int(start[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out

def gen_world1_history(country_rows):
    """country_rows: [(Code, Continent, Population, GNP)] -> country_history rows."""
    ms = months()
    rows = []
    for code, cont, p0, gnp0 in country_rows:
        gp = _rate(code)
        gg = _rate(code + ":gnp")
        p0 = p0 or 0
        gnp0 = gnp0 or 0.0
        for i, m in enumerate(ms):
            pop = half_up(p0 * ((1 + gp) ** i))
            gnp = round(gnp0 * ((1 + gg) ** i), 2)
            pop_res = half_up(pop * 1.06) if cont == "Asia" else pop
            rows.append((code, m, pop, pop_res, gnp, True))
    return rows

POINTS_SCHEMES = {
    # 真实历史口径：2009 赛季前八名积分制；2010 起前十名积分制
    "PS2009": {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1},
    "PS2010": {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1},
}

def gen_points_scheme_rows():
    rows = []
    for sid in sorted(POINTS_SCHEMES):
        for pos in sorted(POINTS_SCHEMES[sid]):
            rows.append((sid, pos, float(POINTS_SCHEMES[sid][pos]), True))
    return rows
