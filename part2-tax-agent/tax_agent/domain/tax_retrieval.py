import json
from typing import Any


TAX_SOURCES = [
    {
        "source_id": "vat-temporary-regulations",
        "title": "中华人民共和国增值税暂行条例",
        "keywords": ["增值税", "进项税额", "销项税额", "小规模纳税人"],
        "snippet": "在中华人民共和国境内销售货物、劳务、服务、无形资产、不动产以及进口货物的单位和个人，为增值税纳税人。",
    },
    {
        "source_id": "enterprise-income-tax-law",
        "title": "中华人民共和国企业所得税法",
        "keywords": ["企业所得税", "税率", "高新技术企业", "小型微利企业"],
        "snippet": "企业所得税基本税率为25%；符合条件的小型微利企业和高新技术企业可适用优惠政策。",
    },
    {
        "source_id": "tax-collection-administration-law",
        "title": "中华人民共和国税收征收管理法",
        "keywords": ["申报", "合规", "纳税", "滞纳金"],
        "snippet": "纳税人必须依照法律、行政法规规定或者税务机关确定的申报期限、申报内容如实办理纳税申报。",
    },
]


def retrieve_tax_context(query: str) -> str:
    """DeepAgents retrieval tool for local tax-law snippets."""
    matched = []
    for source in TAX_SOURCES:
        haystack = "".join([source["title"], source["snippet"], *source["keywords"]])
        if any(keyword in query or keyword in haystack for keyword in source["keywords"]):
            matched.append(_public_source(source))

    sources = matched[:3] or [_public_source(source) for source in TAX_SOURCES[:2]]
    return json.dumps({"query": query, "sources": sources}, ensure_ascii=False)


def extract_citations_from_messages(messages: list[Any]) -> list[dict]:
    citations = []
    seen = set()
    for message in messages:
        name = _message_value(message, "name") or _message_value(message, "tool_name")
        if name != "retrieve_tax_context":
            continue
        payload = _parse_tool_payload(_message_value(message, "content"))
        for source in payload.get("sources", []):
            source_id = source.get("source_id")
            title = source.get("title")
            if not source_id or not title or source_id in seen:
                continue
            seen.add(source_id)
            citations.append({"source_id": source_id, "title": title})
    return citations


def _public_source(source: dict) -> dict:
    return {
        "source_id": source["source_id"],
        "title": source["title"],
        "snippet": source["snippet"],
    }


def _parse_tool_payload(content: Any) -> dict:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _message_value(message: Any, key: str):
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)
