# -*- coding: utf-8 -*-
"""S6 Stage A deterministic translation audit + leak audit + freeze.

Governing prereg: PREREG_poststudy2_20260823.md
sha256 838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669.

Audits every English translation field-by-field against the prereg
checklist (as-of instant, declared-at instant, window phrase, metric-alias
meaning, version-pin phrasing preserved; nothing added), re-runs the
string-level leak audit over the English texts mirroring
pilot2/ci/leak_check.py extended per the S6 task spec (gold values >=8
chars + gold SQL + window endpoints + refusal classes must not appear),
and — only if the final texts fully pass — writes questions_en.json and
the sha256 freeze line. Structured question fields (as_of, declared_at,
windows, metric_alias, pinned_version, gold_*) are read HERE for the
audit only; they are not fed to any scored arm. Frozen inputs are opened
read-only; all outputs are new files under poststudy2_20260823/s6/.
"""
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata

ROOT = "/Volumes/SSD 1/explore_opportunity_cc/pilot2"
S6 = os.path.join(ROOT, "poststudy2_20260823", "s6")
RAW = os.path.join(S6, "translation_raw")
PREREG_SHA = "838a214fc5a09902703d969c839872ff843f190e9f2e1c9f6902f231e061c669"

MONTHS = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May",
          6: "June", 7: "July", 8: "August", 9: "September", 10: "October",
          11: "November", 12: "December"}

NUM_RE = re.compile(r"\d+(?:[-/.]\d+)*")
ASOF_RE = re.compile(r"as-of\s+(\d{4}(?:-\d{2})?(?:-\d{2})?)")
ZH_YM_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")
CJK_RE = re.compile(r"[一-鿿]")
DATEISH_RE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")

# metric-alias meaning: every pattern (case-insensitive regex) must match.
ALIAS_KEYWORDS = {
    "免费餐率": ["free meal rate"],
    "校级免费餐率报表": ["school-level free meal rate report"],
    "时点在效学校数": ["schools in effect"],
    "当月裁定条数": ["adjudication|ruling", "count|number|how many"],
    "裁定强度": ["adjudication intensity|ruling intensity"],
    "轮替合法卡牌总数": ["rotation", "legal", "card", "total|count|number"],
    "单卡当月裁定条数": ["card", "ruling|adjudication", "count|number|how many"],
    "区间裁定条数": ["ruling|adjudication", "count|number|records"],
    "保留卡收藏溢价率": ["reserved", "premium", "rate"],
    "提问采纳率": ["question acceptance rate"],
    "当月投票总数": ["votes?", "total"],
    "用户采纳答案数报表": ["accepted answer", "report"],
    "新提问数报表": ["new question", "report"],
    "用户所在地": ["location"],
    "答题者名录": ["DisplayName", "Location"],
    "月均客户消费额": ["monthly average customer (spending|consumption)"],
    "月消费总额": ["total monthly (consumption|spending)"],
    "细分平均单笔交易金额": ["segment average single transaction amount"],
    "区间交易笔数": ["transaction count|number of transactions"],
    "当月交易笔数": ["monthly transaction count"],
    "当月新增放贷笔数": ["new loans?", "number|count|how many"],
    "罚息交易占比": ["penalty interest transaction (proportion|share|ratio)"],
    "问题贷款率": ["problem loan rate"],
    "快照日球员平均综合评分": ["average composite rating", "snapshot"],
    "主场胜率": ["home win rate"],
    "当月球员属性快照条数": ["player attribute snapshot", "records|count|how many"],
    "区间比赛场数": ["match", "number|count"],
    "评分归一当日胜率": ["rating-normalized", "win rate"],
    "赛季车手总积分": ["season driver total points"],
    "两季车手积分差": ["driver points difference"],
    "赛季参赛记录条数": ["participation records", "season"],
    "区间大奖赛场数": ["grand prix", "count|number"],
    "当月大奖赛场数": ["grand prix", "count|number|races"],
    "车队场均积分": ["points per race|average points per entry", "team"],
    "异常化验率": ["abnormal lab", "rate"],
    "年度检查记录数": ["annual", "examination|exam(?!ple)", "record"],
    "患者异常化验报表": ["patient", "abnormal lab", "report"],
    "患者出生日期": ["birth"],
    "异常化验患者名录": ["patient", "abnormal"],
    "亚洲人口总和": ["population", "asia", "total"],
    "亚洲人口占比": ["asian population share|population share"],
    "区间历史记录条数": ["history record", "number|count"],
}

