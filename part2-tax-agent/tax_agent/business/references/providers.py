from typing import Any, Protocol

from tax_agent.business.references.models import ReferenceItem


TAX_AUTHORITY_SOURCES = [
    {
        "source_id": "vat-temporary-regulations",
        "source_type": "law",
        "title": "中华人民共和国增值税暂行条例",
        "keywords": ["增值税", "进项税额", "销项税额", "小规模纳税人"],
        "snippet": "在中华人民共和国境内销售货物、劳务、服务、无形资产、不动产以及进口货物的单位和个人，为增值税纳税人。",
    },
    {
        "source_id": "enterprise-income-tax-law",
        "source_type": "law",
        "title": "中华人民共和国企业所得税法",
        "keywords": ["企业所得税", "税率", "高新技术企业", "小型微利企业"],
        "snippet": "企业所得税基本税率为25%；符合条件的小型微利企业和高新技术企业可适用优惠政策。",
    },
    {
        "source_id": "tax-collection-administration-law",
        "source_type": "law",
        "title": "中华人民共和国税收征收管理法",
        "keywords": ["申报", "合规", "纳税", "滞纳金"],
        "snippet": "纳税人必须依照法律、行政法规规定或者税务机关确定的申报期限、申报内容如实办理纳税申报。",
    },
]


class ReferenceProvider(Protocol):
    provider_id: str

    def find_tax_authorities(self, query: str) -> list[ReferenceItem]:
        ...


class LocalTaxAuthorityProvider:
    provider_id = "local_tax_authorities"

    def __init__(self, sources: list[dict[str, Any]] | None = None):
        self._sources = sources or TAX_AUTHORITY_SOURCES

    def find_tax_authorities(self, query: str) -> list[ReferenceItem]:
        matched = []
        for source in self._sources:
            haystack = "".join([source["title"], source["snippet"], *source["keywords"]])
            if any(keyword in query or keyword in haystack for keyword in source["keywords"]):
                matched.append(self._item(source, confidence=0.9))
        return matched[:3] or [self._item(source, confidence=0.5) for source in self._sources[:2]]

    def _item(self, source: dict[str, Any], confidence: float) -> ReferenceItem:
        return ReferenceItem(
            source_id=source["source_id"],
            source_type=source.get("source_type", "law"),
            provider_id=self.provider_id,
            title=source["title"],
            locator=None,
            snippet=source["snippet"],
            confidence=confidence,
        )
