"""Compatibility import for the pre-migration Reference Layer path."""

from tax_agent.business.references.tools import (
    DEFAULT_REFERENCE_MANAGER,
    TAX_AUTHORITY_SOURCES,
    Citation,
    LocalTaxAuthorityProvider,
    ReferenceBundle,
    ReferenceItem,
    ReferenceManager,
    ReferenceProvider,
    find_tax_authorities,
)

__all__ = [
    "Citation",
    "DEFAULT_REFERENCE_MANAGER",
    "LocalTaxAuthorityProvider",
    "ReferenceBundle",
    "ReferenceItem",
    "ReferenceManager",
    "ReferenceProvider",
    "TAX_AUTHORITY_SOURCES",
    "find_tax_authorities",
]