# identical ZH alias (verbatim in >=2 question texts) must surface as one
# identical EN alias phrase in every one of those questions.
ALIAS_CONSISTENCY = {
    "免费餐率": "free meal rate",
    "时点在效学校数": "schools in effect",
    "裁定强度": "adjudication intensity",
    "提问采纳率": "question acceptance rate",
    "月均客户消费额": "monthly average customer spending",
    "月消费总额": "total monthly consumption",
    "快照日球员平均综合评分": "average composite rating",
    "问题贷款率": "problem loan rate",
    "罚息交易占比": "penalty interest transaction proportion",
    "当月交易笔数": "monthly transaction count",
    "赛季车手总积分": "season driver total points",
    "亚洲人口总和": "total population of Asia",
    "亚洲人口占比": "Asian population share",
}

# ZH marker -> EN regex (case-insensitive) that must match when marker present.
MARKER_KEYWORDS = [
    ("所在月窗", r"month window"),
    ("所在年窗", r"year window"),
    ("单日窗", r"single[- ]day window"),
    ("窗", r"window"),
    ("月粒", r"month granularity"),
    ("日粒", r"daily granularity|day granularity"),
    ("自然年", r"calendar year"),
    ("学年", r"school year"),
    ("赛季", r"season"),
    ("一周", r"week"),
    ("区间", r"interval|range|from .{4,14} to "),
    ("快照日", r"snapshot date|snapshot day"),
    ("声明时点", r"declaration instant|declared"),
    ("披露策略", r"disclosure policy"),
    ("口径", r"caliber"),
    ("逐日", r"daily|day[- ]by[- ]day"),
    ("各月", r"each month|per month|monthly"),
    ("分子", r"numerator"),
    ("分母", r"denominator"),
    ("钉定", r"pin"),
    ("版本", r"version"),
    ("原值", r"original"),
    ("报表", r"report"),
    ("校级", r"school[- ]level"),
    ("用户级", r"user[- ]level"),
    ("患者级", r"patient[- ]level"),
    ("细分级", r"segment[- ]level"),
    ("按当时生效口径", r"caliber in effect at that time"),
    ("按当时默认口径", r"default caliber"),
    ("治理路由口径", r"governance-routed caliber"),
    ("按现行披露策略呈现", r"under the current disclosure policy"),
    ("按当前轮替口径", r"current rotation caliber"),
    ("按当时生效积分口径", r"points caliber in effect at that time"),
    ("按当时生效人口口径", r"population caliber in effect at that time"),
    ("GOT≥60", r"GOT≥60"),
]

# per-qid extra required phrases (case-insensitive regex).
QID_REQUIRED = {
    "CA-Q6": [r"charter authorization date"],
    "F1-Q3": [r"\bv1\b", r"pin", r"version", r"back-calculat|recomput"],
    "CODE-Q7": [r"top (ten|10)", r"original value"],
    "TH-Q5": [r"original", r"diagnos"],
    "TH-Q6": [r"patient[- ]level", r"row"],
    "CARD-Q4": [r"Kytheon, Hero of Akros // Gideon, Battle-Forged"],
}

REFUSAL_CLASSES = ["anchor-mismatch", "disclosure-blocked", "missing-caliber",
                   "out-of-validity", "am_i", "am_ii", "am_iii", "am_iv",
                   "mc_i", "mc_ii"]


