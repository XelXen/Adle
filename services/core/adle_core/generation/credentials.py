"""In-memory holder for provider secrets.

The desktop shell keeps the model provider key encrypted with the OS credential
store and pushes the plaintext to this process after each launch. Here it lives
only in memory: it is never written to the database, a file, or a log.
"""

from __future__ import annotations

import logging
import threading


class CredentialVault:
    """Thread-safe storage for the current provider API key."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._api_key: str | None = None

    def set_api_key(self, api_key: str) -> None:
        with self._lock:
            self._api_key = api_key

    def clear_api_key(self) -> None:
        with self._lock:
            self._api_key = None

    def api_key(self) -> str | None:
        with self._lock:
            return self._api_key

    @property
    def has_api_key(self) -> bool:
        return self.api_key() is not None

    def __repr__(self) -> str:
        return f"CredentialVault(has_api_key={self.has_api_key})"


class SecretRedactionFilter(logging.Filter):
    """Defence in depth: scrub known secret values from every log record.

    Code should never log a secret in the first place. If one slips into a
    message (for example inside an exception raised by an HTTP library), this
    filter replaces it before the record reaches a handler.
    """

    PLACEHOLDER = "[redacted]"

    def __init__(self, vault: CredentialVault, extra_secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._vault = vault
        self._extra = tuple(secret for secret in extra_secrets if secret)

    def _secrets(self) -> tuple[str, ...]:
        api_key = self._vault.api_key()
        return (*self._extra, api_key) if api_key else self._extra

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = self._secrets()
        if not secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in secrets:
            redacted = redacted.replace(secret, self.PLACEHOLDER)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True
