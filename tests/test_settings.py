from pathlib import Path

from voice_assistant.storage.settings import (
    AppSettings,
    ProviderSettings,
    SpeechSettings,
    StorageSettings,
    load_settings,
    resolve_campaign_root,
    save_settings,
)


def test_explicit_campaign_root_takes_precedence(tmp_path: Path) -> None:
    selected = tmp_path / "selected"
    settings = StorageSettings(campaign_root=selected, portable_mode=True)

    assert (
        resolve_campaign_root(
            settings,
            app_directory=tmp_path / "app",
            data_directory=tmp_path / "data",
        )
        == selected.resolve()
    )


def test_portable_campaign_root_is_beside_application(tmp_path: Path) -> None:
    app_directory = tmp_path / "portable"

    result = resolve_campaign_root(
        StorageSettings(portable_mode=True),
        app_directory=app_directory,
        data_directory=tmp_path / "data",
    )

    assert result == app_directory.resolve() / "campaigns"


def test_default_campaign_root_uses_user_data_directory(tmp_path: Path) -> None:
    result = resolve_campaign_root(
        StorageSettings(),
        app_directory=tmp_path / "app",
        data_directory=tmp_path / "data",
    )

    assert result == tmp_path.resolve() / "data" / "campaigns"


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    settings = AppSettings(
        storage=StorageSettings(campaign_root=tmp_path / "campaigns"),
        providers=ProviderSettings(speech="piper"),
        speech=SpeechSettings(
            voice_root=tmp_path / "voices",
            fallback_order=("piper", "gemini"),
        ),
    )

    saved_path = save_settings(settings, path)

    assert saved_path == path
    assert load_settings(path) == settings
    assert not path.with_suffix(".yaml.tmp").exists()