def load_questions():
    qs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "domains", "*", "questions.json"))):
        qs.extend(json.load(open(f)))
    assert len(qs) == 60, len(qs)
    return qs


def num_tokens(text):
    return NUM_RE.findall(text)


def month_excused(tok, zh, en):
    """ZH '{Y} 年 {M} 月' month digit M is excused if EN carries the same
    month as a month name with the year, or as ISO YYYY-MM."""
    for y, m in ZH_YM_RE.findall(zh):
        if tok in (m, str(int(m))):
            mi = int(m)
            if re.search(MONTHS[mi] + r"\s+" + y, en) or (y + "-%02d" % mi) in en:
                return True
    return False


def date_boundary_search(d, text):
    return re.search(r"(?<![\d-])" + re.escape(d) + r"(?![\d-])", text)


def audit_one(q, en):
    """Field-by-field checks; returns list of (check, ok, detail)."""
    zh = q["question_zh"]
    out = []

    # 0) shape: non-empty single line, no CJK residue
    out.append(("shape.nonempty", bool(en.strip()), ""))
    out.append(("shape.single_line", "\n" not in en, ""))
    out.append(("shape.no_cjk", not CJK_RE.search(en),
                (CJK_RE.search(en) or [""])[0] if CJK_RE.search(en) else ""))

    # 1) declared-at instant + phrasing
    da = q.get("declared_at")
    if da:
        out.append(("declared_at.in_zh", da in zh, da))
        out.append(("declared_at.in_en", da in en, da))
        out.append(("declared_at.phrasing", bool(re.search(r"declar", en, re.I)), ""))

    # 2) as-of tokens: same multiset in ZH and EN; ZH tokens consistent
    #    with the structured as_of field
    zh_asof = sorted(ASOF_RE.findall(zh))
    en_asof = sorted(ASOF_RE.findall(en))
    out.append(("as_of.tokens_equal", zh_asof == en_asof,
                "zh=%s en=%s" % (zh_asof, en_asof)))
    fld = q.get("as_of")
    for t in zh_asof:
        out.append(("as_of.field_consistent", bool(fld) and
                    (fld == t or fld.startswith(t)), "%s vs field %s" % (t, fld)))

    # 3) numbers/dates preserved ZH->EN (window phrase endpoints included)
    en_toks = set(num_tokens(en))
    missing = [t for t in num_tokens(zh)
               if t not in en_toks and not month_excused(t, zh, en)]
    out.append(("numbers.zh_covered_in_en", not missing, missing))

    # 4) nothing added EN->ZH (no new numeric/date token)
    zh_toks = set(num_tokens(zh))
    added = [t for t in num_tokens(en) if t not in zh_toks]
    out.append(("numbers.none_added_in_en", not added, added))

    # 5) ASCII identifiers preserved case-sensitively
    zh_words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", zh)
                if w not in ("as", "of")]
    miss_w = [w for w in zh_words if not re.search(r"\b" + re.escape(w) + r"\b", en)]
    out.append(("identifiers.preserved", not miss_w, miss_w))

    # 6) window/caliber/disclosure/version marker keywords
    for marker, pat in MARKER_KEYWORDS:
        if marker in zh:
            out.append(("marker.%s" % marker,
                        bool(re.search(pat, en, re.I if marker != "GOT≥60" else 0)),
                        pat))

    # 7) version pin
    pv = q.get("pinned_version")
    if pv:
        out.append(("pinned_version.token", pv in en, pv))

    # 8) metric alias meaning
    alias = q.get("metric_alias")
    pats = ALIAS_KEYWORDS.get(alias)
    if pats is None:
        out.append(("alias.keywords", False, "no keyword spec for %s" % alias))
    else:
        for p in pats:
            out.append(("alias.kw:%s" % p, bool(re.search(p, en, re.I)), alias))

    # 9) per-qid required phrases
    for p in QID_REQUIRED.get(q["qid"], []):
        out.append(("qid_required:%s" % p, bool(re.search(p, en, re.I)), ""))

    return out


