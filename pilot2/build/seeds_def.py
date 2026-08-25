# -*- coding: utf-8 -*-
"""pilot2 gov_seed 十表定义（DESIGN_SPEC §3.1 schema 法）。

宪法约束（ND-2 黑名单）在此文件生效：
- 禁字段：select_expr/where_expr/sql/sql_template/expr/filter_sql/snapshot_table/valid_from/valid_to/gold_*；
- 一切字符串值不得含 SQL 片段（SELECT|FROM|WHERE|GROUP BY|JOIN 词边界 / SUM(|COUNT(|AVG(）；
- 覆盖域不物化：锚只登记 effective_col/vf_col/vtc_col 列名指针 + coverage_mode，区间/日期集一律现算；
- 口径定义 = 结构化谓词原子 (col, op, value)，不可粘贴；
- 每库两提交版本全量并存（无 is_current 捷径），被取代 v1 行即天然干扰行；另配 reference-only 路由、
  近似别名、未入解析路径的兄弟 metric（ND-3 干扰行 ≥30% 由 ci 复核）。
"""

VERSIONS = {
    "financial":               [("v1", "1994-01-15", 1, "初版治理：问题贷款口径含催收中与坏账两类"),
                                ("v2", "1998-03-01", 2, "核销新政后问题贷款口径收窄为坏账单类")],
    "card_games":              [("v1", "2015-01-15", 1, "初版治理：轮替合法套牌清单（鞑靼可汗期）"),
                                ("v2", "2017-09-28", 2, "轮替更新：合法套牌清单换代（依克夏兰期）")],
    "codebase_community":      [("v1", "2010-09-01", 1, "初版治理：采纳率分母为窗内全部新提问"),
                                ("v2", "2013-01-01", 2, "采纳率分母排除社区共有帖（协作维基帖不计入）")],
    "formula_1":               [("v1", "2009-03-01", 1, "初版治理：赛季积分映射沿用前八名 10-8-6-5-4-3-2-1"),
                                ("v2", "2010-02-01", 2, "积分映射改制：前十名 25-18-15-12-10-8-6-4-2-1")],
    "debit_card_specializing": [("v1", "2012-06-01", 1, "初版治理：客户级统计小胞阈值 k=10"),
                                ("v2", "2013-06-01", 2, "披露收紧：客户级统计小胞阈值升至 k=20")],
    "european_football_2":     [("v1", "2010-08-01", 1, "初版治理：胜率口径平局计半胜"),
                                ("v2", "2014-08-01", 2, "胜率口径改制：平局不计胜（权重 0.5 归零）")],
    "california_schools":      [("v1", "2014-09-01", 1, "初版治理：免费餐率默认口径 K-12 注册数"),
                                ("v2", "2015-07-01", 2, "默认口径切换：免费餐率改按 Ages 5-17 注册数")],
    "thrombosis_prediction":   [("v1", "1995-01-01", 1, "初版治理：出生日期掩码保留年月"),
                                ("v2", "1998-01-01", 2, "掩码升级：出生日期仅保留年份")],
    "world_1":                 [("v1", "2026-01-15", 1, "初版治理：人口口径为普查基线序列"),
                                ("v2", "2026-07-01", 2, "亚洲常住人口重定基：度量改指常住口径列（1.06 半上取整）")],
}


def _stamp(rows, gv):
    return [dict(r, graph_version=gv) for r in rows]


def dual(rows_v1, v2_patch=None, id_field=None, drop_in_v2=(), add_in_v2=()):
    """v1 全量 + v2 全量（默认逐行照抄，v2_patch 按 id 覆写，drop/add 控制成员）。"""
    out = _stamp(rows_v1, "v1")
    v2_rows = []
    for r in rows_v1:
        rid = r.get(id_field) if id_field else None
        if rid in drop_in_v2:
            continue
        r2 = dict(r)
        if v2_patch and rid in v2_patch:
            r2.update(v2_patch[rid])
        v2_rows.append(r2)
    v2_rows.extend(add_in_v2)
    out.extend(_stamp(v2_rows, "v2"))
    return out


def version_rows(domain):
    return [{"graph_version": gv, "domain": domain, "committed_at": at,
             "commit_seq": seq, "change_note": note}
            for gv, at, seq, note in VERSIONS[domain]]


