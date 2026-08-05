"""Optional LLM judging for semantic quality and expected customer tags."""

from __future__ import annotations

import json
import os
import re

from . import harness  # noqa: F401 - imports env loader side effects

SEMANTIC_SYSTEM = (
    "你是客服机器人回复的质检评审员。给定用户问题和机器人回复，判断回复是否"
    "『语义合理且与问题相关』：语句通顺、直接回应了问题、无明显自相矛盾或答非所问。"
    "只评语义合理性，不核对事实数字准确性。只返回 JSON："
    "{\"ok\": true|false, \"reason\": \"简短中文理由\"}"
)
TAG_SYSTEM = (
    "你是客户意向标签质检员。只根据用户在本次会话中的消息，判断这个用户应该被打的客户标签。"
    "只能从以下枚举中选择一个：未识别、未预定低意向、未预定高意向、已预定未提机、已提机。"
    "标签定义：未识别=闲聊、假设问题、信息不足、招聘、辱骂等；"
    "未预定低意向=只问活动时间、抽奖、礼品、普通优惠、官方身份；"
    "未预定高意向=问价格、配置、购买方式、分期、如何预订；"
    "已预定未提机=明确说已预订、收到确认码、预订成功，但没有提机；"
    "已提机=明确说已提机、已购买、已激活，或业务数据确认成交。"
    "若同时满足多个标签，按 已提机 > 已预定未提机 > 未预定高意向 > 未预定低意向 > 未识别 的优先级选择。"
    "已预订/已预定视为同义，返回值统一用“已预定未提机”。只返回 JSON："
    "{\"tag\": \"未识别|未预定低意向|未预定高意向|已预定未提机|已提机\", \"reason\": \"简短中文理由\"}"
)
TAG_VALUES = ("未识别", "未预定低意向", "未预定高意向", "已预定未提机", "已提机")


def _semantic_prompt(item: dict) -> str:
    expected_handoff = bool(item.get("expected_handoff"))
    handling = (
        "本用例期望转人工。若回复明确说明正在转人工，或说明人工暂不可用但已保留人工诉求，应视为语义合理。"
        if expected_handoff
        else "本用例期望机器人直接回答，不应仅用转人工或无覆盖话术代替答案。"
    )
    keywords = item.get("answer_keywords") or []
    return (
        f"用户问题：{item['query']}\n\n"
        f"机器人回复：{item.get('reply') or '（无回复）'}\n\n"
        f"期望处置：{handling}\n"
        f"参考事实关键词：{', '.join(keywords) if keywords else '无'}\n\n"
        "请判断该回复是否语义合理且与问题相关，返回 JSON。"
    )


def _parse_semantic(text: object) -> dict:
    content = text if isinstance(text, str) else str(text)
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return {"ok": None, "reason": "无法解析: " + content[:80]}
    try:
        obj = json.loads(match.group(0))
        return {"ok": bool(obj.get("ok")), "reason": str(obj.get("reason", ""))[:120]}
    except ValueError:
        return {"ok": None, "reason": "JSON解析失败"}


def _tag_prompt(item: dict) -> str:
    messages = item.get("user_context") or [item.get("query", "")]
    lines = [f"{index + 1}. {message}" for index, message in enumerate(messages) if message]
    return "用户会话消息：\n" + "\n".join(lines) + "\n\n请判断期望客户标签，返回 JSON。"


def _parse_tag(text: object) -> dict:
    content = text if isinstance(text, str) else str(text)
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return {"tag": "未识别", "reason": "无法解析: " + content[:80]}
    try:
        obj = json.loads(match.group(0))
    except ValueError:
        return {"tag": "未识别", "reason": "JSON解析失败"}
    tag = str(obj.get("tag", "")).strip().replace("预订", "预定").replace("无法判断", "未识别")
    if tag not in TAG_VALUES:
        tag = "未识别"
    return {"tag": tag, "reason": str(obj.get("reason", ""))[:120]}


def _model():
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise SystemExit("LLM judge requires DEEPSEEK_API_KEY or LLM_API_KEY")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("LLM_API_BASE", "https://api.deepseek.com"),
        model=os.environ.get("DEEPSEEK_MODEL") or os.environ.get("LLM_MODEL", "deepseek-chat"),
        temperature=0,
        max_retries=2,
    )


def judge_semantic(items: list[dict]) -> dict[str, dict]:
    if not items:
        return {}
    from langchain_core.messages import HumanMessage, SystemMessage

    model = _model()
    batch = [[SystemMessage(SEMANTIC_SYSTEM), HumanMessage(_semantic_prompt(item))] for item in items]
    responses = model.batch(batch)
    return {
        item["case_id"]: _parse_semantic(getattr(response, "content", response))
        for item, response in zip(items, responses)
    }


def judge_expected_tags(items: list[dict]) -> dict[str, dict]:
    if not items:
        return {}
    from langchain_core.messages import HumanMessage, SystemMessage

    model = _model()
    batch = [[SystemMessage(TAG_SYSTEM), HumanMessage(_tag_prompt(item))] for item in items]
    responses = model.batch(batch)
    return {
        item["case_id"]: _parse_tag(getattr(response, "content", response))
        for item, response in zip(items, responses)
    }
