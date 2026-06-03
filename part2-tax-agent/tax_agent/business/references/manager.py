from tax_agent.business.references.models import Citation, ReferenceBundle, ReferenceItem
from tax_agent.business.references.providers import LocalTaxAuthorityProvider, ReferenceProvider


class ReferenceManager:
    def __init__(self, providers: list[ReferenceProvider]):
        self._providers = providers

    def find_tax_authorities(self, query: str) -> ReferenceBundle:
        items: list[ReferenceItem] = []
        provider_ids: list[str] = []
        seen: set[tuple[str, str]] = set()

        for provider in self._providers:
            provider_ids.append(provider.provider_id)
            for item in provider.find_tax_authorities(query):
                key = (item.provider_id, item.source_id)
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)

        items.sort(key=lambda item: item.confidence, reverse=True)
        citations = [item.citation() for item in items]
        coverage = "matched" if any(item.confidence >= 0.9 for item in items) else "fallback"
        return ReferenceBundle(
            query=query,
            provider_ids=provider_ids,
            items=items,
            citations=citations,
            coverage=coverage,
        )


DEFAULT_REFERENCE_MANAGER = ReferenceManager([LocalTaxAuthorityProvider()])