# ---------------------------------------------------------------- financial
def seeds_financial():
    D = "financial"
    nodes = [
        {"node_id": "fin.loan", "domain": D, "physical_table": "loan", "entity_key": "loan_id", "scope_keys": {}},
        {"node_id": "fin.trans", "domain": D, "physical_table": "trans", "entity_key": "trans_id", "scope_keys": {}},
        {"node_id": "fin.account", "domain": D, "physical_table": "account", "entity_key": "account_id", "scope_keys": {"district_id": "district_id"}},
        {"node_id": "fin.district", "domain": D, "physical_table": "district", "entity_key": "district_id", "scope_keys": {}},
        {"node_id": "fin.client", "domain": D, "physical_table": "client", "entity_key": "client_id", "scope_keys": {}},
        {"node_id": "fin.disp", "domain": D, "physical_table": "disp", "entity_key": "disp_id", "scope_keys": {}},
        {"node_id": "fin.card", "domain": D, "physical_table": "card", "entity_key": "card_id", "scope_keys": {}},
        {"node_id": "fin.order", "domain": D, "physical_table": "order", "entity_key": "order_id", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "fin.problem_loan_rate", "domain": D, "kind": "ratio", "num_node": "fin.loan", "den_node": "fin.loan"},
        {"metric_id": "fin.penalty_trans_rate", "domain": D, "kind": "ratio", "num_node": "fin.trans", "den_node": "fin.trans"},
        {"metric_id": "fin.loan_count_month", "domain": D, "kind": "atomic", "num_node": "fin.loan", "den_node": None},
        {"metric_id": "fin.trans_count_month", "domain": D, "kind": "atomic", "num_node": "fin.trans", "den_node": None},
        {"metric_id": "fin.trans_count_range", "domain": D, "kind": "atomic", "num_node": "fin.trans", "den_node": None},
        # 干扰 metric（不在任何金标路径）
        {"metric_id": "fin.penalty_rate_classified", "domain": D, "kind": "ratio", "num_node": "fin.trans", "den_node": "fin.trans"},
        {"metric_id": "fin.problem_loan_count", "domain": D, "kind": "atomic", "num_node": "fin.loan", "den_node": None},
        {"metric_id": "fin.avg_loan_amount", "domain": D, "kind": "atomic", "num_node": "fin.loan", "den_node": None},
    ]
    measure = [
        {"measure_id": "fin.plr.num", "metric_id": "fin.problem_loan_rate", "leg": "num", "node_id": "fin.loan",
         "measure": "count", "preds": [{"col": "status", "op": "in", "value": ["B", "D"]}]},
        {"measure_id": "fin.plr.den", "metric_id": "fin.problem_loan_rate", "leg": "den", "node_id": "fin.loan",
         "measure": "count", "preds": []},
        {"measure_id": "fin.ptr.num", "metric_id": "fin.penalty_trans_rate", "leg": "num", "node_id": "fin.trans",
         "measure": "count", "preds": [{"col": "k_symbol", "op": "=", "value": "SANKC. UROK"}]},
        {"measure_id": "fin.ptr.den", "metric_id": "fin.penalty_trans_rate", "leg": "den", "node_id": "fin.trans",
         "measure": "count", "preds": []},
        {"measure_id": "fin.lcm.atom", "metric_id": "fin.loan_count_month", "leg": "atom", "node_id": "fin.loan",
         "measure": "count", "preds": []},
        {"measure_id": "fin.tcm.atom", "metric_id": "fin.trans_count_month", "leg": "atom", "node_id": "fin.trans",
         "measure": "count", "preds": []},
        {"measure_id": "fin.tcr.atom", "metric_id": "fin.trans_count_range", "leg": "atom", "node_id": "fin.trans",
         "measure": "count", "preds": []},
        # 干扰
        {"measure_id": "fin.prc.num", "metric_id": "fin.penalty_rate_classified", "leg": "num", "node_id": "fin.trans",
         "measure": "count", "preds": [{"col": "k_symbol", "op": "=", "value": "SANKC. UROK"}]},
        {"measure_id": "fin.prc.den", "metric_id": "fin.penalty_rate_classified", "leg": "den", "node_id": "fin.trans",
         "measure": "count", "preds": [{"col": "k_symbol", "op": "not_null", "value": None}]},
        {"measure_id": "fin.plc.atom", "metric_id": "fin.problem_loan_count", "leg": "atom", "node_id": "fin.loan",
         "measure": "count", "preds": [{"col": "status", "op": "in", "value": ["B", "D"]}]},
        {"measure_id": "fin.ala.atom", "metric_id": "fin.avg_loan_amount", "leg": "atom", "node_id": "fin.loan",
         "measure": "avg:amount", "preds": []},
    ]
    aliases = [
        {"alias_id": "fin.al1", "alias_text": "问题贷款率", "metric_id": "fin.problem_loan_rate"},
        {"alias_id": "fin.al2", "alias_text": "罚息交易占比", "metric_id": "fin.penalty_trans_rate"},
        {"alias_id": "fin.al3", "alias_text": "当月新增放贷笔数", "metric_id": "fin.loan_count_month"},
        {"alias_id": "fin.al4", "alias_text": "当月交易笔数", "metric_id": "fin.trans_count_month"},
        {"alias_id": "fin.al5", "alias_text": "区间交易笔数", "metric_id": "fin.trans_count_range"},
        # 近似别名干扰
        {"alias_id": "fin.al6", "alias_text": "问题贷款笔数", "metric_id": "fin.problem_loan_count"},
        {"alias_id": "fin.al7", "alias_text": "分类交易罚息占比", "metric_id": "fin.penalty_rate_classified"},
        {"alias_id": "fin.al8", "alias_text": "平均贷款金额", "metric_id": "fin.avg_loan_amount"},
    ]
    routing = [
        {"routing_id": "fin.rt1", "metric_id": "fin.penalty_trans_rate", "leg": "num", "hop_seq": 0,
         "src_node": "fin.trans", "dst_node": "fin.trans", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "fin.rt2", "metric_id": "fin.penalty_trans_rate", "leg": "den", "hop_seq": 0,
         "src_node": "fin.trans", "dst_node": "fin.trans", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "fin.rt3", "metric_id": "fin.problem_loan_rate", "leg": "num", "hop_seq": 0,
         "src_node": "fin.loan", "dst_node": "fin.loan", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "fin.rt4", "metric_id": "fin.problem_loan_rate", "leg": "den", "hop_seq": 0,
         "src_node": "fin.loan", "dst_node": "fin.loan", "join_on": [], "dst_caliber": "all"},
        # 干扰：受罚账户自指分母（旧企业轨 blind 模式的登记形态，reference-only）
        {"routing_id": "fin.rt9", "metric_id": "fin.penalty_rate_classified", "leg": "den", "hop_seq": 0,
         "src_node": "fin.trans", "dst_node": "fin.account", "join_on": [["account_id", "account_id"]],
         "dst_caliber": "none"},
    ]
    anchors = [
        {"anchor_id": "A-FIN-TRANS", "node_id": "fin.trans", "anchor_type": "snapshot_effective_date",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        {"anchor_id": "A-FIN-LOAN", "node_id": "fin.loan", "anchor_type": "snapshot_effective_date",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        {"anchor_id": "A-FIN-ACC", "node_id": "fin.account", "anchor_type": "snapshot_effective_date",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-FIN-PLR-N", "metric_id": "fin.problem_loan_rate", "leg": "num", "anchor_id": "A-FIN-LOAN",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-FIN-PLR-D", "metric_id": "fin.problem_loan_rate", "leg": "den", "anchor_id": "A-FIN-LOAN",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-FIN-PTR-N", "metric_id": "fin.penalty_trans_rate", "leg": "num", "anchor_id": "A-FIN-TRANS",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-FIN-PTR-D", "metric_id": "fin.penalty_trans_rate", "leg": "den", "anchor_id": "A-FIN-TRANS",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-FIN-LCM", "metric_id": "fin.loan_count_month", "leg": "atom", "anchor_id": "A-FIN-LOAN",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-FIN-TCM", "metric_id": "fin.trans_count_month", "leg": "atom", "anchor_id": "A-FIN-TRANS",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-FIN-TCR", "metric_id": "fin.trans_count_range", "leg": "atom", "anchor_id": "A-FIN-TRANS",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        # 干扰绑定
        {"binding_id": "B-FIN-PLC", "metric_id": "fin.problem_loan_count", "leg": "atom", "anchor_id": "A-FIN-LOAN",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-FIN-ALA", "metric_id": "fin.avg_loan_amount", "leg": "atom", "anchor_id": "A-FIN-LOAN",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
    ]
    edges = [
        {"edge_id": "fin.tg1", "domain": D, "axis": "time", "from_level": "day", "to_level": "month",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "fin.tg2", "domain": D, "axis": "time", "from_level": "month", "to_level": "year",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure, v2_patch={
            "fin.plr.num": {"preds": [{"col": "status", "op": "in", "value": ["D"]}]},
        }, id_field="measure_id"),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": [],  # D_v=∅ → ungoverned-disclosure 诚实标注
    }


# ---------------------------------------------------------------- card_games
ROTATION_V1 = ["KTK", "FRF", "DTK", "ORI", "BFZ"]
ROTATION_V2 = ["BFZ", "OGW", "SOI", "EMN", "KLD", "AER", "AKH", "HOU", "XLN"]

def seeds_card_games():
    D = "card_games"
    nodes = [
        {"node_id": "card.rulings", "domain": D, "physical_table": "rulings", "entity_key": "id", "scope_keys": {}},
        {"node_id": "card.cards", "domain": D, "physical_table": "cards", "entity_key": "uuid",
         "scope_keys": {"card_name": "name", "set_code": "setCode"}},
        {"node_id": "card.sets", "domain": D, "physical_table": "sets", "entity_key": "code", "scope_keys": {}},
        {"node_id": "card.legalities", "domain": D, "physical_table": "legalities", "entity_key": "id", "scope_keys": {}},
        {"node_id": "card.foreign_data", "domain": D, "physical_table": "foreign_data", "entity_key": "id", "scope_keys": {}},
        {"node_id": "card.set_translations", "domain": D, "physical_table": "set_translations", "entity_key": "id", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "card.ruling_intensity", "domain": D, "kind": "ratio", "num_node": "card.rulings", "den_node": "card.cards"},
        {"metric_id": "card.monthly_rulings", "domain": D, "kind": "atomic", "num_node": "card.rulings", "den_node": None},
        {"metric_id": "card.standard_card_count", "domain": D, "kind": "atomic", "num_node": "card.cards", "den_node": None},
        {"metric_id": "card.card_rulings_count", "domain": D, "kind": "atomic", "num_node": "card.rulings", "den_node": None},
        {"metric_id": "card.rulings_range", "domain": D, "kind": "atomic", "num_node": "card.rulings", "den_node": None},
        {"metric_id": "card.collector_premium", "domain": D, "kind": "ratio", "num_node": "card.cards", "den_node": "card.cards"},
        # 干扰
        {"metric_id": "card.foreign_coverage", "domain": D, "kind": "ratio", "num_node": "card.foreign_data", "den_node": "card.cards"},
        {"metric_id": "card.monthly_sets", "domain": D, "kind": "atomic", "num_node": "card.sets", "den_node": None},
    ]
    measure = [
        {"measure_id": "card.ri.num", "metric_id": "card.ruling_intensity", "leg": "num", "node_id": "card.rulings",
         "measure": "count", "preds": []},
        {"measure_id": "card.ri.den", "metric_id": "card.ruling_intensity", "leg": "den", "node_id": "card.cards",
         "measure": "count", "preds": []},
        {"measure_id": "card.mr.atom", "metric_id": "card.monthly_rulings", "leg": "atom", "node_id": "card.rulings",
         "measure": "count", "preds": []},
        {"measure_id": "card.scc.atom", "metric_id": "card.standard_card_count", "leg": "atom", "node_id": "card.cards",
         "measure": "count", "preds": [{"col": "setCode", "op": "in", "value": ROTATION_V1}]},
        {"measure_id": "card.crc.atom", "metric_id": "card.card_rulings_count", "leg": "atom", "node_id": "card.rulings",
         "measure": "count", "preds": []},
        {"measure_id": "card.rr.atom", "metric_id": "card.rulings_range", "leg": "atom", "node_id": "card.rulings",
         "measure": "count", "preds": []},
        {"measure_id": "card.cp.num", "metric_id": "card.collector_premium", "leg": "num", "node_id": "card.cards",
         "measure": "count", "preds": [{"col": "isReserved", "op": "=", "value": 1}]},
        {"measure_id": "card.cp.den", "metric_id": "card.collector_premium", "leg": "den", "node_id": "card.cards",
         "measure": "count", "preds": []},
        # 干扰
        {"measure_id": "card.fc.num", "metric_id": "card.foreign_coverage", "leg": "num", "node_id": "card.foreign_data",
         "measure": "count", "preds": []},
        {"measure_id": "card.fc.den", "metric_id": "card.foreign_coverage", "leg": "den", "node_id": "card.cards",
         "measure": "count", "preds": []},
        {"measure_id": "card.ms.atom", "metric_id": "card.monthly_sets", "leg": "atom", "node_id": "card.sets",
         "measure": "count", "preds": []},
    ]
    aliases = [
        {"alias_id": "card.al1", "alias_text": "裁定强度", "metric_id": "card.ruling_intensity"},
        {"alias_id": "card.al2", "alias_text": "当月裁定条数", "metric_id": "card.monthly_rulings"},
        {"alias_id": "card.al3", "alias_text": "轮替合法卡牌总数", "metric_id": "card.standard_card_count"},
        {"alias_id": "card.al4", "alias_text": "单卡当月裁定条数", "metric_id": "card.card_rulings_count"},
        {"alias_id": "card.al5", "alias_text": "区间裁定条数", "metric_id": "card.rulings_range"},
        {"alias_id": "card.al6", "alias_text": "保留卡收藏溢价率", "metric_id": "card.collector_premium"},
        # 干扰
        {"alias_id": "card.al7", "alias_text": "当月新发行套牌数", "metric_id": "card.monthly_sets"},
        {"alias_id": "card.al8", "alias_text": "外文覆盖率", "metric_id": "card.foreign_coverage"},
    ]
    routing = [
        {"routing_id": "card.rt1", "metric_id": "card.ruling_intensity", "leg": "num", "hop_seq": 0,
         "src_node": "card.rulings", "dst_node": "card.rulings", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "card.rt2", "metric_id": "card.ruling_intensity", "leg": "den", "hop_seq": 0,
         "src_node": "card.cards", "dst_node": "card.sets", "join_on": [["setCode", "code"]], "dst_caliber": "scoped"},
        {"routing_id": "card.rt3", "metric_id": "card.card_rulings_count", "leg": "scope", "hop_seq": 0,
         "src_node": "card.rulings", "dst_node": "card.cards", "join_on": [["uuid", "uuid"]], "dst_caliber": "scoped"},
        {"routing_id": "card.rt6", "metric_id": "card.standard_card_count", "leg": "atom", "hop_seq": 0,
         "src_node": "card.cards", "dst_node": "card.sets", "join_on": [["setCode", "code"]], "dst_caliber": "scoped"},
        # MC(i)：收藏溢价率无成本侧数据 → reference-only
        {"routing_id": "card.rt4", "metric_id": "card.collector_premium", "leg": "den", "hop_seq": 0,
         "src_node": "card.cards", "dst_node": "card.cards", "join_on": [], "dst_caliber": "none"},
        # 干扰
        {"routing_id": "card.rt5", "metric_id": "card.foreign_coverage", "leg": "num", "hop_seq": 0,
         "src_node": "card.foreign_data", "dst_node": "card.cards", "join_on": [["uuid", "uuid"]], "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-CARD-RUL", "node_id": "card.rulings", "anchor_type": "snapshot_effective_date",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        {"anchor_id": "A-CARD-SET", "node_id": "card.sets", "anchor_type": "snapshot_effective_date",
         "effective_col": "releaseDate", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-CARD-RI-N", "metric_id": "card.ruling_intensity", "leg": "num", "anchor_id": "A-CARD-RUL",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CARD-RI-D", "metric_id": "card.ruling_intensity", "leg": "den", "anchor_id": "A-CARD-SET",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CARD-MR", "metric_id": "card.monthly_rulings", "leg": "atom", "anchor_id": "A-CARD-RUL",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CARD-SCC", "metric_id": "card.standard_card_count", "leg": "atom", "anchor_id": "A-CARD-SET",
         "rule_id": "same_valid_time_window", "window_gran": "cum_day"},
        {"binding_id": "B-CARD-CRC", "metric_id": "card.card_rulings_count", "leg": "atom", "anchor_id": "A-CARD-RUL",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CARD-RR", "metric_id": "card.rulings_range", "leg": "atom", "anchor_id": "A-CARD-RUL",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        {"binding_id": "B-CARD-CP-N", "metric_id": "card.collector_premium", "leg": "num", "anchor_id": "A-CARD-SET",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CARD-CP-D", "metric_id": "card.collector_premium", "leg": "den", "anchor_id": "A-CARD-SET",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        # 干扰
        {"binding_id": "B-CARD-MS", "metric_id": "card.monthly_sets", "leg": "atom", "anchor_id": "A-CARD-SET",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
    ]
    edges = [
        {"edge_id": "card.tg1", "domain": D, "axis": "time", "from_level": "day", "to_level": "month",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    # 卡牌域路由需 cards 侧窗过 sets：num 腿 card_rulings_count 的 scope 需 rulings→cards
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure, v2_patch={
            "card.scc.atom": {"preds": [{"col": "setCode", "op": "in", "value": ROTATION_V2}]},
        }, id_field="measure_id"),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": [],
    }


# ---------------------------------------------------------------- codebase_community
def seeds_codebase():
    D = "codebase_community"
    nodes = [
        {"node_id": "code.posts", "domain": D, "physical_table": "posts", "entity_key": "Id", "scope_keys": {}},
        {"node_id": "code.users", "domain": D, "physical_table": "users", "entity_key": "Id",
         "scope_keys": {"user_id": "Id"}},
        {"node_id": "code.votes", "domain": D, "physical_table": "votes", "entity_key": "Id", "scope_keys": {}},
        {"node_id": "code.comments", "domain": D, "physical_table": "comments", "entity_key": "Id", "scope_keys": {}},
        {"node_id": "code.badges", "domain": D, "physical_table": "badges", "entity_key": "Id", "scope_keys": {}},
        {"node_id": "code.postHistory", "domain": D, "physical_table": "postHistory", "entity_key": "Id", "scope_keys": {}},
        {"node_id": "code.postLinks", "domain": D, "physical_table": "postLinks", "entity_key": "Id", "scope_keys": {}},
        {"node_id": "code.tags", "domain": D, "physical_table": "tags", "entity_key": "Id", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "code.accepted_rate", "domain": D, "kind": "ratio", "num_node": "code.posts", "den_node": "code.posts"},
        {"metric_id": "code.monthly_votes", "domain": D, "kind": "atomic", "num_node": "code.votes", "den_node": None},
        {"metric_id": "code.user_accepted_report", "domain": D, "kind": "report", "num_node": "code.posts",
         "den_node": None, "report_axis": "entity", "entity_node": "code.users"},
        {"metric_id": "code.daily_questions", "domain": D, "kind": "report", "num_node": "code.posts",
         "den_node": None, "report_axis": "time", "entity_node": "code.users"},
        {"metric_id": "code.user_location", "domain": D, "kind": "attribute", "num_node": "code.users", "den_node": None},
        {"metric_id": "code.top_answerer_roster", "domain": D, "kind": "roster", "num_node": "code.posts",
         "den_node": None, "entity_node": "code.users"},
        # 干扰
        {"metric_id": "code.answer_accept_share", "domain": D, "kind": "ratio", "num_node": "code.posts", "den_node": "code.posts"},
        {"metric_id": "code.monthly_badges", "domain": D, "kind": "atomic", "num_node": "code.badges", "den_node": None},
    ]
    measure = [
        {"measure_id": "code.ar.num", "metric_id": "code.accepted_rate", "leg": "num", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 2}]},
        {"measure_id": "code.ar.den", "metric_id": "code.accepted_rate", "leg": "den", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 1}]},
        {"measure_id": "code.mv.atom", "metric_id": "code.monthly_votes", "leg": "atom", "node_id": "code.votes",
         "measure": "count", "preds": []},
        {"measure_id": "code.uar.atom", "metric_id": "code.user_accepted_report", "leg": "atom", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 2}]},
        {"measure_id": "code.dq.atom", "metric_id": "code.daily_questions", "leg": "atom", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 1}]},
        {"measure_id": "code.ul.atom", "metric_id": "code.user_location", "leg": "atom", "node_id": "code.users",
         "measure": "value:Location", "preds": []},
        {"measure_id": "code.tar.atom", "metric_id": "code.top_answerer_roster", "leg": "atom", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 2}]},
        # 干扰（blind 分母=窗内答案）
        {"measure_id": "code.aas.num", "metric_id": "code.answer_accept_share", "leg": "num", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 2}]},
        {"measure_id": "code.aas.den", "metric_id": "code.answer_accept_share", "leg": "den", "node_id": "code.posts",
         "measure": "count", "preds": [{"col": "PostTypeId", "op": "=", "value": 2}]},
        {"measure_id": "code.mb.atom", "metric_id": "code.monthly_badges", "leg": "atom", "node_id": "code.badges",
         "measure": "count", "preds": []},
    ]
    aliases = [
        {"alias_id": "code.al1", "alias_text": "提问采纳率", "metric_id": "code.accepted_rate"},
        {"alias_id": "code.al2", "alias_text": "当月投票总数", "metric_id": "code.monthly_votes"},
        {"alias_id": "code.al3", "alias_text": "用户采纳答案数报表", "metric_id": "code.user_accepted_report"},
        {"alias_id": "code.al4", "alias_text": "新提问数报表", "metric_id": "code.daily_questions"},
        {"alias_id": "code.al5", "alias_text": "用户所在地", "metric_id": "code.user_location"},
        {"alias_id": "code.al6", "alias_text": "答题者名录", "metric_id": "code.top_answerer_roster"},
        # 干扰
        {"alias_id": "code.al7", "alias_text": "答案采纳率", "metric_id": "code.answer_accept_share"},
        {"alias_id": "code.al8", "alias_text": "当月徽章授予数", "metric_id": "code.monthly_badges"},
    ]
    routing = [
        # 采纳判定：答案 a 半连接提问 qq（qq.AcceptedAnswerId = a.Id）
        {"routing_id": "code.rt1", "metric_id": "code.accepted_rate", "leg": "num", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.posts", "join_on": [["Id", "AcceptedAnswerId"]],
         "dst_caliber": "scoped"},
        {"routing_id": "code.rt2", "metric_id": "code.accepted_rate", "leg": "den", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.posts", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "code.rt3", "metric_id": "code.user_accepted_report", "leg": "atom", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.posts", "join_on": [["Id", "AcceptedAnswerId"]],
         "dst_caliber": "scoped"},
        {"routing_id": "code.rt4", "metric_id": "code.user_accepted_report", "leg": "entity", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.users", "join_on": [["OwnerUserId", "Id"]],
         "dst_caliber": "scoped"},
        {"routing_id": "code.rt5", "metric_id": "code.top_answerer_roster", "leg": "atom", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.posts", "join_on": [["Id", "AcceptedAnswerId"]],
         "dst_caliber": "scoped"},
        {"routing_id": "code.rt6", "metric_id": "code.top_answerer_roster", "leg": "entity", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.users", "join_on": [["OwnerUserId", "Id"]],
         "dst_caliber": "scoped"},
        # 干扰
        {"routing_id": "code.rt7", "metric_id": "code.answer_accept_share", "leg": "num", "hop_seq": 0,
         "src_node": "code.posts", "dst_node": "code.posts", "join_on": [["Id", "AcceptedAnswerId"]],
         "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-CODE-POST", "node_id": "code.posts", "anchor_type": "snapshot_effective_date",
         "effective_col": "CreaionDate", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        {"anchor_id": "A-CODE-VOTE", "node_id": "code.votes", "anchor_type": "snapshot_effective_date",
         "effective_col": "CreationDate", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        {"anchor_id": "A-CODE-USER", "node_id": "code.users", "anchor_type": "snapshot_effective_date",
         "effective_col": "CreationDate", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-CODE-AR-N", "metric_id": "code.accepted_rate", "leg": "num", "anchor_id": "A-CODE-POST",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CODE-AR-D", "metric_id": "code.accepted_rate", "leg": "den", "anchor_id": "A-CODE-POST",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CODE-MV", "metric_id": "code.monthly_votes", "leg": "atom", "anchor_id": "A-CODE-VOTE",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CODE-UAR", "metric_id": "code.user_accepted_report", "leg": "atom", "anchor_id": "A-CODE-POST",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CODE-DQ", "metric_id": "code.daily_questions", "leg": "atom", "anchor_id": "A-CODE-POST",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-CODE-TAR", "metric_id": "code.top_answerer_roster", "leg": "atom", "anchor_id": "A-CODE-POST",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        # 干扰
        {"binding_id": "B-CODE-MB", "metric_id": "code.monthly_badges", "leg": "atom", "anchor_id": "A-CODE-USER",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
    ]
    edges = [
        {"edge_id": "code.eg1", "domain": D, "axis": "entity", "from_level": "user", "to_level": "reputation_band",
         "node_id": "code.users", "group_cols": [], "derived": [], "band_col": "Reputation",
         "band_bounds": [0, 100, 1000, 10000]},
        {"edge_id": "code.eg2", "domain": D, "axis": "entity", "from_level": "reputation_band", "to_level": "all",
         "node_id": "code.users", "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "code.tg1", "domain": D, "axis": "time", "from_level": "day", "to_level": "month",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    policies = [
        {"policy_id": "code.pi1", "domain": D, "kind": "mask", "node_id": "code.users",
         "cols": ["DisplayName", "Location", "AboutMe"], "mask_class": "generalize_last_component",
         "lattice_levels": [], "k": None, "time_floor_gran": None,
         "carry": [{"node_id": "code.posts", "col": "OwnerDisplayName", "via": [["OwnerUserId", "Id"]]}],
         "applies_to": "code.users"},
        {"policy_id": "code.pi2", "domain": D, "kind": "k_threshold", "node_id": "code.users", "cols": [],
         "mask_class": None, "lattice_levels": ["user", "reputation_band", "all"], "k": 5,
         "time_floor_gran": None, "carry": [], "applies_to": "code.users", "k_exempt_top": True},
        {"policy_id": "code.pi3", "domain": D, "kind": "present_only", "node_id": "code.users", "cols": ["Age"],
         "mask_class": "decade_band", "lattice_levels": [], "k": None, "time_floor_gran": None,
         "carry": [], "applies_to": "code.users"},
        {"policy_id": "code.pi4", "domain": D, "kind": "time_floor", "node_id": "code.users", "cols": [],
         "mask_class": None, "lattice_levels": [], "k": None, "time_floor_gran": "month",
         "carry": [], "applies_to": "code.users"},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure, v2_patch={
            "code.ar.den": {"preds": [{"col": "PostTypeId", "op": "=", "value": 1},
                                      {"col": "CommunityOwnedDate", "op": "is_null", "value": None}]},
        }, id_field="measure_id"),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": dual(policies),
    }


# ---------------------------------------------------------------- formula_1
def seeds_formula_1():
    D = "formula_1"
    nodes = [
        {"node_id": "f1.results", "domain": D, "physical_table": "results", "entity_key": "resultId", "scope_keys": {}},
        {"node_id": "f1.races", "domain": D, "physical_table": "races", "entity_key": "raceId", "scope_keys": {}},
        {"node_id": "f1.drivers", "domain": D, "physical_table": "drivers", "entity_key": "driverId",
         "scope_keys": {"driver": "driverRef"}},
        {"node_id": "f1.constructors", "domain": D, "physical_table": "constructors", "entity_key": "constructorId",
         "scope_keys": {"constructor": "constructorRef"}},
        {"node_id": "f1.points_scheme", "domain": D, "physical_table": "points_scheme", "entity_key": None, "scope_keys": {}},
        {"node_id": "f1.driverStandings", "domain": D, "physical_table": "driverStandings", "entity_key": "driverStandingsId", "scope_keys": {}},
        {"node_id": "f1.constructorStandings", "domain": D, "physical_table": "constructorStandings", "entity_key": "constructorStandingsId", "scope_keys": {}},
        {"node_id": "f1.lapTimes", "domain": D, "physical_table": "lapTimes", "entity_key": None, "scope_keys": {}},
        {"node_id": "f1.pitStops", "domain": D, "physical_table": "pitStops", "entity_key": None, "scope_keys": {}},
        {"node_id": "f1.qualifying", "domain": D, "physical_table": "qualifying", "entity_key": "qualifyId", "scope_keys": {}},
        {"node_id": "f1.circuits", "domain": D, "physical_table": "circuits", "entity_key": "circuitId", "scope_keys": {}},
        {"node_id": "f1.seasons", "domain": D, "physical_table": "seasons", "entity_key": "year", "scope_keys": {}},
        {"node_id": "f1.status", "domain": D, "physical_table": "status", "entity_key": "statusId", "scope_keys": {}},
        {"node_id": "f1.constructorResults", "domain": D, "physical_table": "constructorResults", "entity_key": "constructorResultsId", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "f1.driver_season_points", "domain": D, "kind": "atomic", "num_node": "f1.results", "den_node": None},
        {"metric_id": "f1.points_per_entry", "domain": D, "kind": "ratio", "num_node": "f1.results", "den_node": "f1.results"},
        {"metric_id": "f1.entry_count", "domain": D, "kind": "atomic", "num_node": "f1.results", "den_node": None},
        {"metric_id": "f1.races_count_month", "domain": D, "kind": "atomic", "num_node": "f1.races", "den_node": None},
        {"metric_id": "f1.races_count_range", "domain": D, "kind": "atomic", "num_node": "f1.races", "den_node": None},
        {"metric_id": "f1.season_points_delta", "domain": D, "kind": "delta", "num_node": "f1.results",
         "den_node": None, "base_metric_id": "f1.driver_season_points"},
        # 干扰：官方积分表直读（与治理重算口径分道，登记但不入金标路径）
        {"metric_id": "f1.official_standing_points", "domain": D, "kind": "atomic", "num_node": "f1.driverStandings", "den_node": None},
        {"metric_id": "f1.avg_lap_ms", "domain": D, "kind": "atomic", "num_node": "f1.lapTimes", "den_node": None},
    ]
    measure = [
        {"measure_id": "f1.dsp.atom", "metric_id": "f1.driver_season_points", "leg": "atom", "node_id": "f1.results",
         "measure": "sum:points_scheme.points",
         "preds": [{"node": "f1.points_scheme", "col": "scheme_id", "op": "=", "value": "PS2009"}]},
        {"measure_id": "f1.ppe.num", "metric_id": "f1.points_per_entry", "leg": "num", "node_id": "f1.results",
         "measure": "sum:points_scheme.points",
         "preds": [{"node": "f1.points_scheme", "col": "scheme_id", "op": "=", "value": "PS2009"}]},
        {"measure_id": "f1.ppe.den", "metric_id": "f1.points_per_entry", "leg": "den", "node_id": "f1.results",
         "measure": "count", "preds": []},
        {"measure_id": "f1.ec.atom", "metric_id": "f1.entry_count", "leg": "atom", "node_id": "f1.results",
         "measure": "count", "preds": []},
        {"measure_id": "f1.rcm.atom", "metric_id": "f1.races_count_month", "leg": "atom", "node_id": "f1.races",
         "measure": "count", "preds": []},
        {"measure_id": "f1.rcr.atom", "metric_id": "f1.races_count_range", "leg": "atom", "node_id": "f1.races",
         "measure": "count", "preds": []},
        # 干扰
        {"measure_id": "f1.osp.atom", "metric_id": "f1.official_standing_points", "leg": "atom",
         "node_id": "f1.driverStandings", "measure": "sum:points", "preds": []},
        {"measure_id": "f1.alm.atom", "metric_id": "f1.avg_lap_ms", "leg": "atom", "node_id": "f1.lapTimes",
         "measure": "avg:milliseconds", "preds": []},
    ]
    aliases = [
        {"alias_id": "f1.al1", "alias_text": "赛季车手总积分", "metric_id": "f1.driver_season_points"},
        {"alias_id": "f1.al2", "alias_text": "车队场均积分", "metric_id": "f1.points_per_entry"},
        {"alias_id": "f1.al3", "alias_text": "赛季参赛记录条数", "metric_id": "f1.entry_count"},
        {"alias_id": "f1.al4", "alias_text": "当月大奖赛场数", "metric_id": "f1.races_count_month"},
        {"alias_id": "f1.al5", "alias_text": "区间大奖赛场数", "metric_id": "f1.races_count_range"},
        {"alias_id": "f1.al6", "alias_text": "两季车手积分差", "metric_id": "f1.season_points_delta"},
        # 干扰（近义直觉词指向官方表直读）
        {"alias_id": "f1.al7", "alias_text": "官方积分榜总分", "metric_id": "f1.official_standing_points"},
        {"alias_id": "f1.al8", "alias_text": "平均圈速毫秒", "metric_id": "f1.avg_lap_ms"},
    ]
    routing = [
        {"routing_id": "f1.rt1", "metric_id": "f1.driver_season_points", "leg": "atom", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.races", "join_on": [["raceId", "raceId"]], "dst_caliber": "scoped"},
        {"routing_id": "f1.rt2", "metric_id": "f1.driver_season_points", "leg": "atom", "hop_seq": 1,
         "src_node": "f1.results", "dst_node": "f1.points_scheme", "join_on": [["positionOrder", "position"]],
         "dst_caliber": "scoped"},
        {"routing_id": "f1.rt3", "metric_id": "f1.driver_season_points", "leg": "scope", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.drivers", "join_on": [["driverId", "driverId"]], "dst_caliber": "scoped"},
        {"routing_id": "f1.rt4", "metric_id": "f1.points_per_entry", "leg": "num", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.races", "join_on": [["raceId", "raceId"]], "dst_caliber": "scoped"},
        {"routing_id": "f1.rt5", "metric_id": "f1.points_per_entry", "leg": "num", "hop_seq": 1,
         "src_node": "f1.results", "dst_node": "f1.points_scheme", "join_on": [["positionOrder", "position"]],
         "dst_caliber": "scoped"},
        {"routing_id": "f1.rt6", "metric_id": "f1.points_per_entry", "leg": "den", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.races", "join_on": [["raceId", "raceId"]], "dst_caliber": "scoped"},
        {"routing_id": "f1.rt7", "metric_id": "f1.points_per_entry", "leg": "scope", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.constructors", "join_on": [["constructorId", "constructorId"]],
         "dst_caliber": "scoped"},
        {"routing_id": "f1.rt8", "metric_id": "f1.entry_count", "leg": "atom", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.races", "join_on": [["raceId", "raceId"]], "dst_caliber": "scoped"},
        {"routing_id": "f1.rt9", "metric_id": "f1.entry_count", "leg": "scope", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.constructors", "join_on": [["constructorId", "constructorId"]],
         "dst_caliber": "scoped"},
        {"routing_id": "f1.rt10", "metric_id": "f1.season_points_delta", "leg": "atom", "hop_seq": 0,
         "src_node": "f1.results", "dst_node": "f1.races", "join_on": [["raceId", "raceId"]], "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-F1-RACE", "node_id": "f1.races", "anchor_type": "snapshot_effective_date",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-F1-DSP", "metric_id": "f1.driver_season_points", "leg": "atom", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-F1-PPE-N", "metric_id": "f1.points_per_entry", "leg": "num", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-F1-PPE-D", "metric_id": "f1.points_per_entry", "leg": "den", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-F1-EC", "metric_id": "f1.entry_count", "leg": "atom", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-F1-RCM", "metric_id": "f1.races_count_month", "leg": "atom", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-F1-RCR", "metric_id": "f1.races_count_range", "leg": "atom", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        {"binding_id": "B-F1-SPD", "metric_id": "f1.season_points_delta", "leg": "atom", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        # 干扰
        {"binding_id": "B-F1-OSP", "metric_id": "f1.official_standing_points", "leg": "atom", "anchor_id": "A-F1-RACE",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
    ]
    edges = [
        {"edge_id": "f1.tg1", "domain": D, "axis": "time", "from_level": "day", "to_level": "month",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "f1.tg2", "domain": D, "axis": "time", "from_level": "month", "to_level": "year",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure, v2_patch={
            "f1.dsp.atom": {"preds": [{"node": "f1.points_scheme", "col": "scheme_id", "op": "=", "value": "PS2010"}]},
            "f1.ppe.num": {"preds": [{"node": "f1.points_scheme", "col": "scheme_id", "op": "=", "value": "PS2010"}]},
        }, id_field="measure_id"),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": [],
    }


# ---------------------------------------------------------------- debit_card_specializing
def seeds_debit():
    D = "debit_card_specializing"
    nodes = [
        {"node_id": "deb.yearmonth", "domain": D, "physical_table": "yearmonth", "entity_key": "CustomerID", "scope_keys": {}},
        {"node_id": "deb.customers", "domain": D, "physical_table": "customers", "entity_key": "CustomerID",
         "scope_keys": {"currency": "Currency", "segment": "Segment"}},
        {"node_id": "deb.transactions_1k", "domain": D, "physical_table": "transactions_1k", "entity_key": "TransactionID", "scope_keys": {}},
        {"node_id": "deb.gasstations", "domain": D, "physical_table": "gasstations", "entity_key": "GasStationID",
         "scope_keys": {"country": "Country"}},
        {"node_id": "deb.products", "domain": D, "physical_table": "products", "entity_key": "ProductID", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "deb.avg_consumption", "domain": D, "kind": "atomic", "num_node": "deb.yearmonth", "den_node": None},
        {"metric_id": "deb.consumption_sum", "domain": D, "kind": "atomic", "num_node": "deb.yearmonth", "den_node": None},
        {"metric_id": "deb.segment_avg_trans", "domain": D, "kind": "report", "num_node": "deb.transactions_1k",
         "den_node": None, "report_axis": "entity", "entity_node": "deb.customers"},
        {"metric_id": "deb.price_margin", "domain": D, "kind": "ratio", "num_node": "deb.transactions_1k", "den_node": "deb.products"},
        # 干扰
        {"metric_id": "deb.station_trans_count", "domain": D, "kind": "atomic", "num_node": "deb.transactions_1k", "den_node": None},
    ]
    measure = [
        {"measure_id": "deb.ac.atom", "metric_id": "deb.avg_consumption", "leg": "atom", "node_id": "deb.yearmonth",
         "measure": "avg:Consumption", "preds": []},
        {"measure_id": "deb.cs.atom", "metric_id": "deb.consumption_sum", "leg": "atom", "node_id": "deb.yearmonth",
         "measure": "sum:Consumption", "preds": []},
        {"measure_id": "deb.sat.atom", "metric_id": "deb.segment_avg_trans", "leg": "atom", "node_id": "deb.transactions_1k",
         "measure": "avg:Amount", "preds": []},
        {"measure_id": "deb.pm.num", "metric_id": "deb.price_margin", "leg": "num", "node_id": "deb.transactions_1k",
         "measure": "avg:Price", "preds": []},
        {"measure_id": "deb.pm.den", "metric_id": "deb.price_margin", "leg": "den", "node_id": "deb.products",
         "measure": "count", "preds": []},
        # 干扰
        {"measure_id": "deb.stc.atom", "metric_id": "deb.station_trans_count", "leg": "atom",
         "node_id": "deb.transactions_1k", "measure": "count", "preds": []},
    ]
    aliases = [
        {"alias_id": "deb.al1", "alias_text": "月均客户消费额", "metric_id": "deb.avg_consumption"},
        {"alias_id": "deb.al2", "alias_text": "月消费总额", "metric_id": "deb.consumption_sum"},
        {"alias_id": "deb.al3", "alias_text": "细分平均单笔交易金额", "metric_id": "deb.segment_avg_trans"},
        {"alias_id": "deb.al4", "alias_text": "价格毛利率", "metric_id": "deb.price_margin"},
        # 干扰
        {"alias_id": "deb.al5", "alias_text": "站点交易笔数", "metric_id": "deb.station_trans_count"},
    ]
    routing = [
        {"routing_id": "deb.rt1", "metric_id": "deb.avg_consumption", "leg": "scope", "hop_seq": 0,
         "src_node": "deb.yearmonth", "dst_node": "deb.customers", "join_on": [["CustomerID", "CustomerID"]],
         "dst_caliber": "scoped"},
        {"routing_id": "deb.rt2", "metric_id": "deb.consumption_sum", "leg": "scope", "hop_seq": 0,
         "src_node": "deb.yearmonth", "dst_node": "deb.customers", "join_on": [["CustomerID", "CustomerID"]],
         "dst_caliber": "scoped"},
        {"routing_id": "deb.rt3", "metric_id": "deb.segment_avg_trans", "leg": "scope", "hop_seq": 0,
         "src_node": "deb.transactions_1k", "dst_node": "deb.customers", "join_on": [["CustomerID", "CustomerID"]],
         "dst_caliber": "scoped"},
        {"routing_id": "deb.rt4", "metric_id": "deb.segment_avg_trans", "leg": "entity", "hop_seq": 0,
         "src_node": "deb.transactions_1k", "dst_node": "deb.customers", "join_on": [["CustomerID", "CustomerID"]],
         "dst_caliber": "scoped"},
        # MC(i)：价格毛利率无成本侧 → reference-only
        {"routing_id": "deb.rt5", "metric_id": "deb.price_margin", "leg": "den", "hop_seq": 0,
         "src_node": "deb.transactions_1k", "dst_node": "deb.products", "join_on": [["ProductID", "ProductID"]],
         "dst_caliber": "none"},
        # 干扰
        {"routing_id": "deb.rt6", "metric_id": "deb.station_trans_count", "leg": "scope", "hop_seq": 0,
         "src_node": "deb.transactions_1k", "dst_node": "deb.gasstations", "join_on": [["GasStationID", "GasStationID"]],
         "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-DEB-YM", "node_id": "deb.yearmonth", "anchor_type": "date_set",
         "effective_col": "Date", "vf_col": None, "vtc_col": None, "granularity": "month_token_yyyymm",
         "coverage_mode": "strict_member"},
        {"anchor_id": "A-DEB-T1K", "node_id": "deb.transactions_1k", "anchor_type": "snapshot_effective_date",
         "effective_col": "Date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-DEB-AC", "metric_id": "deb.avg_consumption", "leg": "atom", "anchor_id": "A-DEB-YM",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
        {"binding_id": "B-DEB-CS", "metric_id": "deb.consumption_sum", "leg": "atom", "anchor_id": "A-DEB-YM",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
        {"binding_id": "B-DEB-SAT", "metric_id": "deb.segment_avg_trans", "leg": "atom", "anchor_id": "A-DEB-T1K",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        {"binding_id": "B-DEB-PM-N", "metric_id": "deb.price_margin", "leg": "num", "anchor_id": "A-DEB-T1K",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-DEB-PM-D", "metric_id": "deb.price_margin", "leg": "den", "anchor_id": "A-DEB-T1K",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        # 干扰
        {"binding_id": "B-DEB-STC", "metric_id": "deb.station_trans_count", "leg": "atom", "anchor_id": "A-DEB-T1K",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
    ]
    edges = [
        {"edge_id": "deb.eg1", "domain": D, "axis": "entity", "from_level": "customer", "to_level": "Segment",
         "node_id": "deb.customers", "group_cols": ["Segment"], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "deb.eg2", "domain": D, "axis": "entity", "from_level": "Segment", "to_level": "all",
         "node_id": "deb.customers", "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "deb.tg1", "domain": D, "axis": "time", "from_level": "day", "to_level": "month",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    policies = [
        {"policy_id": "deb.pi1", "domain": D, "kind": "k_threshold", "node_id": "deb.customers", "cols": [],
         "mask_class": None, "lattice_levels": ["customer", "Segment", "all"], "k": 10,
         "time_floor_gran": None, "carry": [], "applies_to": "deb.customers", "k_exempt_top": True},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        # RC-7×RC-8 交互：披露策略本身版本化，k 10→20
        "gov_disclosure_policy": dual(policies, v2_patch={"deb.pi1": {"k": 20}}, id_field="policy_id"),
    }


# ---------------------------------------------------------------- european_football_2
def seeds_ef2():
    D = "european_football_2"
    nodes = [
        {"node_id": "ef2.player_attr", "domain": D, "physical_table": "Player_Attributes", "entity_key": "id", "scope_keys": {}},
        {"node_id": "ef2.match", "domain": D, "physical_table": "Match", "entity_key": "id",
         "scope_keys": {"season": "season"}},
        {"node_id": "ef2.league", "domain": D, "physical_table": "League", "entity_key": "id",
         "scope_keys": {"league": "name"}},
        {"node_id": "ef2.player", "domain": D, "physical_table": "Player", "entity_key": "id", "scope_keys": {}},
        {"node_id": "ef2.team", "domain": D, "physical_table": "Team", "entity_key": "id", "scope_keys": {}},
        {"node_id": "ef2.team_attr", "domain": D, "physical_table": "Team_Attributes", "entity_key": "id", "scope_keys": {}},
        {"node_id": "ef2.country", "domain": D, "physical_table": "Country", "entity_key": "id", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "ef2.avg_overall_rating", "domain": D, "kind": "atomic", "num_node": "ef2.player_attr", "den_node": None},
        {"metric_id": "ef2.win_rate", "domain": D, "kind": "ratio", "num_node": "ef2.match", "den_node": "ef2.match"},
        {"metric_id": "ef2.pa_month_count", "domain": D, "kind": "atomic", "num_node": "ef2.player_attr", "den_node": None},
        {"metric_id": "ef2.matches_range", "domain": D, "kind": "atomic", "num_node": "ef2.match", "den_node": None},
        {"metric_id": "ef2.rating_weighted_win_rate", "domain": D, "kind": "ratio", "num_node": "ef2.match",
         "den_node": "ef2.player_attr"},
        # 干扰
        {"metric_id": "ef2.team_buildup_speed", "domain": D, "kind": "atomic", "num_node": "ef2.team_attr", "den_node": None},
        {"metric_id": "ef2.goal_sum_month", "domain": D, "kind": "atomic", "num_node": "ef2.match", "den_node": None},
    ]
    measure = [
        {"measure_id": "ef2.aor.atom", "metric_id": "ef2.avg_overall_rating", "leg": "atom", "node_id": "ef2.player_attr",
         "measure": "avg:overall_rating", "preds": []},
        # 胜率：v1 平局计半胜（两行加权），v2 平局归零（单行）
        {"measure_id": "ef2.wr.num.win", "metric_id": "ef2.win_rate", "leg": "num", "node_id": "ef2.match",
         "measure": "count", "preds": [{"col": "home_team_goal", "op": ">col", "value": "away_team_goal"}], "weight": 1.0},
        {"measure_id": "ef2.wr.num.draw", "metric_id": "ef2.win_rate", "leg": "num", "node_id": "ef2.match",
         "measure": "count", "preds": [{"col": "home_team_goal", "op": "=col", "value": "away_team_goal"}], "weight": 0.5},
        {"measure_id": "ef2.wr.den", "metric_id": "ef2.win_rate", "leg": "den", "node_id": "ef2.match",
         "measure": "count", "preds": []},
        {"measure_id": "ef2.pmc.atom", "metric_id": "ef2.pa_month_count", "leg": "atom", "node_id": "ef2.player_attr",
         "measure": "count", "preds": []},
        {"measure_id": "ef2.mr.atom", "metric_id": "ef2.matches_range", "leg": "atom", "node_id": "ef2.match",
         "measure": "count", "preds": []},
        {"measure_id": "ef2.rwwr.num", "metric_id": "ef2.rating_weighted_win_rate", "leg": "num", "node_id": "ef2.match",
         "measure": "count", "preds": [{"col": "home_team_goal", "op": ">col", "value": "away_team_goal"}]},
        {"measure_id": "ef2.rwwr.den", "metric_id": "ef2.rating_weighted_win_rate", "leg": "den", "node_id": "ef2.player_attr",
         "measure": "avg:overall_rating", "preds": []},
        # 干扰
        {"measure_id": "ef2.tbs.atom", "metric_id": "ef2.team_buildup_speed", "leg": "atom", "node_id": "ef2.team_attr",
         "measure": "avg:buildUpPlaySpeed", "preds": []},
        {"measure_id": "ef2.gsm.atom", "metric_id": "ef2.goal_sum_month", "leg": "atom", "node_id": "ef2.match",
         "measure": "sum:home_team_goal", "preds": []},
    ]
    aliases = [
        {"alias_id": "ef2.al1", "alias_text": "快照日球员平均综合评分", "metric_id": "ef2.avg_overall_rating"},
        {"alias_id": "ef2.al2", "alias_text": "主场胜率", "metric_id": "ef2.win_rate"},
        {"alias_id": "ef2.al3", "alias_text": "当月球员属性快照条数", "metric_id": "ef2.pa_month_count"},
        {"alias_id": "ef2.al4", "alias_text": "区间比赛场数", "metric_id": "ef2.matches_range"},
        {"alias_id": "ef2.al5", "alias_text": "评分归一当日胜率", "metric_id": "ef2.rating_weighted_win_rate"},
        # 干扰
        {"alias_id": "ef2.al6", "alias_text": "球队推进速度均值", "metric_id": "ef2.team_buildup_speed"},
        {"alias_id": "ef2.al7", "alias_text": "当月主队进球总数", "metric_id": "ef2.goal_sum_month"},
    ]
    routing = [
        {"routing_id": "ef2.rt1", "metric_id": "ef2.win_rate", "leg": "scope", "hop_seq": 0,
         "src_node": "ef2.match", "dst_node": "ef2.league", "join_on": [["league_id", "id"]], "dst_caliber": "scoped"},
        {"routing_id": "ef2.rt2", "metric_id": "ef2.rating_weighted_win_rate", "leg": "num", "hop_seq": 0,
         "src_node": "ef2.match", "dst_node": "ef2.match", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "ef2.rt3", "metric_id": "ef2.rating_weighted_win_rate", "leg": "den", "hop_seq": 0,
         "src_node": "ef2.player_attr", "dst_node": "ef2.player_attr", "join_on": [], "dst_caliber": "all"},
        # 干扰
        {"routing_id": "ef2.rt4", "metric_id": "ef2.goal_sum_month", "leg": "scope", "hop_seq": 0,
         "src_node": "ef2.match", "dst_node": "ef2.league", "join_on": [["league_id", "id"]], "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-EF2-PA", "node_id": "ef2.player_attr", "anchor_type": "date_set",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "strict_member"},
        {"anchor_id": "A-EF2-MATCH", "node_id": "ef2.match", "anchor_type": "snapshot_effective_date",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        # 干扰锚
        {"anchor_id": "A-EF2-TA", "node_id": "ef2.team_attr", "anchor_type": "date_set",
         "effective_col": "date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "strict_member"},
    ]
    bindings = [
        {"binding_id": "B-EF2-AOR", "metric_id": "ef2.avg_overall_rating", "leg": "atom", "anchor_id": "A-EF2-PA",
         "rule_id": "same_valid_time_window", "window_gran": "member_day"},
        {"binding_id": "B-EF2-WR-N", "metric_id": "ef2.win_rate", "leg": "num", "anchor_id": "A-EF2-MATCH",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        {"binding_id": "B-EF2-WR-D", "metric_id": "ef2.win_rate", "leg": "den", "anchor_id": "A-EF2-MATCH",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        {"binding_id": "B-EF2-PMC", "metric_id": "ef2.pa_month_count", "leg": "atom", "anchor_id": "A-EF2-PA",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
        {"binding_id": "B-EF2-MR", "metric_id": "ef2.matches_range", "leg": "atom", "anchor_id": "A-EF2-MATCH",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        {"binding_id": "B-EF2-RWWR-N", "metric_id": "ef2.rating_weighted_win_rate", "leg": "num",
         "anchor_id": "A-EF2-MATCH", "rule_id": "same_valid_time_window", "window_gran": "day"},
        {"binding_id": "B-EF2-RWWR-D", "metric_id": "ef2.rating_weighted_win_rate", "leg": "den",
         "anchor_id": "A-EF2-PA", "rule_id": "same_valid_time_window", "window_gran": "day"},
        # 干扰
        {"binding_id": "B-EF2-TBS", "metric_id": "ef2.team_buildup_speed", "leg": "atom", "anchor_id": "A-EF2-TA",
         "rule_id": "same_valid_time_window", "window_gran": "member_day"},
        {"binding_id": "B-EF2-GSM", "metric_id": "ef2.goal_sum_month", "leg": "atom", "anchor_id": "A-EF2-MATCH",
         "rule_id": "same_valid_time_window", "window_gran": "month"},
    ]
    edges = [
        {"edge_id": "ef2.tg1", "domain": D, "axis": "time", "from_level": "day", "to_level": "month",
         "node_id": None, "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure, id_field="measure_id",
                                drop_in_v2=("ef2.wr.num.draw",)),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": [],
    }


# ---------------------------------------------------------------- california_schools
def seeds_ca_schools():
    D = "california_schools"
    nodes = [
        {"node_id": "ca.schools", "domain": D, "physical_table": "schools", "entity_key": "CDSCode",
         "scope_keys": {"county": "County"}},
        {"node_id": "ca.frpm", "domain": D, "physical_table": "frpm", "entity_key": "CDSCode",
         "scope_keys": {"county": "County Name", "district": "District Name"}},
        {"node_id": "ca.satscores", "domain": D, "physical_table": "satscores", "entity_key": "cds", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "ca.free_meal_rate", "domain": D, "kind": "ratio", "num_node": "ca.frpm", "den_node": "ca.frpm"},
        {"metric_id": "ca.schools_in_effect", "domain": D, "kind": "atomic", "num_node": "ca.schools", "den_node": None},
        {"metric_id": "ca.school_frpm_report", "domain": D, "kind": "report", "num_node": "ca.frpm",
         "den_node": None, "report_axis": "entity", "entity_node": "ca.frpm", "base_metric_id": "ca.free_meal_rate"},
        # 干扰
        {"metric_id": "ca.avg_sat_math", "domain": D, "kind": "atomic", "num_node": "ca.satscores", "den_node": None},
        {"metric_id": "ca.charter_school_count", "domain": D, "kind": "atomic", "num_node": "ca.schools", "den_node": None},
    ]
    measure = [
        {"measure_id": "ca.fmr.num", "metric_id": "ca.free_meal_rate", "leg": "num", "node_id": "ca.frpm",
         "measure": "sum:Free Meal Count (K-12)", "preds": []},
        {"measure_id": "ca.fmr.den", "metric_id": "ca.free_meal_rate", "leg": "den", "node_id": "ca.frpm",
         "measure": "sum:Enrollment (K-12)", "preds": []},
        {"measure_id": "ca.sie.atom", "metric_id": "ca.schools_in_effect", "leg": "atom", "node_id": "ca.schools",
         "measure": "count", "preds": []},
        {"measure_id": "ca.sfr.atom", "metric_id": "ca.school_frpm_report", "leg": "atom", "node_id": "ca.frpm",
         "measure": "ratio_of_base", "preds": []},
        # 干扰
        {"measure_id": "ca.asm.atom", "metric_id": "ca.avg_sat_math", "leg": "atom", "node_id": "ca.satscores",
         "measure": "avg:AvgScrMath", "preds": []},
        {"measure_id": "ca.csc.atom", "metric_id": "ca.charter_school_count", "leg": "atom", "node_id": "ca.schools",
         "measure": "count", "preds": [{"col": "Charter", "op": "=", "value": 1}]},
    ]
    aliases = [
        {"alias_id": "ca.al1", "alias_text": "免费餐率", "metric_id": "ca.free_meal_rate"},
        {"alias_id": "ca.al2", "alias_text": "时点在效学校数", "metric_id": "ca.schools_in_effect"},
        {"alias_id": "ca.al3", "alias_text": "校级免费餐率报表", "metric_id": "ca.school_frpm_report"},
        # 干扰
        {"alias_id": "ca.al4", "alias_text": "平均数学成绩", "metric_id": "ca.avg_sat_math"},
        {"alias_id": "ca.al5", "alias_text": "特许学校数", "metric_id": "ca.charter_school_count"},
    ]
    routing = [
        {"routing_id": "ca.rt1", "metric_id": "ca.free_meal_rate", "leg": "num", "hop_seq": 0,
         "src_node": "ca.frpm", "dst_node": "ca.frpm", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "ca.rt2", "metric_id": "ca.free_meal_rate", "leg": "den", "hop_seq": 0,
         "src_node": "ca.frpm", "dst_node": "ca.frpm", "join_on": [], "dst_caliber": "all"},
    ]
    anchors = [
        {"anchor_id": "A-CA-SCD", "node_id": "ca.schools", "anchor_type": "scd_type2",
         "effective_col": None, "vf_col": "OpenDate", "vtc_col": "ClosedDate", "granularity": "day",
         "coverage_mode": "hull"},
        {"anchor_id": "A-CA-FRPM", "node_id": "ca.frpm", "anchor_type": "date_set",
         "effective_col": "Academic Year", "vf_col": None, "vtc_col": None,
         "granularity": "academic_year_token", "coverage_mode": "strict_member"},
    ]
    bindings = [
        {"binding_id": "B-CA-FMR-N", "metric_id": "ca.free_meal_rate", "leg": "num", "anchor_id": "A-CA-FRPM",
         "rule_id": "same_valid_time_window", "window_gran": "academic_year_token"},
        {"binding_id": "B-CA-FMR-D", "metric_id": "ca.free_meal_rate", "leg": "den", "anchor_id": "A-CA-FRPM",
         "rule_id": "same_valid_time_window", "window_gran": "academic_year_token"},
        {"binding_id": "B-CA-SIE", "metric_id": "ca.schools_in_effect", "leg": "atom", "anchor_id": "A-CA-SCD",
         "rule_id": "point_in_effect", "window_gran": "day"},
        {"binding_id": "B-CA-SFR", "metric_id": "ca.school_frpm_report", "leg": "atom", "anchor_id": "A-CA-FRPM",
         "rule_id": "same_valid_time_window", "window_gran": "academic_year_token"},
        # 干扰
        {"binding_id": "B-CA-CSC", "metric_id": "ca.charter_school_count", "leg": "atom", "anchor_id": "A-CA-SCD",
         "rule_id": "point_in_effect", "window_gran": "day"},
    ]
    edges = [
        {"edge_id": "ca.eg1", "domain": D, "axis": "entity", "from_level": "school", "to_level": "district",
         "node_id": "ca.frpm", "group_cols": ["District Name"], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "ca.eg2", "domain": D, "axis": "entity", "from_level": "district", "to_level": "county",
         "node_id": "ca.frpm", "group_cols": ["County Name"], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "ca.eg3", "domain": D, "axis": "entity", "from_level": "county", "to_level": "all",
         "node_id": "ca.frpm", "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    policies = [
        {"policy_id": "ca.pi1", "domain": D, "kind": "k_threshold", "node_id": "ca.frpm", "cols": [],
         "mask_class": None, "lattice_levels": ["school", "district", "county", "all"], "k": 10,
         "time_floor_gran": None, "carry": [], "applies_to": "ca.frpm", "k_exempt_top": True},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure, v2_patch={
            "ca.fmr.num": {"measure": "sum:Free Meal Count (Ages 5-17)", "preds": []},
            "ca.fmr.den": {"measure": "sum:Enrollment (Ages 5-17)", "preds": []},
        }, id_field="measure_id"),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": dual(policies),
    }


# ---------------------------------------------------------------- thrombosis_prediction
def seeds_thrombosis():
    D = "thrombosis_prediction"
    nodes = [
        {"node_id": "th.laboratory", "domain": D, "physical_table": "Laboratory", "entity_key": "ID", "scope_keys": {}},
        {"node_id": "th.patient", "domain": D, "physical_table": "Patient", "entity_key": "ID",
         "scope_keys": {"patient_id": "ID"}},
        {"node_id": "th.examination", "domain": D, "physical_table": "Examination", "entity_key": "ID", "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "th.abnormal_lab_rate", "domain": D, "kind": "ratio", "num_node": "th.laboratory", "den_node": "th.laboratory"},
        {"metric_id": "th.exam_count", "domain": D, "kind": "atomic", "num_node": "th.examination", "den_node": None},
        {"metric_id": "th.patient_abnormal_report", "domain": D, "kind": "report", "num_node": "th.laboratory",
         "den_node": None, "report_axis": "entity", "entity_node": "th.patient"},
        {"metric_id": "th.patient_birthday", "domain": D, "kind": "attribute", "num_node": "th.patient", "den_node": None},
        {"metric_id": "th.patient_roster", "domain": D, "kind": "roster", "num_node": "th.laboratory",
         "den_node": None, "entity_node": "th.patient"},
        # 干扰
        {"metric_id": "th.ana_positive_count", "domain": D, "kind": "atomic", "num_node": "th.examination", "den_node": None},
    ]
    measure = [
        {"measure_id": "th.alr.num", "metric_id": "th.abnormal_lab_rate", "leg": "num", "node_id": "th.laboratory",
         "measure": "count", "preds": [{"col": "GOT", "op": ">=", "value": 60}]},
        {"measure_id": "th.alr.den", "metric_id": "th.abnormal_lab_rate", "leg": "den", "node_id": "th.laboratory",
         "measure": "count", "preds": []},
        {"measure_id": "th.ec.atom", "metric_id": "th.exam_count", "leg": "atom", "node_id": "th.examination",
         "measure": "count", "preds": []},
        {"measure_id": "th.par.atom", "metric_id": "th.patient_abnormal_report", "leg": "atom", "node_id": "th.laboratory",
         "measure": "count", "preds": [{"col": "GOT", "op": ">=", "value": 60}]},
        {"measure_id": "th.pb.atom", "metric_id": "th.patient_birthday", "leg": "atom", "node_id": "th.patient",
         "measure": "value:Birthday", "preds": []},
        {"measure_id": "th.pr.atom", "metric_id": "th.patient_roster", "leg": "atom", "node_id": "th.laboratory",
         "measure": "count", "preds": [{"col": "GOT", "op": ">=", "value": 60}]},
        # 干扰
        {"measure_id": "th.apc.atom", "metric_id": "th.ana_positive_count", "leg": "atom", "node_id": "th.examination",
         "measure": "count", "preds": [{"col": "ANA", "op": "not_null", "value": None}]},
    ]
    aliases = [
        {"alias_id": "th.al1", "alias_text": "异常化验率", "metric_id": "th.abnormal_lab_rate"},
        {"alias_id": "th.al2", "alias_text": "年度检查记录数", "metric_id": "th.exam_count"},
        {"alias_id": "th.al3", "alias_text": "患者异常化验报表", "metric_id": "th.patient_abnormal_report"},
        {"alias_id": "th.al4", "alias_text": "患者出生日期", "metric_id": "th.patient_birthday"},
        {"alias_id": "th.al5", "alias_text": "异常化验患者名录", "metric_id": "th.patient_roster"},
        # 干扰
        {"alias_id": "th.al6", "alias_text": "抗核抗体检出数", "metric_id": "th.ana_positive_count"},
    ]
    routing = [
        {"routing_id": "th.rt1", "metric_id": "th.abnormal_lab_rate", "leg": "num", "hop_seq": 0,
         "src_node": "th.laboratory", "dst_node": "th.laboratory", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "th.rt2", "metric_id": "th.abnormal_lab_rate", "leg": "den", "hop_seq": 0,
         "src_node": "th.laboratory", "dst_node": "th.laboratory", "join_on": [], "dst_caliber": "all"},
        {"routing_id": "th.rt3", "metric_id": "th.patient_abnormal_report", "leg": "entity", "hop_seq": 0,
         "src_node": "th.laboratory", "dst_node": "th.patient", "join_on": [["ID", "ID"]], "dst_caliber": "scoped"},
        {"routing_id": "th.rt4", "metric_id": "th.patient_roster", "leg": "entity", "hop_seq": 0,
         "src_node": "th.laboratory", "dst_node": "th.patient", "join_on": [["ID", "ID"]], "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-TH-LAB", "node_id": "th.laboratory", "anchor_type": "snapshot_effective_date",
         "effective_col": "Date", "vf_col": None, "vtc_col": None, "granularity": "day", "coverage_mode": "hull"},
        {"anchor_id": "A-TH-EXAM", "node_id": "th.examination", "anchor_type": "snapshot_effective_date",
         "effective_col": "Examination Date", "vf_col": None, "vtc_col": None, "granularity": "day",
         "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-TH-ALR-N", "metric_id": "th.abnormal_lab_rate", "leg": "num", "anchor_id": "A-TH-LAB",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-TH-ALR-D", "metric_id": "th.abnormal_lab_rate", "leg": "den", "anchor_id": "A-TH-LAB",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-TH-EC", "metric_id": "th.exam_count", "leg": "atom", "anchor_id": "A-TH-EXAM",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-TH-PAR", "metric_id": "th.patient_abnormal_report", "leg": "atom", "anchor_id": "A-TH-LAB",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        {"binding_id": "B-TH-PRO", "metric_id": "th.patient_roster", "leg": "atom", "anchor_id": "A-TH-LAB",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
        # 干扰（AM(iv) 素材：检查日锚×化验日锚双 hull 错位）
        {"binding_id": "B-TH-APC", "metric_id": "th.ana_positive_count", "leg": "atom", "anchor_id": "A-TH-EXAM",
         "rule_id": "same_valid_time_window", "window_gran": "year"},
    ]
    edges = [
        {"edge_id": "th.eg1", "domain": D, "axis": "entity", "from_level": "patient", "to_level": "cohort",
         "node_id": "th.patient", "group_cols": ["SEX"], "derived": [{"col": "Birthday", "fn": "decade"}],
         "band_col": None, "band_bounds": []},
        {"edge_id": "th.eg2", "domain": D, "axis": "entity", "from_level": "cohort", "to_level": "sex",
         "node_id": "th.patient", "group_cols": ["SEX"], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "th.eg3", "domain": D, "axis": "entity", "from_level": "sex", "to_level": "all",
         "node_id": "th.patient", "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    policies = [
        {"policy_id": "th.pi1", "domain": D, "kind": "mask", "node_id": "th.patient",
         "cols": ["Birthday"], "mask_class": "year_month", "lattice_levels": [], "k": None,
         "time_floor_gran": None, "carry": [], "applies_to": "th.patient"},
        {"policy_id": "th.pi2", "domain": D, "kind": "k_threshold", "node_id": "th.patient", "cols": [],
         "mask_class": None, "lattice_levels": ["patient", "cohort", "sex", "all"], "k": 10,
         "time_floor_gran": None, "carry": [], "applies_to": "th.patient", "k_exempt_top": True},
        {"policy_id": "th.pi3", "domain": D, "kind": "mask", "node_id": "th.patient",
         "cols": ["Diagnosis"], "mask_class": "category_first_token", "lattice_levels": [], "k": None,
         "time_floor_gran": None, "carry": [], "applies_to": "th.patient"},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        "gov_measure_def": dual(measure),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        # 掩码强度 v1 年月 → v2 仅年份
        "gov_disclosure_policy": dual(policies, v2_patch={"th.pi1": {"mask_class": "year_only"}},
                                      id_field="policy_id"),
    }


# ---------------------------------------------------------------- world_1
def seeds_world_1():
    D = "world_1"
    nodes = [
        {"node_id": "w1.country", "domain": D, "physical_table": "country", "entity_key": "Code",
         "scope_keys": {"continent": "Continent"}},
        {"node_id": "w1.country_history", "domain": D, "physical_table": "country_history", "entity_key": None,
         "scope_keys": {}},
    ]
    metrics = [
        {"metric_id": "w1.asia_population_sum", "domain": D, "kind": "atomic", "num_node": "w1.country_history", "den_node": None},
        {"metric_id": "w1.world_population_sum", "domain": D, "kind": "atomic", "num_node": "w1.country_history", "den_node": None},
        {"metric_id": "w1.population_share", "domain": D, "kind": "ratio", "num_node": "w1.country_history",
         "den_node": "w1.country_history"},
        {"metric_id": "w1.history_rows_range", "domain": D, "kind": "atomic", "num_node": "w1.country_history", "den_node": None},
        # 干扰
        {"metric_id": "w1.gnp_sum", "domain": D, "kind": "atomic", "num_node": "w1.country_history", "den_node": None},
        {"metric_id": "w1.country_count", "domain": D, "kind": "atomic", "num_node": "w1.country", "den_node": None},
    ]
    measure = [
        {"measure_id": "w1.aps.atom", "metric_id": "w1.asia_population_sum", "leg": "atom", "node_id": "w1.country_history",
         "measure": "sum:population",
         "preds": [{"node": "w1.country", "col": "Continent", "op": "=", "value": "Asia"}]},
        {"measure_id": "w1.wps.atom", "metric_id": "w1.world_population_sum", "leg": "atom", "node_id": "w1.country_history",
         "measure": "sum:population", "preds": []},
        {"measure_id": "w1.ps.num", "metric_id": "w1.population_share", "leg": "num", "node_id": "w1.country_history",
         "measure": "sum:population",
         "preds": [{"node": "w1.country", "col": "Continent", "op": "=", "value": "Asia"}]},
        {"measure_id": "w1.ps.den", "metric_id": "w1.population_share", "leg": "den", "node_id": "w1.country_history",
         "measure": "sum:population", "preds": []},
        {"measure_id": "w1.hrr.atom", "metric_id": "w1.history_rows_range", "leg": "atom", "node_id": "w1.country_history",
         "measure": "count", "preds": []},
        # 干扰
        {"measure_id": "w1.gs.atom", "metric_id": "w1.gnp_sum", "leg": "atom", "node_id": "w1.country_history",
         "measure": "sum:gnp", "preds": []},
        {"measure_id": "w1.cc.atom", "metric_id": "w1.country_count", "leg": "atom", "node_id": "w1.country",
         "measure": "count", "preds": []},
    ]
    aliases = [
        {"alias_id": "w1.al1", "alias_text": "亚洲人口总和", "metric_id": "w1.asia_population_sum"},
        {"alias_id": "w1.al2", "alias_text": "全球人口总和", "metric_id": "w1.world_population_sum"},
        {"alias_id": "w1.al3", "alias_text": "亚洲人口占比", "metric_id": "w1.population_share"},
        {"alias_id": "w1.al4", "alias_text": "区间历史记录条数", "metric_id": "w1.history_rows_range"},
        # 干扰
        {"alias_id": "w1.al5", "alias_text": "国民生产总值合计", "metric_id": "w1.gnp_sum"},
        {"alias_id": "w1.al6", "alias_text": "国家数量", "metric_id": "w1.country_count"},
    ]
    routing = [
        {"routing_id": "w1.rt1", "metric_id": "w1.asia_population_sum", "leg": "atom", "hop_seq": 0,
         "src_node": "w1.country_history", "dst_node": "w1.country", "join_on": [["code", "Code"]], "dst_caliber": "scoped"},
        {"routing_id": "w1.rt2", "metric_id": "w1.population_share", "leg": "num", "hop_seq": 0,
         "src_node": "w1.country_history", "dst_node": "w1.country", "join_on": [["code", "Code"]], "dst_caliber": "scoped"},
        {"routing_id": "w1.rt3", "metric_id": "w1.population_share", "leg": "den", "hop_seq": 0,
         "src_node": "w1.country_history", "dst_node": "w1.country_history", "join_on": [], "dst_caliber": "all"},
        # 干扰
        {"routing_id": "w1.rt4", "metric_id": "w1.gnp_sum", "leg": "atom", "hop_seq": 0,
         "src_node": "w1.country_history", "dst_node": "w1.country", "join_on": [["code", "Code"]], "dst_caliber": "scoped"},
    ]
    anchors = [
        {"anchor_id": "A-W1-HIST", "node_id": "w1.country_history", "anchor_type": "snapshot_effective_date",
         "effective_col": "effective_month", "vf_col": None, "vtc_col": None,
         "granularity": "month_token_yyyy_mm", "coverage_mode": "hull"},
    ]
    bindings = [
        {"binding_id": "B-W1-APS", "metric_id": "w1.asia_population_sum", "leg": "atom", "anchor_id": "A-W1-HIST",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
        {"binding_id": "B-W1-WPS", "metric_id": "w1.world_population_sum", "leg": "atom", "anchor_id": "A-W1-HIST",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
        {"binding_id": "B-W1-PS-N", "metric_id": "w1.population_share", "leg": "num", "anchor_id": "A-W1-HIST",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
        {"binding_id": "B-W1-PS-D", "metric_id": "w1.population_share", "leg": "den", "anchor_id": "A-W1-HIST",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
        {"binding_id": "B-W1-HRR", "metric_id": "w1.history_rows_range", "leg": "atom", "anchor_id": "A-W1-HIST",
         "rule_id": "same_valid_time_window", "window_gran": "range_request"},
        # 干扰
        {"binding_id": "B-W1-GS", "metric_id": "w1.gnp_sum", "leg": "atom", "anchor_id": "A-W1-HIST",
         "rule_id": "same_valid_time_window", "window_gran": "month_token"},
    ]
    edges = [
        {"edge_id": "w1.eg1", "domain": D, "axis": "entity", "from_level": "country", "to_level": "continent",
         "node_id": "w1.country", "group_cols": ["Continent"], "derived": [], "band_col": None, "band_bounds": []},
        {"edge_id": "w1.eg2", "domain": D, "axis": "entity", "from_level": "continent", "to_level": "all",
         "node_id": "w1.country", "group_cols": [], "derived": [], "band_col": None, "band_bounds": []},
    ]
    return {
        "gov_semantic_graph_version": version_rows(D),
        "gov_semantic_node": dual(nodes),
        "gov_metric": dual(metrics),
        # v2 常住口径重定基：度量列 population→population_resident（数据行携带 1.06 半上取整）
        "gov_measure_def": dual(measure, v2_patch={
            "w1.aps.atom": {"measure": "sum:population_resident"},
            "w1.wps.atom": {"measure": "sum:population_resident"},
            "w1.ps.num": {"measure": "sum:population_resident"},
            "w1.ps.den": {"measure": "sum:population_resident"},
        }, id_field="measure_id"),
        "gov_metric_alias": dual(aliases),
        "gov_caliber_routing": dual(routing),
        "gov_valid_time_anchor": dual(anchors),
        "gov_temporal_binding": dual(bindings),
        "gov_granularity_edge": dual(edges),
        "gov_disclosure_policy": [],
    }


SEED_BUILDERS = {
    "financial": seeds_financial,
    "card_games": seeds_card_games,
    "codebase_community": seeds_codebase,
    "formula_1": seeds_formula_1,
    "debit_card_specializing": seeds_debit,
    "european_football_2": seeds_ef2,
    "california_schools": seeds_ca_schools,
    "thrombosis_prediction": seeds_thrombosis,
    "world_1": seeds_world_1,
}
