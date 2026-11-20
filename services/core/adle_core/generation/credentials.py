"""In-memory holder for provider secrets, and for which providers may be used.

The desktop shell keeps each model provider key encrypted with the OS credential
store and pushes the plaintext to this process after each launch, together with
the learner's choice of provider. Here they live only in memory: nothing in this
module is ever written to the database, a file, or a log.

There is one key per provider, kept under that provider's name. A key is only
ever handed out for the provider it was stored for, so one provider's key cannot
be sent to another's address (ADR-021).

The learner's choice is one provider, or "automatic": every provider they have
given a key for, each used for what it is good at (ADR-023).
"""

from __future__ import annotations

import logging
import threading

from adle_core.generation.routing import AUTOMATIC

#: The provider a key belongs to when nobody says which. The first one there is.
DEFAULT_PROVIDER_ID = "aihubmix"


class CredentialVault:
    """Thread-safe storage for provider API keys and the learner's choice of provider."""

    def __init__(
        self, default_provider_id: str = DEFAULT_PROVIDER_ID, selection: str = AUTOMATIC
    ) -> None:
        self._lock = threading.Lock()
        self._api_keys: dict[str, str] = {}
        self._default = default_provider_id
        self._selection = selection

    @property
    def default_provider_id(self) -> str:
        """Whose key a key is when it arrives without a name: the first provider."""
        return self._default

    @property
    def selection(self) -> str:
        """One provider's name, or ``AUTOMATIC``: what the learner chose."""
        with self._lock:
            return self._selection

    def select(self, selection: str) -> None:
        """Record the learner's choice. No key is touched."""
        with self._lock:
            self._selection = selection

    def set_api_key(self, api_key: str, provider_id: str | None = None) -> None:
        """Keep a key for one provider: the one named, or the first there is."""
        with self._lock:
            self._api_keys[provider_id or self._default] = api_key

    def clear_api_key(self, provider_id: str | None = None) -> None:
        with self._lock:
            self._api_keys.pop(provider_id or self._default, None)

    def api_key(self, provider_id: str | None = None) -> str | None:
        """The key stored for one provider and for no other."""
        with self._lock:
            return self._api_keys.get(provider_id or self._default)

    def has_key_for(self, provider_id: str) -> bool:
        return self.api_key(provider_id) is not None

    @property
    def has_api_key(self) -> bool:
        """Whether anything could be asked of a provider at all, by the learner's choice."""
        with self._lock:
            if self._selection == AUTOMATIC:
                return bool(self._api_keys)
            return self._selection in self._api_keys

    def all_keys(self) -> tuple[str, ...]:
        """Every key held, for scrubbing them from log records. Never for sending."""
        with self._lock:
            return tuple(self._api_keys.values())

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CredentialVault(selection={self._selection!r}, "
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
