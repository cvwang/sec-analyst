"""PII scrubber module to sanitize sensitive information prior to logging or persistent storage."""

import re
from typing import Any, Dict, List, Union


class PIIScrubber:
    """Regex-based PII scrubber for masking SSNs, credit cards, accounts, tokens, and emails."""

    # Regex patterns for sensitive identifiers
    PATTERNS: Dict[str, re.Pattern] = {
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "api_key": re.compile(r"\b(?:AIza[0-9A-Za-z-_]{35}|sk-[a-zA-Z0-9]{32,}|bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*)\b", re.IGNORECASE),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "account_number": re.compile(r"\b(account|acct|iban)[\s:#=]+([0-9A-Z]{8,18})\b", re.IGNORECASE),
    }

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Sanitizes text strings by replacing detected PII patterns with redacted placeholders."""
        if not isinstance(text, str):
            return text

        scrubbed = text
        scrubbed = cls.PATTERNS["ssn"].sub("[REDACTED_SSN]", scrubbed)
        scrubbed = cls.PATTERNS["credit_card"].sub("[REDACTED_CARD]", scrubbed)
        scrubbed = cls.PATTERNS["api_key"].sub("[REDACTED_KEY]", scrubbed)
        scrubbed = cls.PATTERNS["email"].sub("[REDACTED_EMAIL]", scrubbed)
        scrubbed = cls.PATTERNS["account_number"].sub(r"\1 [REDACTED_ACCOUNT]", scrubbed)
        return scrubbed

    @classmethod
    def scrub_data(cls, data: Union[Dict, List, str, Any]) -> Any:
        """Recursively scrubs dictionary keys/values, lists, and strings for PII."""
        if isinstance(data, str):
            return cls.scrub_text(data)
        elif isinstance(data, dict):
            return {k: cls.scrub_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.scrub_data(item) for item in data]
        return data