def alias_consistency(questions, en_map):
    """Same verbatim ZH alias in >=2 question texts -> one EN phrase in all."""
    res = []
    groups = {}
    for q in questions:
        a = q.get("metric_alias")
        if a and a in q["question_zh"]:
            groups.setdefault(a, []).append(q["qid"])
    for a, qids in sorted(groups.items()):
        if len(qids) < 2:
            continue
        phrase = ALIAS_CONSISTENCY.get(a)
        if phrase is None:
            res.append({"alias": a, "qids": qids, "ok": False,
                        "detail": "multi-question alias missing consistency phrase"})
            continue
        bad = [qid for qid in qids
               if not re.search(re.escape(phrase), en_map[qid], re.I)]
        res.append({"alias": a, "alias_en": phrase, "qids": qids,
                    "ok": not bad, "detail": bad})
    return res


def leak_audit(questions, en_map):
    """String-level leak audit over the English texts, mirroring
    pilot2/ci/leak_check.py's gold-literal discipline, extended per the S6
    task spec: gold values >=8 chars, gold SQL, window endpoints, refusal
    classes must not appear."""
    problems = []
    checks = {"gold_value_ge8": 0, "gold_value_int_gt30": 0, "gold_sql": 0,
              "sql_keyword": 0, "window_endpoints": 0, "refusal_classes": 0}

    # global forbidden gold-value strings (>=8 chars), incl. leaves of
    # structured golds
    gold_strings = set()
    for q in questions:
        gv = q.get("gold_value")

        def leaves(v):
            if isinstance(v, dict):
                for x in v.values():
                    leaves(x)
            elif isinstance(v, (list, tuple)):
                for x in v:
                    leaves(x)
            elif v is not None:
                s = str(v)
                if len(s) >= 8:
                    gold_strings.add(s)
        leaves(gv)
        if gv is not None and len(str(gv)) >= 8:
            gold_strings.add(str(gv))

    for qid, en in en_map.items():
        for s in gold_strings:
            checks["gold_value_ge8"] += 1
            if s in en:
                problems.append((qid, "gold value literal (>=8 chars) in EN", s))
        if re.search(r"\bSELECT\b", en, re.I) or re.search(r"\bWHERE\b", en):
            problems.append((qid, "SQL keyword in EN", ""))
        checks["sql_keyword"] += 1

    for q in questions:
        qid, zh = q["qid"], q["question_zh"]
        en = en_map[qid]
        # weak int mirror of frozen leak_check.py, applied to EN
        gv = q.get("gold_value")
        checks["gold_value_int_gt30"] += 1
        if isinstance(gv, int) and abs(gv) > 30 and str(gv) in en:
            problems.append((qid, "gold int literal leaked into question_en", str(gv)))
        # gold SQL substring (any question's SQL vs this EN is overkill;
        # SQL text can only leak from its own record)
        gs = q.get("gold_sql")
        checks["gold_sql"] += 1
        if gs and gs.strip() and gs.strip() in en:
            problems.append((qid, "gold_sql leaked into question_en", ""))
        # window endpoints: any windows date not present in own ZH must not
        # appear in EN
        w = q.get("windows")
        if w:
            for d in sorted(set(DATEISH_RE.findall(json.dumps(w)))):
                checks["window_endpoints"] += 1
                if not date_boundary_search(d, zh) and date_boundary_search(d, en):
                    problems.append((qid, "window endpoint leaked into question_en", d))
        # refusal classes anywhere in any EN
    for qid, en in en_map.items():
        for rc in REFUSAL_CLASSES:
            checks["refusal_classes"] += 1
            if re.search(r"\b" + re.escape(rc) + r"\b", en, re.I):
                problems.append((qid, "refusal class token in EN", rc))

    return {"problems": problems, "n_checks": checks,
            "n_gold_strings_ge8": len(gold_strings),
            "pass": not problems}


