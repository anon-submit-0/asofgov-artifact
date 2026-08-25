# -*- coding: utf-8 -*-
"""pilot2 总控建库：9 库 warehouse + gov_seed 十表 + provenance + 60 题金标物化（路径 A）。
可重跑、确定性、幂等（整库重建）。用法：
  python3 build_all.py            # 全部 9 库 + 出题
  python3 build_all.py financial  # 单库（供 extract_<db>.py 薄封装调用）
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import duckdb
import lib_build as L
import synth_rules as S
from seeds_def import SEED_BUILDERS
from questions_def import QUESTIONS, WINDOWS_NOTE, VISIBLE_FIELDS


def build_domain(domain):
    d = L.dom_dir(domain)
    wpath = os.path.join(d, "warehouse.duckdb")
    if os.path.exists(wpath):
        os.remove(wpath)
    con = duckdb.connect(wpath)
    prov = {"domain": domain, "built_at": L.now_utc(),
            "extraction": "duckdb sqlite scanner ATTACH + CREATE TABLE AS (原值拷贝)",
            "tables": {}, "authored_rules": None, "source": None}

    if domain == "world_1":
        src = L.W1_SRC_DUCK
        prov["source"] = {"kind": "spider_dev_via_pilot_public_extract", "path": src,
                          "sha256": L.sha256_file(src),
                          "note": "country 239 行为 Spider dev world_1.country 原值（经旧公共轨抽取件承接，血缘簇）"}
        prov["extraction"] = "duckdb ATTACH 旧公共轨 warehouse（country_v2026_01 即 Spider 原值）"
        con.execute(f"ATTACH '{src}' AS legacy (READ_ONLY)")
        con.execute('CREATE TABLE country AS SELECT "Code","Name","Continent","Region",'
                    '"SurfaceArea","IndepYear","Population","LifeExpectancy","GNP" '
                    'FROM legacy.country_v2026_01')
        con.execute("DETACH legacy")
        n = con.execute("SELECT COUNT(*) FROM country").fetchone()[0]
        prov["tables"]["country"] = {"rows": n, "authored": False}
        rows = con.execute('SELECT "Code","Continent","Population","GNP" FROM country ORDER BY "Code"').fetchall()
        hist = S.gen_world1_history(rows)
        con.execute("CREATE TABLE country_history (code VARCHAR, effective_month VARCHAR, "
                    "population BIGINT, population_resident BIGINT, gnp DOUBLE, authored BOOLEAN)")
        con.executemany("INSERT INTO country_history VALUES (?,?,?,?,?,?)", hist)
        prov["tables"]["country_history"] = {"rows": len(hist), "authored": True}
        prov["authored_rules"] = ("population(code,m)=half_up(P0*(1+g)^dm), g=sha1(code)[:8]→[-0.4%,+0.8%]/月, "
                                  "m0=2020-01, 84 月; gnp 同法(sha1(code+':gnp')); population_resident: "
                                  "Continent='Asia' 行 ×1.06 半上取整(v2 常住口径), 其余等值; " + S.SEED_NOTE)
    else:
        src = os.path.join(L.BIRD, domain, domain + ".sqlite")
        prov["source"] = {"kind": "bird_dev_20240627", "path": src, "sha256": L.sha256_file(src),
                          "license": "CC BY-SA 4.0 (bird-bench.github.io)"}
        counts = L.import_sqlite_to_duckdb(con, src)
        for t, n in counts.items():
            prov["tables"][t] = {"rows": n, "authored": False}
        if domain == "formula_1":
            con.execute("CREATE TABLE points_scheme (scheme_id VARCHAR, position INTEGER, "
                        "points DOUBLE, authored BOOLEAN)")
            con.executemany("INSERT INTO points_scheme VALUES (?,?,?,?)", S.gen_points_scheme_rows())
            n = con.execute("SELECT COUNT(*) FROM points_scheme").fetchone()[0]
            prov["tables"]["points_scheme"] = {"rows": n, "authored": True}
            prov["authored_rules"] = ("points_scheme: PS2009(前八 10-8-6-5-4-3-2-1)/PS2010(前十 25-18-…-1) "
                                      "真实历史积分口径的关系原子化; " + S.SEED_NOTE)

    seeds = SEED_BUILDERS[domain]()
    L.write_seed_files(domain, seeds)
    seed_stats = L.load_gov_seed_into_duck(con, seeds)
    prov["gov_seed_rows"] = seed_stats
    con.close()
    L.jdump(prov, os.path.join(d, "provenance.json"))
    return prov


def materialize_questions():
    """路径 A：逐题执行 gold_sql 物化 gold_value；写 domains/<db>/questions.json。"""
    by_dom = {}
    for q in QUESTIONS:
        by_dom.setdefault(q["domain"], []).append(q)
    report = {"expect_close": [], "flip_pairs": []}
    for domain, qs in by_dom.items():
        wpath = os.path.join(L.dom_dir(domain), "warehouse.duckdb")
        con = duckdb.connect(wpath, read_only=True)
        out = []
        for q in qs:
            g = q["_gold"]
            gold_value = None
            if g["gold_sql"]:
                if g["value_kind"] == "cells":
                    rows = con.execute(g["gold_sql"]).fetchall()
                    gold_value = [[r[0], float(r[1]) if isinstance(r[1], (int, float)) else r[1]]
                                  for r in rows]
                elif g["value_kind"] == "string":
                    r = con.execute(g["gold_sql"]).fetchone()
                    gold_value = None if r is None else str(r[0])
                else:
                    r = con.execute(g["gold_sql"]).fetchone()
                    v = r[0]
                    gold_value = float(v) if isinstance(v, float) else (
                        int(v) if v is not None else None)
            if g.get("expect_close") is not None and gold_value is not None:
                ok = abs(float(gold_value) - float(g["expect_close"])) <= 1e-6 * max(
                    1.0, abs(float(g["expect_close"])))
                report["expect_close"].append(
                    {"qid": q["qid"], "expected": g["expect_close"], "got": gold_value, "ok": ok})
            row = {k: q[k] for k in VISIBLE_FIELDS}
            row.update({"metric": g["metric"], "expected_kind": g["expected_kind"],
                        "refusal_reason": g["refusal_reason"],
                        "refusal_subtype": g["refusal_subtype"], "rewrite": g["rewrite"],
                        "gold_sql": g["gold_sql"], "gold_value": gold_value,
                        "windows": g["windows"], "windows_note": WINDOWS_NOTE,
                        "notes": g["notes"]})
            out.append(row)
        con.close()
        L.jdump(out, os.path.join(L.dom_dir(domain), "questions.json"))
    # flip 对断言：同题双 T 异值
    idx = {}
    for domain, qs in by_dom.items():
        p = os.path.join(L.dom_dir(domain), "questions.json")
        for row in json.load(open(p)):
            idx[row["qid"]] = row
    for a, b in [("FIN-Q1", "FIN-Q2"), ("F1-Q1", "F1-Q2"), ("CA-Q1", "CA-Q2"), ("W1-Q1", "W1-Q2")]:
        va, vb = idx[a]["gold_value"], idx[b]["gold_value"]
        report["flip_pairs"].append({"pair": [a, b], "values": [va, vb], "distinct": va != vb})
        assert va != vb, f"flip pair {a}/{b} 未分离: {va}"
    return report


def main():
    args = sys.argv[1:]
    domains = args if args else L.DOMAINS
    provs = {}
    for dm in domains:
        print(f"[build] {dm} ...", flush=True)
        provs[dm] = build_domain(dm)
        print(f"[build] {dm} done: " +
              ", ".join(f"{t}={v['rows']}" for t, v in sorted(provs[dm]["tables"].items())))
    if not args:
        print("[questions] materializing gold via path-A SQL ...", flush=True)
        rep = materialize_questions()
        L.jdump(rep, os.path.join(L.ROOT, "build", "materialize_report.json"))
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    print("[build] ALL DONE")


if __name__ == "__main__":
    main()
