from tax_agent.business.analysis.tax_context import analyze_tax_question
from tax_agent.business.references.tools import find_tax_authorities


TAX_AGENT_TOOLS = [find_tax_authorities, analyze_tax_question]
