"""Compatibility imports for the pre-F005 retrieval path."""

from tax_agent.business.references.tools import (
    TAX_AUTHORITY_SOURCES as TAX_SOURCES,
    extract_citations_from_messages,
    retrieve_tax_context,
)

__all__ = ["TAX_SOURCES", "extract_citations_from_messages", "retrieve_tax_context"]