def run_round(questions, en_map):
    per_q, n_fail = {}, 0
    for q in questions:
        rows = audit_one(q, en_map[q["qid"]])
        fails = [(c, d) for c, ok, d in rows if not ok]
        per_q[q["qid"]] = {"n_checks": len(rows), "failures": fails}
        if fails:
            n_fail += 1
    cons = alias_consistency(questions, en_map)
    leak = leak_audit(questions, en_map)
    total_checks = sum(v["n_checks"] for v in per_q.values()) + len(cons)
    return {"per_question": per_q,
            "n_questions": len(questions),
            "n_questions_failing": n_fail,
            "total_field_checks": total_checks,
            "alias_consistency": cons,
            "alias_consistency_fail": [c for c in cons if not c["ok"]],
            "leak_audit": leak,
            "pass": n_fail == 0 and all(c["ok"] for c in cons) and leak["pass"]}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    questions = load_questions()
    raw_map, fix_reasons = {}, {}
    for q in questions:
        rec = json.load(open(os.path.join(RAW, q["qid"] + ".json")))
        raw_map[q["qid"]] = unicodedata.normalize("NFC", rec["question_en_raw"]).strip()
    fixes = json.load(open(os.path.join(S6, "translation_fixes.json")))
    fixes = {k: v for k, v in fixes.items() if not k.startswith("_")}

    final_map = dict(raw_map)
    for qid, fx in fixes.items():
        assert qid in final_map, qid
        fix_reasons[qid] = {"reason": fx["reason"], "trigger": fx["trigger"],
                            "raw": raw_map[qid], "fixed": fx["question_en"]}
        final_map[qid] = unicodedata.normalize("NFC", fx["question_en"]).strip()

    round_raw = run_round(questions, raw_map)
    round_final = run_round(questions, final_map)

    report = {
        "study": "S6 Stage A — translations + audit + freeze (no scored calls)",
        "prereg": "PREREG_poststudy2_20260823.md",
        "prereg_sha256": PREREG_SHA,
        "translator_model": "claude-opus-4-6 (llmhub), question_zh only as input",
        "n_questions": 60,
        "round_raw": round_raw,
        "fixes_applied": fix_reasons,
        "n_fixes": len(fix_reasons),
        "round_final": round_final,
        "final_pass": round_final["pass"],
    }

    audit_json = os.path.join(S6, "translation_audit.json")
    with open(audit_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    if not round_final["pass"]:
        print("FINAL AUDIT FAIL — questions_en.json NOT written")
        for qid, v in round_final["per_question"].items():
            for c, d in v["failures"]:
                print("  ", qid, c, d)
        for c in round_final["alias_consistency_fail"]:
            print("  consistency", c)
        for p in round_final["leak_audit"]["problems"]:
            print("  leak", p)
        return 1

    qe_path = os.path.join(S6, "questions_en.json")
    with open(qe_path, "w", encoding="utf-8") as f:
        json.dump({q["qid"]: final_map[q["qid"]] for q in questions},
                  f, ensure_ascii=False, indent=1)
    sha = sha256_file(qe_path)
    with open(os.path.join(S6, "FREEZE_questions_en.sha256"), "w") as f:
        f.write("%s  questions_en.json\n" % sha)
    report["questions_en_sha256"] = sha
    with open(audit_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("FINAL AUDIT PASS")
    print("questions_en.json sha256 =", sha)
    print("raw round: %d/60 questions failing; final round: %d/60 failing" %
          (round_raw["n_questions_failing"], round_final["n_questions_failing"]))
    print("field checks (final): %d; leak problems: %d" %
          (round_final["total_field_checks"],
           len(round_final["leak_audit"]["problems"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
