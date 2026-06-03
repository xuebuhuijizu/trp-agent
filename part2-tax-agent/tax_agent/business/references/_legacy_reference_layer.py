"""Legacy compatibility wrapper — Reference Layer.

All content has been moved to:
  - models.py        → Citation, ReferenceItem, ReferenceBundle
  - providers.py     → ReferenceProvider, LocalTaxAuthorityProvider
  - manager.py       → ReferenceManager, DEFAULT_REFERENCE_MANAGER
  - tools.py         → find_tax_authorities

This file re-exports for backward compatibility and will be removed
once all external consumers have been migrated.
"""

from tax_agent.business.references.manager import (  # noqa: F401
    DEFAULT_REFERENCE_MANAGER,
    ReferenceManager,
)
from tax_agent.business.references.models import (  # noqa: F401
    Citation,
    ReferenceBundle,
    ReferenceItem,
)
from tax_agent.business.references.providers import (  # noqa: F401
    LocalTaxAuthorityProvider,
    ReferenceProvider,
    TAX_AUTHORITY_SOURCES,
)
from tax_agent.business.references.tools import (  # noqa: F401
    extract_citations_from_messages,
    find_tax_authorities,
    retrieve_tax_context,
)
