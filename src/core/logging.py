"""Structured JSON logging with per-request correlation IDs and secret redaction."""

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Patterns matching sensitive credentials, tokens, API keys, and passphrases
SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(Basic\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"((?:^|[?&\s])(?:key|api_key|token|access_token|refresh_token|client_secret|code)=)[^&\s'\"]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(AIza[0-9A-Za-z\-_]{16,})"), "[GEMINI_KEY_REDACTED]"),
    (re.compile(r'("(?:api_key|client_secret|access_token|refresh_token|passphrase|password|encrypted_[a-z_]+)"\s*:\s*)"[^"]*"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r"((?:x-goog-api-key|authorization)\s*[:=]\s*)[^\s,;'\"]+", re.IGNORECASE), r"\1[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    """Redact credentials, bearer tokens, and API keys from arbitrary log/error strings."""
    if not text:
        return ""
    out = text
    for pattern, repl in SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


class SecretRedactingFilter(logging.Filter):
    """Logging filter injecting request_id and scrubbing secrets from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_secrets(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secrets(a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON with timestamp, level, logger, and request_id."""

    def format(self, record: logging.LogRecord) -> str:
        message = redact_secrets(record.getMessage())
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", request_id_ctx.get()),
            "message": message,
        }
        if record.exc_info:
            payload["exception"] = redact_secrets(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with structured JSON formatting and secret redaction."""
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicating handlers if called repeatedly
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())
    handler.addFilter(SecretRedactingFilter())
    root.addHandler(handler)

