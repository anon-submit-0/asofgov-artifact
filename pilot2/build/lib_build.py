# -*- coding: utf-8 -*-
"""pilot2 共享建库库：BIRD/Spider SQLite -> per-domain warehouse.duckdb + gov_seed 十表落盘。
确定性、幂等：每次运行整库重建；一切数字由脚本复算。
"""
import os, json, hashlib, datetime

ROOT = "/Volumes/SSD 1/explore_opportunity_cc/pilot2"
BIRD = "/Users/loctek/bench_data/dev_20240627/dev_databases"
W1_SRC_DUCK = "/Volumes/SSD 1/explore_opportunity_cc/pilot/public/warehouse.duckdb"

DOMAINS = ["financial", "card_games", "codebase_community", "formula_1",
           "debit_card_specializing", "european_football_2", "california_schools",
           "thrombosis_prediction", "world_1"]

GOV_TABLES = ["gov_semantic_graph_version", "gov_semantic_node", "gov_metric",
              "gov_measure_def", "gov_metric_alias", "gov_caliber_routing",
              "gov_valid_time_anchor", "gov_temporal_binding",
              "gov_granularity_edge", "gov_disclosure_policy"]

def dom_dir(domain):
    d = os.path.join(ROOT, "domains", domain)
    os.makedirs(os.path.join(d, "gov_seed"), exist_ok=True)
    return d

def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def jdump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")

def write_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

def import_sqlite_to_duckdb(con, sqlite_path):
    """把 SQLite 全部业务表原值拷入当前 duckdb 连接。返回 {table: rowcount}。"""
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{sqlite_path}' AS src (TYPE sqlite)")
    tabs = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_catalog='src'").fetchall()]
    counts = {}
    for t in sorted(tabs):
        if t == "sqlite_sequence":
            continue
        con.execute(f'DROP TABLE IF EXISTS "{t}"')
        try:
            con.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
        except Exception:
            # 源库声明类型与实存值不符（如 ef2 Player.height INTEGER 实存浮点）：
            # 该表全列按 VARCHAR 原值载入（保留公开数据原值，不做类型改写）
            con.execute("SET GLOBAL sqlite_all_varchar=true")
            con.execute(f'DROP TABLE IF EXISTS "{t}"')
            con.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
            con.execute("SET GLOBAL sqlite_all_varchar=false")
        counts[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    con.execute("DETACH src")
    return counts

def load_gov_seed_into_duck(con, seed_dict):
    """gov 十表以 (全部标量 + 复杂值 JSON 字符串) 形式落 duckdb；同时返回行数统计。"""
    stats = {}
    for tname in GOV_TABLES:
        rows = seed_dict.get(tname, [])
        cols = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        con.execute(f'DROP TABLE IF EXISTS "{tname}"')
        if not rows:
            con.execute(f'CREATE TABLE "{tname}" (placeholder VARCHAR)')
            con.execute(f'DELETE FROM "{tname}"')
            stats[tname] = 0
            continue
        coldefs = ", ".join(f'"{c}" VARCHAR' for c in cols)
        con.execute(f'CREATE TABLE "{tname}" ({coldefs})')
        ins = f'INSERT INTO "{tname}" VALUES ({", ".join(["?"] * len(cols))})'
        data = []
        for r in rows:
            vals = []
            for c in cols:
                v = r.get(c)
                if isinstance(v, (dict, list)):
                    vals.append(json.dumps(v, ensure_ascii=False, sort_keys=True))
                elif v is None:
                    vals.append(None)
                else:
                    vals.append(str(v))
            data.append(vals)
        con.executemany(ins, data)
        stats[tname] = len(rows)
    return stats

def write_seed_files(domain, seed_dict):
    d = dom_dir(domain)
    for tname in GOV_TABLES:
        write_jsonl(seed_dict.get(tname, []), os.path.join(d, "gov_seed", tname + ".jsonl"))

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
