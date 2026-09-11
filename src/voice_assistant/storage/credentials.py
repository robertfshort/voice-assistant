from __future__ import annotations

from typing import Protocol

import keyring
from keyring.errors import KeyringError

from voice_assistant.domain.errors import ConfigurationError

_SERVICE = "RPG Voice Assistant"
_GEMINI_ACCOUNT = "providers:gemini:api-key"


class CredentialBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class CredentialStore:
    def __init__(self, backend: CredentialBackend = keyring) -> None:
        self._backend = backend

    def get_gemini_api_key(self) -> str:
        try:
            return self._backend.get_password(_SERVICE, _GEMINI_ACCOUNT) or ""
        except KeyringError as exc:
            raise ConfigurationError(f"Unable to read the Gemini API key: {exc}") from exc

    def set_gemini_api_key(self, api_key: str) -> None:
        value = api_key.strip()
        try:
            if value:
                self._backend.set_password(_SERVICE, _GEMINI_ACCOUNT, value)
            else:
                self._backend.delete_password(_SERVICE, _GEMINI_ACCOUNT)
        except KeyringError as exc:
            raise ConfigurationError(
                f"Unable to store the Gemini API key securely: {exc}"
            ) from exc
