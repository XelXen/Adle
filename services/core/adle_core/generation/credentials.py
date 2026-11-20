"""In-memory holder for provider secrets, and for which provider is in use.

The desktop shell keeps each model provider key encrypted with the OS credential
store and pushes the plaintext to this process after each launch, together with
the learner's choice of provider. Here they live only in memory: nothing in this
module is ever written to the database, a file, or a log.

There is one key per provider, kept under that provider's name. A key is only
ever handed out for the provider it was stored for, so one provider's key cannot
be sent to another's address (ADR-021).
"""

from __future__ import annotations

import logging
import threading

#: The provider a fresh installation uses until the learner chooses another.
DEFAULT_PROVIDER_ID = "aihubmix"


class CredentialVault:
    """Thread-safe storage for provider API keys and the provider in use."""

    def __init__(self, active_provider_id: str = DEFAULT_PROVIDER_ID) -> None:
        self._lock = threading.Lock()
        self._api_keys: dict[str, str] = {}
        self._active = active_provider_id

    @property
    def active_provider_id(self) -> str:
        with self._lock:
            return self._active

    def select(self, provider_id: str) -> None:
        """Make ``provider_id`` the provider requests go to. Its key, if any, is not touched."""
        with self._lock:
            self._active = provider_id

    def set_api_key(self, api_key: str, provider_id: str | None = None) -> None:
        """Keep a key for one provider: the one named, or the one in use."""
        with self._lock:
            self._api_keys[provider_id or self._active] = api_key

    def clear_api_key(self, provider_id: str | None = None) -> None:
        with self._lock:
            self._api_keys.pop(provider_id or self._active, None)

    def api_key(self, provider_id: str | None = None) -> str | None:
        """The key stored for one provider and for no other."""
        with self._lock:
            return self._api_keys.get(provider_id or self._active)

    def has_key_for(self, provider_id: str) -> bool:
        return self.api_key(provider_id) is not None

    @property
    def has_api_key(self) -> bool:
        """Whether the provider in use has a key."""
        return self.api_key() is not None

    def all_keys(self) -> tuple[str, ...]:
        """Every key held, for scrubbing them from log records. Never for sending."""
        with self._lock:
            return tuple(self._api_keys.values())

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CredentialVault(active={self._active!r}, "
                f"providers_with_a_key={sorted(self._api_keys)})"
            )


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
        return (*self._extra, *self._vault.all_keys())

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
