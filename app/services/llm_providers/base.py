from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standard response wrapper for all LLM providers."""
    content: str
    model: str
    usage: Optional[dict] = None


class BaseLLMClient(ABC):
    """Abstract base class for all LLM provider clients."""

    @abstractmethod
    async def generate_sql(self, schema: str, domain_context: str, user_query: str, dialect: str) -> LLMResponse:
        """Generate SQL from natural language. Must return LLMResponse."""
        pass

    def _build_prompt(self, schema: str, domain_context: str, dialect: str) -> str:
        """Build the system prompt for SQL generation."""
        base = f"You are an expert {dialect} assistant.\n\nDatabase Schema:\n{schema}\n\n"
        if domain_context and domain_context.strip():
            base += f"Domain Context:\n{domain_context}\n\n"
        base += (
            "Rules:\n"
            "- Use fully qualified names like 'schema.table'\n"
            "- Consider end_date columns for calculations unless the user query mentions inactive status\n"
            "- Only return the SQL query, no comments or extra text."
        )
        return base
