# -*- coding: utf-8 -*-
"""A2 泄漏纪律比对（DESIGN_SPEC §3.4）+ 双路径零共享自检。

1) 字段分区：questions.json 每题字段 = 评测可见集 ∪ 金标侧集，两集不交；
   评测可见集 = {qid, domain, question_zh, as_of, declared_at, metric_alias, scope,
   pinned_version, cross_window, anchor_override, window_request, requested_granularity,
   requested_time_gran, presentation, ctx_role, periods}。
2) 运行时投影：dualpath_check 只向路径 B 传可见投影（其内部有断言）；本闸静态复核
   路径 B 源码不引用金标侧字段名，也不 import 出题定义模块；
3) 双路径 import 零交集（呼应 impl ci_check 红线的 pilot2 本地对应）。
"""
import os, sys, json, re, glob, ast

ROOT = "/Volumes/SSD 1/explore_opportunity_cc/pilot2"
VISIBLE = {"qid", "domain", "question_zh", "as_of", "declared_at", "metric_alias", "scope",
           "pinned_version", "cross_window", "anchor_override", "window_request",
           "requested_granularity", "requested_time_gran", "presentation", "ctx_role",
           "periods"}
GOLD = {"metric", "expected_kind", "refusal_reason", "refusal_subtype", "rewrite",
        "gold_sql", "gold_value", "windows", "windows_note", "notes"}


def imports_of(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split(".")[0])
    return out


def main():
    problems = []
    n = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "domains", "*", "questions.json"))):
        for q in json.load(open(f)):
            n += 1
            keys = set(q.keys())
            extra = keys - VISIBLE - GOLD
            if extra:
                problems.append((q["qid"], "unclassified fields", sorted(extra)))
            if VISIBLE & GOLD:
                problems.append((q["qid"], "field sets overlap", []))
            # 金标值不得出现在题面（弱检查：整数金标）
            if isinstance(q.get("gold_value"), int) and abs(q["gold_value"]) > 30:
                if str(q["gold_value"]) in q["question_zh"]:
                    problems.append((q["qid"], "gold literal leaked into question_zh", []))

    src_b = open(os.path.join(ROOT, "build", "govchain_resolver.py"), encoding="utf-8").read()
    for bad in ["gold_sql", "gold_value", "_gold", "expected_kind", "questions_def"]:
        if re.search(r"\b" + re.escape(bad) + r"\b", src_b):
            problems.append(("govchain_resolver.py", "references gold-side token", [bad]))

    imp_a = imports_of(os.path.join(ROOT, "build", "questions_def.py"))
    imp_b = imports_of(os.path.join(ROOT, "build", "govchain_resolver.py"))
    inter = (imp_a & imp_b) - {"__future__"}
    rep = {"n_questions": n, "problems": problems,
           "pathA_imports": sorted(imp_a), "pathB_imports": sorted(imp_b),
           "import_intersection": sorted(inter),
           "pass": not problems and not inter}
    with open(os.path.join(ROOT, "ci", "leak_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(f"[leak] n={n} problems={len(problems)} importsA={sorted(imp_a)} "
          f"importsB={sorted(imp_b)} inter={sorted(inter)} -> "
          f"{'PASS' if rep['pass'] else 'FAIL'}")
    for p in problems[:20]:
        print("   ", p)
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
