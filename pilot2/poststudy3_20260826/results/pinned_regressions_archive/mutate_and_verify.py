import json, os, sys, io, contextlib
import duckdb
sys.path.insert(0, "/Volumes/SSD 1/vldb_asof/asofgov-artifact-final/impl/asof_verifier")
import chk

WORK = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(WORK, "warehouse.duckdb")
base = json.load(open(os.path.join(WORK, "CARD-Q2.json"), encoding="utf-8"))
q = json.load(open(os.path.join(WORK, "q_CARD-Q2.json"), encoding="utf-8"))
orig = base["sql"]

NUM = ('(SELECT COUNT(*) FROM "rulings" t0 WHERE '
       'substr(CAST(t0."date" AS VARCHAR),1,10) >= \'2016-11-01\' AND '
       'substr(CAST(t0."date" AS VARCHAR),1,10) < \'2016-12-01\')')
DEN_INNER = ('(SELECT COUNT(*) FROM "cards" t0 INNER JOIN "sets" t1 ON t0."setCode" = t1."code" '
             'WHERE substr(CAST(t1."releaseDate" AS VARCHAR),1,10) >= \'2016-11-01\' AND '
             'substr(CAST(t1."releaseDate" AS VARCHAR),1,10) < \'2016-12-01\')')
assert NUM in orig, "NUM template not found"
assert DEN_INNER in orig, "DEN template not found"

mutations = {}

# (a) numerator aggregate -> COUNT(DISTINCT rulings.date)
num_a = NUM.replace("COUNT(*)", 'COUNT(DISTINCT t0."date")')
mutations["a_count_distinct_date"] = orig.replace(NUM, num_a)

# (b) swap numerator / denominator legs: (den)/(num)
mutations["b_leg_swap"] = (DEN_INNER + " * 1.0 / NULLIF(" + NUM + ", 0)")

# (c) constant, multi-row projection
mutations["c_constant_999"] = ('SELECT 999 FROM "rulings" t0 WHERE '
    'substr(CAST(t0."date" AS VARCHAR),1,10) >= \'2016-11-01\' AND '
    'substr(CAST(t0."date" AS VARCHAR),1,10) < \'2016-12-01\'')

# (d) wrong (still in-window) registered predicate: narrow numerator window to mid-month
num_d = NUM.replace("'2016-11-01'", "'2016-11-10'").replace("'2016-12-01'", "'2016-11-20'")
mutations["d_narrowed_predicate"] = orig.replace(NUM, num_d)

con = duckdb.connect(DB, read_only=True)

def exec_val(sql):
    try:
        rows = con.execute(sql).fetchall()
        return {"nrows": len(rows), "first": rows[0] if rows else None}
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}

results = {}
# baseline recompute for reference
results["_baseline"] = {"sql": orig, "exec": exec_val(orig)}

for name, msql in mutations.items():
    cert = json.loads(json.dumps(base))
    cert["sql"] = msql
    path = os.path.join(WORK, "cert_mut_%s.json" % name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cert, fh, ensure_ascii=False, indent=1)
    c2 = duckdb.connect(DB, read_only=True)
    rep = chk.verify(cert, q, c2, None, allow_declared_windows=True)
    c2.close()
    with open(os.path.join(WORK, "out_mut_%s.json" % name), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    v6a = next(c for c in rep["checks"] if c["check"] == "V6a")
    results[name] = {
        "sql": msql,
        "exec": exec_val(msql),
        "verdict": rep["verdict"],
        "rejected_by": rep["rejected_by"],
        "V6a": [v6a["status"], v6a["detail"][:160]],
        "fail_checks": [(c["check"], c["detail"][:120]) for c in rep["checks"] if c["status"] == "FAIL"],
    }

con.close()
print(json.dumps(results, ensure_ascii=False, indent=1))
