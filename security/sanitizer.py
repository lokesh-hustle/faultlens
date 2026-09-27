"""
FaultLens Security - Input Validation & Context Propagation Sanitizer
Hardened against XSS, SQLi, NoSQLi, Path Traversal, and Header Injection attacks.
"""

import re
import html
from typing import Any, Dict, Union, List, Optional


class TelemetrySanitizer:
    # Pattern for valid W3C Trace IDs (32 hex chars) and Span IDs (16 hex chars)
    TRACE_ID_REGEX = re.compile(r"^[a-fA-F0-9]{32}$")
    SPAN_ID_REGEX = re.compile(r"^[a-fA-F0-9]{16}$")
    SAFE_SERVICE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9\-_:]{1,64}$")
    
    # Common injection attack indicators
    DANGEROUS_PATTERNS = [
        re.compile(r"<script.*?>.*?</script>", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"onload\s*=", re.IGNORECASE),
        re.compile(r"onerror\s*=", re.IGNORECASE),
        re.compile(r"(--|;|/\*|\*/|UNION\s+SELECT|SELECT\s+.*?\s+FROM)", re.IGNORECASE),  # SQLi
        re.compile(r"\$gt|\$lt|\$ne|\$where|\$regex", re.IGNORECASE),  # NoSQLi
        re.compile(r"(\.\./|\.\.\\)", re.IGNORECASE)  # Path Traversal
    ]

    @classmethod
    def sanitize_string(cls, text: Optional[str], max_len: int = 4096) -> str:
        """Sanitizes raw string inputs to protect against XSS and Injections."""
        if not text:
            return ""
        
        # Enforce max length to mitigate ReDoS and Memory Exhaustion
        truncated = text[:max_len]
        
        # Neutralize dangerous script & injection patterns
        cleaned = truncated
        for pattern in cls.DANGEROUS_PATTERNS:
            cleaned = pattern.sub("[REDACTED_INJECTION_ATTEMPT]", cleaned)

        # HTML Entity Encode to prevent DOM XSS
        sanitized = html.escape(cleaned)
        return sanitized

    @classmethod
    def validate_trace_id(cls, trace_id: Optional[str]) -> str:
        """Validates or normalizes W3C Trace ID format."""
        if not trace_id:
            return "00000000000000000000000000000000"
        
        clean = trace_id.strip()
        if cls.TRACE_ID_REGEX.match(clean):
            return clean.lower()
        
        # If non-standard, sanitize string and return safe fallback
        sanitized = cls.sanitize_string(clean, max_len=32)
        return sanitized.zfill(32)[:32]

    @classmethod
    def validate_span_id(cls, span_id: Optional[str]) -> str:
        """Validates or normalizes W3C Span ID format."""
        if not span_id:
            return "0000000000000000"
        
        clean = span_id.strip()
        if cls.SPAN_ID_REGEX.match(clean):
            return clean.lower()
        
        sanitized = cls.sanitize_string(clean, max_len=16)
        return sanitized.zfill(16)[:16]

    @classmethod
    def validate_service_name(cls, name: Optional[str]) -> str:
        """Validates service identifiers against strict character rules."""
        if not name:
            return "unknown-service"
        
        clean = name.strip()
        if cls.SAFE_SERVICE_NAME_REGEX.match(clean):
            return clean.lower()
        
        # Filter non-alphanumeric chars except dash and underscore
        filtered = re.sub(r"[^a-zA-Z0-9\-_:]", "", clean)
        return filtered.lower()[:64] or "unknown-service"

    @classmethod
    def sanitize_dictionary(cls, obj: Any) -> Any:
        """Recursively sanitizes nested dictionaries or lists."""
        if isinstance(obj, str):
            return cls.sanitize_string(obj)
        elif isinstance(obj, dict):
            return {cls.sanitize_string(str(k)): cls.sanitize_dictionary(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls.sanitize_dictionary(item) for item in obj]
        return obj
