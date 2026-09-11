import pytest
from keyring.errors import KeyringError

from voice_assistant.domain.errors import ConfigurationError
from voice_assistant.storage.credentials import CredentialStore


class MemoryBackend:
    def __init__(self) -> None:
        self.value: str | None = None

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.value

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.value = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.value = None


def test_credential_store_round_trip() -> None:
    backend = MemoryBackend()
    store = CredentialStore(backend)

    store.set_gemini_api_key(" secret ")
    assert store.get_gemini_api_key() == "secret"
    store.set_gemini_api_key("")
    assert store.get_gemini_api_key() == ""


def test_credential_store_does_not_fall_back_to_plaintext() -> None:
    class FailingBackend(MemoryBackend):
        def set_password(self, service_name: str, username: str, password: str) -> None:
            raise KeyringError("unavailable")

    with pytest.raises(ConfigurationError, match="securely"):
        CredentialStore(FailingBackend()).set_gemini_api_key("secret")
