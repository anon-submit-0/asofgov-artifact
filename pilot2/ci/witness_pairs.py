# -*- coding: utf-8 -*-
"""ND-1 标签的元数据不可决定性：见证对物化断言（DESIGN_SPEC §3.2）。

对金标 ∈ {REFUSE(OOV / AM(iv) / MC(ii)), REWRITE(小胞驱动上卷)} 的题 q，构造 D₂ =
D₁ + 少量增行（治理种子逐字节不动），断言 label(q,G,D₁) ≠ label(q,G,D₂)：
证明这些标签是数据的函数——把治理内容整层喂给任何无执行系统，信息论上不可判。
"""
import os, sys, json, shutil
ROOT = "/Volumes/SSD 1/explore_opportunity_cc/pilot2"
sys.path.insert(0, os.path.join(ROOT, "build"))
import duckdb
from questions_def import VISIBLE_FIELDS
from govchain_resolver import Resolver

WORK = os.path.join(ROOT, "ci", "witness_work")

# (qid, domain, [mutation sql...], 说明)
WITNESSES = [
    ("FIN-Q7", "financial",
     ["INSERT INTO trans (trans_id, account_id, date) VALUES (99999901, 1, '1999-06-15')"],
     "OOV: 向 1999-06 插入一笔交易 → hull 右移，月窗部分覆盖"),
    ("F1-Q7", "formula_1",
     ["INSERT INTO races (raceId, year, round, circuitId, name, date) "
      "VALUES (999901, 1949, 1, 1, 'Witness GP', '1949-05-20')"],
     "OOV: 向 1949-05 插入一场赛事 → hull 左移"),
    ("DEB-Q6", "debit_card_specializing",
     ["INSERT INTO yearmonth (CustomerID, Date, Consumption) VALUES (999901, '201312', 100.0)"],
     "OOV(strict_member): 月集补入 201312"),
    ("EF2-Q5", "european_football_2",
     ["INSERT INTO Player_Attributes (id, date, overall_rating) "
      "VALUES (9999001, '2013-12-25 00:00:00', 70)"],
     "OOV(strict_member): 快照日集补入 2013-12-25"),
    ("CARD-Q7", "card_games",
     ["INSERT INTO sets (id, code, name, releaseDate) VALUES (999901, 'ZZW', 'Witness Set', '2017-02-10')",
      "INSERT INTO cards (id, uuid, name, setCode) VALUES (999901, 'witness-uuid-0001', 'Witness Card', 'ZZW')"],
     "MC(ii): 向 2017-02 插入一套牌+一印刷 → 分母质量翻正"),
    ("F1-Q8", "formula_1", None,  # raceId 运行时探取
     "MC(ii): 向 2010 赛季插入一条 brawn 参赛记录 → 分母翻正"),
    ("EF2-Q6", "european_football_2",
     ["INSERT INTO Player_Attributes (id, date, overall_rating) "
      "VALUES (9999002, '2013-12-01 00:00:00', 75)"],
     "AM(iv): 向 2013-12-01 插入一行快照 → 锚对实现集一致，审计通过"),
    ("DEB-Q5", "debit_card_specializing",
     ["INSERT INTO customers (CustomerID, Segment, Currency) VALUES (999901,'LAM','EUR'),(999902,'LAM','EUR'),(999903,'LAM','EUR'),(999904,'LAM','EUR')",
      "INSERT INTO transactions_1k (TransactionID, Date, CustomerID, Amount) "
      "VALUES (999901,'2012-08-24',999901,30.0),(999902,'2012-08-24',999902,30.0),"
      "(999903,'2012-08-24',999903,30.0),(999904,'2012-08-24',999904,30.0)"],
     "REWRITE(小胞): LAM×EUR 胞 16→20 = k(v2) → 上卷判定翻回 Segment 级 ANSWER"),
]


def label_of(res):
    return (res["label"], res.get("refusal_reason"), res.get("refusal_subtype"),
            (res.get("rewrite") or {}).get("kind"))


def main():
    os.makedirs(WORK, exist_ok=True)
    out = []
    for qid, domain, muts, note in WITNESSES:
        dompath = os.path.join(ROOT, "domains", domain)
        qs = json.load(open(os.path.join(dompath, "questions.json")))
        q = [x for x in qs if x["qid"] == qid][0]
        visible = {k: q.get(k) for k in VISIBLE_FIELDS}

        con1 = duckdb.connect(os.path.join(dompath, "warehouse.duckdb"), read_only=True)
        r1 = Resolver(con1).resolve(visible)
        con1.close()

        w2 = os.path.join(WORK, f"{qid}.duckdb")
        if os.path.exists(w2):
            os.remove(w2)
        shutil.copy(os.path.join(dompath, "warehouse.duckdb"), w2)
        con2 = duckdb.connect(w2)
        if qid == "F1-Q8":
            rid = con2.execute("SELECT raceId FROM races WHERE date>='2010-01-01' AND "
                               "date<'2011-01-01' ORDER BY date LIMIT 1").fetchone()[0]
            muts = [f"INSERT INTO results (resultId, raceId, driverId, constructorId, positionOrder) "
                    f"VALUES (9999901, {rid}, 18, 23, 1)"]
        for m in muts:
            con2.execute(m)
        r2 = Resolver(con2).resolve(visible)
        con2.close()
        os.remove(w2)

        l1, l2 = label_of(r1), label_of(r2)
        ok = l1 != l2
        out.append({"qid": qid, "note": note, "label_D1": list(l1), "label_D2": list(l2),
                    "value_D2": r2.get("value"), "flip": ok})
        print(f"[witness] {qid:8s} {'FLIP' if ok else 'NO-FLIP'}  {l1} -> {l2}")
    rep = {"witnesses": out, "pass": all(w["flip"] for w in out)}
    with open(os.path.join(ROOT, "ci", "witness_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("[witness] ALL FLIP" if rep["pass"] else "[witness] FAILURES PRESENT")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
