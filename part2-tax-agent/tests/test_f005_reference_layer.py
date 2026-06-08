import json

from tax_agent.business.references.manager import ReferenceManager
from tax_agent.business.references.models import Citation
from tax_agent.business.references.providers import LocalTaxAuthorityProvider
from tax_agent.business.references.tools import extract_citations_from_messages, find_tax_authorities


def test_local_tax_authority_provider_returns_standard_reference_bundle():
    manager = ReferenceManager([LocalTaxAuthorityProvider()])

    bundle = manager.find_tax_authorities("增值税")

    assert bundle.provider_ids == ["local_tax_authorities"]
    assert bundle.items
    citation = bundle.citations[0]
    assert isinstance(citation, Citation)
    assert citation.source_type == "law"
    assert citation.provider_id == "local_tax_authorities"
    assert citation.source_id
    assert citation.title
    assert citation.snippet
    assert citation.confidence > 0
    assert citation.retrieved_at is None
    assert citation.metadata == {}


def test_find_tax_authorities_tool_returns_standard_payload():
    payload = json.loads(find_tax_authorities("企业所得税"))

    assert payload["query"] == "企业所得税"
    assert payload["provider_ids"] == ["local_tax_authorities"]
    assert payload["items"]
    assert payload["citations"]
    assert {
        "citation_id",
        "source_id",
        "source_type",
        "provider_id",
        "title",
        "locator",
        "snippet",
        "confidence",
        "retrieved_at",
        "metadata",
    }.issubset(payload["citations"][0])


def test_extract_citations_reads_standard_reference_bundle_messages():
    payload = {
        "citations": [
            {
                "citation_id": "local_tax_authorities:vat-regulation",
                "source_id": "vat-regulation",
                "source_type": "law",
                "provider_id": "local_tax_authorities",
                "title": "增值税暂行条例",
                "locator": None,
                "snippet": "增值税依据",
                "confidence": 0.9,
                "retrieved_at": None,
                "metadata": {},
            }
        ]
    }

    citations = extract_citations_from_messages(
        [{"name": "find_tax_authorities", "content": json.dumps(payload, ensure_ascii=False)}]
    )

    assert citations == payload["citations"]

