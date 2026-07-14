# -*- coding: utf-8 -*-
"""Generate human-readable FAQ review doc for ops/product."""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = json.loads((ROOT / "data/faq-export/sources.json").read_text(encoding="utf-8"))
rows = src["workbooks"]["Hot70_Script"]["data"]["FAQ知识库"]["rows"]

items = []
auto = 0
summary_path = ROOT / "data" / "faq-export" / "build-summary.json"
intent_total = 0
if summary_path.exists():
    intent_total = json.loads(summary_path.read_text(encoding="utf-8")).get("intent", 0)
for r in rows:
    q = str(r.get("用户问题", "")).strip()
    cat = str(r.get("分类", "")).strip()
    if not q or not cat:
        continue
    seq = r.get("序号", "")
    if seq != "" and str(seq) != "nan":
        fid = f"FAQ-{int(float(seq)):03d}"
    else:
        auto += 1
        fid = f"FAQ-A{auto:03d}"
    items.append(
        {
            "id": fid,
            "q": q,
            "cat": cat,
            "handoff": str(r.get("是否需要转人工", "")).strip(),
            "handoff_note": str(r.get("转人工条件/备注", "")).strip(),
            "status": str(r.get("状态", "")).strip(),
            "facts_zh": str(r.get("回复中文翻译", "")).replace("\n", " / ")[:200],
        }
    )

by_cat = defaultdict(list)
for it in items:
    by_cat[it["cat"]].append(it)

lines = [
    "# Hot70 语料 Review 清单",
    "",
    f"> 共 **{len(items)}** 条 FAQ 主问法（含 paraphrase 扩展共 **{intent_total or '—'}** 条意图语料）",
    "> 请运营/产品确认后，在 Excel 将「状态」改为 **已确认**，再重新 build 语料",
    "",
    "## Review 勾选",
    "",
    "- [ ] 分类正确",
    "- [ ] 转人工标记正确（是/否/视情况）",
    "- [ ] 回复口径可对外",
    "- [ ] 相似问法覆盖够用",
    "",
    "---",
    "",
]

for cat in sorted(by_cat.keys()):
    lines.append(f"## {cat}（{len(by_cat[cat])} 条）")
    lines.append("")
    lines.append("| ID | 用户问题 | 转人工 | 转人工条件 | 状态 | 回复要点 |")
    lines.append("|----|----------|--------|------------|------|----------|")
    for it in by_cat[cat]:
        q = it["q"].replace("|", "/")
        note = it["handoff_note"].replace("|", "/")[:50]
        facts = it["facts_zh"].replace("|", "/")[:80]
        lines.append(
            f"| {it['id']} | {q} | {it['handoff']} | {note} | {it['status']} | {facts} |"
        )
    lines.append("")

lines += ["---", "", "## 需关注：是 / 视情况 转人工", ""]
for it in items:
    if it["handoff"] in ("是", "视情况"):
        lines.append(f"- **{it['id']}** [{it['handoff']}] {it['q']}")

out = ROOT / "reports" / "corpus-review-for-ops.md"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print(f"OK {out} ({len(items)} items)")
