# -*- coding: utf-8 -*-
"""ND-2 禁字段/SQL片段闸 + ND-3 干扰行密度闸（DESIGN_SPEC §3.2）。

ND-2：gov_seed 十表 jsonl 全量扫描——
  字段名黑名单 select_expr/where_expr/sql/sql_template/expr/filter_sql/snapshot_table/
  valid_from/valid_to/gold_*；一切字符串值不得匹配
  /\\b(SELECT|FROM|WHERE|GROUP BY|JOIN)\\b|SUM\\(|COUNT\\(|AVG\\(/i。零命中方绿。
ND-3：路径 B 解析器全题触达行集（dualpath_report.json）对种子全量的补集占比 ≥30%。
"""
import os, sys, json, re, glob

ROOT = "/Volumes/SSD 1/explore_opportunity_cc/pilot2"
BANNED_FIELDS = {"select_expr", "where_expr", "sql", "sql_template", "expr",
                 "filter_sql", "snapshot_table", "valid_from", "valid_to"}
SQL_RE = re.compile(r"\b(SELECT|FROM|WHERE|GROUP BY|JOIN)\b|SUM\(|COUNT\(|AVG\(", re.I)


def scan_value(v, path, hits):
    if isinstance(v, str):
        if SQL_RE.search(v):
            hits.append(("sql_fragment", path, v))
    elif isinstance(v, dict):
        for k, x in v.items():
            scan_value(x, f"{path}.{k}", hits)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            scan_value(x, f"{path}[{i}]", hits)


def nd2():
    hits = []
    files = sorted(glob.glob(os.path.join(ROOT, "domains", "*", "gov_seed", "*.jsonl")))
    n_rows = 0
    for f in files:
        for ln, line in enumerate(open(f, encoding="utf-8")):
            line = line.strip()
            if not line:
                continue
            n_rows += 1
            row = json.loads(line)
            for k, v in row.items():
                if k in BANNED_FIELDS or k.startswith("gold_"):
                    hits.append(("banned_field", f"{os.path.basename(f)}:{ln+1}", k))
                scan_value(v, f"{os.path.basename(f)}:{ln+1}.{k}", hits)
    return {"files": len(files), "rows": n_rows, "hits": hits, "pass": not hits}


def nd3():
    rep = json.load(open(os.path.join(ROOT, "build", "dualpath_report.json")))
    per_dom, tot_all, tot_touch = {}, 0, 0
    for dom, totals in rep["seed_totals"].items():
        n_all = sum(totals.values())
        touched = rep["touched_by_domain"].get(dom, [])
        n_touch = len(set(map(tuple, touched)))
        per_dom[dom] = {"total": n_all, "touched": n_touch,
                        "distractor_ratio": round(1 - n_touch / n_all, 4) if n_all else None}
        tot_all += n_all
        tot_touch += n_touch
    ratio = 1 - tot_touch / tot_all
    return {"per_domain": per_dom, "total_rows": tot_all, "touched_rows": tot_touch,
            "global_distractor_ratio": round(ratio, 4), "threshold": 0.30,
            "pass": ratio >= 0.30}


def main():
    r2, r3 = nd2(), nd3()
    out = {"ND2": r2, "ND3": r3, "pass": r2["pass"] and r3["pass"]}
    with open(os.path.join(ROOT, "ci", "nondegeneracy_report.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[ND-2] files={r2['files']} rows={r2['rows']} hits={len(r2['hits'])} -> "
          f"{'PASS' if r2['pass'] else 'FAIL'}")
    for h in r2["hits"][:20]:
        print("   ", h)
    print(f"[ND-3] touched={r3['touched_rows']}/{r3['total_rows']} "
          f"distractor={r3['global_distractor_ratio']:.1%} (>=30%) -> "
          f"{'PASS' if r3['pass'] else 'FAIL'}")
    for dm, v in sorted(r3["per_domain"].items()):
        print(f"    {dm:26s} {v['touched']:>4}/{v['total']:>4} distractor={v['distractor_ratio']:.1%}")
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
