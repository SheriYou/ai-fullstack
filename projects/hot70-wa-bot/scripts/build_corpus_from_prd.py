# -*- coding: utf-8 -*-
"""Build corpus CSV from prd/ xlsx (TestFactory)."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FAQ_JSON = ROOT / "data" / "faq-export" / "sources.json"

CAT_INTENT = {
    "HOT70 商品信息": "产品信息",
    "活动规则": "活动规则",
    "活动权益": "活动权益",
    "提机规则": "提机相关",
    "门店信息": "门店相关",
    "官方身份说明": "官方身份",
    "人工兜底规则": "人工兜底",
}

CAT_CODE = {
    "HOT70 商品信息": "PROD",
    "活动规则": "ACT",
    "活动权益": "BEN",
    "提机规则": "PICK",
    "门店信息": "STORE",
    "官方身份说明": "OFF",
    "人工兜底规则": "HANDOFF",
}

FAQ_Q_COL = "用户问题（用户实际使用语种）"


def keywords_from_translation(text: str, max_kw: int = 8) -> str:
    kws = []
    for line in str(text).split("\n"):
        line = line.strip()
        if not line or line.startswith("如需"):
            continue
        m = re.match(r"[•\d️⃣]+?\s*(.+?)[：:]", line)
        if m:
            kws.append(m.group(1).strip()[:24])
        elif len(line) < 48 and "？" not in line and "?" not in line:
            kws.append(line[:24])
    if not kws and text:
        kws = [str(text).split("\n")[0][:30]]
    return "|".join(dict.fromkeys(kws))[:200] if kws else ""


def parse_handoff(val: str) -> str:
    v = str(val).strip()
    if v == "是":
        return "true"
    if v == "否":
        return "false"
    return "conditional"


def split_similar(s: str) -> list[str]:
    if not s or str(s) in ("nan", ""):
        return []
    return [p.strip() for p in re.split(r"\s*/\s*", str(s)) if p.strip()]


def load_sources():
    raw = json.loads(FAQ_JSON.read_text(encoding="utf-8"))
    return raw.get("workbooks", raw)


def iter_sheets(src):
    for wb_name, wb in src.items():
        for sheet_name, sheet in wb.get("data", {}).items():
            yield wb_name, sheet_name, sheet


def extract_faq_rows(src) -> list[dict]:
    rows_out = []
    auto = 0
    for wb_name, sheet_name, sheet in iter_sheets(src):
        cols = sheet.get("columns", [])
        if FAQ_Q_COL not in cols or "分类" not in cols:
            continue
        if "话术编号" in cols:
            continue
        for row in sheet["rows"]:
            q = str(row.get(FAQ_Q_COL, "")).strip()
            cat = str(row.get("分类", "")).strip()
            if not q or not cat:
                continue
            seq = row.get("序号", "")
            if seq != "" and str(seq) != "nan":
                fid = f"FAQ-{int(float(seq)):03d}"
            else:
                auto += 1
                fid = f"FAQ-A{auto:03d}"
            rows_out.append({**row, "_fid": fid, "_wb": wb_name, "_sheet": sheet_name})
    return rows_out


def extract_script_rows(src) -> list[dict]:
    rows_out = []
    for wb_name, sheet_name, sheet in iter_sheets(src):
        cols = sheet.get("columns", [])
        if "话术编号" not in cols:
            continue
        for row in sheet["rows"]:
            sid = str(row.get("话术编号", "")).strip()
            if not sid:
                continue
            rows_out.append({**row, "_wb": wb_name, "_sheet": sheet_name})
    return rows_out


def build():
    src = load_sources()
    faq_rows = extract_faq_rows(src)
    script_rows = extract_script_rows(src)

    intent_rows, kb_rows, handoff_rows, script_rows_out = [], [], [], []

    for row in faq_rows:
        fid = row["_fid"]
        cat = row["分类"]
        q = str(row[FAQ_Q_COL]).strip()
        intent = CAT_INTENT.get(cat, "无法覆盖")
        code = CAT_CODE.get(cat, "OTHER")
        trans = str(row.get("回复中文翻译", "") or row.get("业务反馈", ""))
        facts = keywords_from_translation(trans)
        ho = parse_handoff(row.get("是否需要转人工", ""))
        action = "handoff" if ho == "true" else "reply"
        pri = "P0"

        kb_rows.append(
            dict(
                id=f"KB-{fid}",
                input=q,
                category=code,
                expected_facts=facts,
                should_handoff=ho,
                priority=pri,
                rule_id=fid,
                source="faq",
            )
        )
        intent_rows.append(
            dict(
                id=f"INT-{fid}",
                input=q,
                expected_intent=intent,
                expected_action=action,
                expected_facts=facts if action == "reply" else "",
                should_handoff=ho,
                priority=pri,
                rule_id=fid,
                source="faq",
            )
        )
        for i, sim in enumerate(split_similar(row.get("相似问法", "")), 1):
            sim_q = sim if "?" in sim or "？" in sim else sim
            intent_rows.append(
                dict(
                    id=f"INT-{fid}-P{i}",
                    input=sim_q,
                    expected_intent=intent,
                    expected_action=action,
                    expected_facts=facts if action == "reply" else "",
                    should_handoff=ho,
                    priority=pri,
                    rule_id=fid,
                    source="faq_paraphrase",
                )
            )
            kb_rows.append(
                dict(
                    id=f"KB-{fid}-P{i}",
                    input=sim_q,
                    category=code,
                    expected_facts=facts,
                    should_handoff=ho,
                    priority=pri,
                    rule_id=fid,
                    source="faq_paraphrase",
                )
            )
        note = str(row.get("转人工条件/备注", "")).strip()
        if ho in ("true", "conditional"):
            handoff_rows.append(
                dict(
                    id=f"HO-{fid}",
                    input=q,
                    expected_action="handoff" if ho == "true" else "conditional",
                    reason=note or cat,
                    should_handoff=ho,
                    priority=pri,
                    rule_id=fid,
                    source="faq",
                )
            )

    for row in script_rows:
        sid = row["话术编号"]
        ho = parse_handoff(row.get("是否需转人工", ""))
        action = "handoff" if ho == "true" else ("conditional" if ho == "conditional" else "reply")
        q = str(row.get("用户示例问题", "")).strip()
        pref = str(row.get("预填消息示例", "")).strip()
        script_rows_out.append(
            dict(
                id=sid,
                scene=row.get("场景分类", ""),
                trigger=str(row.get("触发条件", ""))[:120],
                input=q,
                prefill=pref,
                expected_script_keywords=str(row.get("中文话术", ""))[:80],
                expected_action=action,
                should_handoff=ho,
                priority=row.get("优先级", "P0"),
                source="script",
            )
        )
        if q:
            intent_rows.append(
                dict(
                    id=f"INT-{sid}",
                    input=q,
                    expected_intent=row.get("场景分类", ""),
                    expected_action=action,
                    expected_facts="",
                    should_handoff=ho,
                    priority=row.get("优先级", "P0"),
                    rule_id=sid,
                    source="script",
                )
            )
        if pref and pref != q:
            intent_rows.append(
                dict(
                    id=f"INT-{sid}-PF",
                    input=pref,
                    expected_intent="首轮承接",
                    expected_action="reply",
                    expected_facts="预订|提机|福利",
                    should_handoff="false",
                    priority="P0",
                    rule_id=sid,
                    source="script_prefill",
                )
            )
        if ho == "true" or sid == "HANDOFF_001":
            handoff_rows.append(
                dict(
                    id=f"HO-{sid}",
                    input=q or "I want to talk to human",
                    expected_action="handoff",
                    reason=str(row.get("转人工原因", "") or row.get("触发条件", ""))[:80],
                    should_handoff="true",
                    priority="P0",
                    rule_id=sid,
                    source="script",
                )
            )

    adv_rows = [
        dict(id="ADV-Q02-001", input="（转人工后）在吗", expected_action="none", reason="机器人不自动回复", priority="P0", rule_id="R-HO-005", source="prd"),
        dict(id="ADV-HO-002", input="还有库存吗", expected_action="handoff", reason="动态信息", priority="P0", rule_id="R-KB-002", source="faq_rule"),
        dict(id="ADV-HO-003", input="我的订单到哪了", expected_action="handoff", reason="查订单", priority="P0", rule_id="R-KB-002", source="faq_rule"),
        dict(id="ADV-INT-001", input="今天天气怎么样", expected_action="handoff", reason="无法覆盖", priority="P0", rule_id="R-INT-002", source="prd"),
    ]

    def write_csv(path, fieldnames, rows):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    write_csv(
        DATA / "corpus-intent.csv",
        ["id", "input", "expected_intent", "expected_action", "expected_facts", "should_handoff", "priority", "rule_id", "source"],
        intent_rows,
    )
    write_csv(
        DATA / "corpus-kb.csv",
        ["id", "input", "category", "expected_facts", "should_handoff", "priority", "rule_id", "source"],
        kb_rows,
    )
    write_csv(
        DATA / "corpus-handoff.csv",
        ["id", "input", "expected_action", "reason", "should_handoff", "priority", "rule_id", "source"],
        handoff_rows,
    )
    write_csv(
        DATA / "corpus-script.csv",
        ["id", "scene", "trigger", "input", "prefill", "expected_script_keywords", "expected_action", "should_handoff", "priority", "source"],
        script_rows_out,
    )
    write_csv(
        DATA / "corpus-adversarial.csv",
        ["id", "input", "expected_action", "reason", "priority", "rule_id", "source"],
        adv_rows,
    )

    summary = {
        "faq_entries": len(faq_rows),
        "script_entries": len(script_rows),
        "intent": len(intent_rows),
        "kb": len(kb_rows),
        "handoff": len(handoff_rows),
        "script": len(script_rows_out),
    }
    (DATA / "faq-export" / "build-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    build()
