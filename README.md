# Voice Assistant

A portable, personal tabletop RPG voice assistant for prepared narration and conversational NPCs.

## Project goals

- Run locally as a desktop application.
- Support cloud and local AI providers.
- Keep player speech separate from private GM text direction.
- Store campaigns in portable, human-readable directories.
- Maintain separate profiles, lore, secrets, memory, and voices for each NPC.
- Allow the user to choose where campaigns are stored.

## Repository structure

```text
src/voice_assistant/
├── domain/       campaign, NPC, secret, and session models
├── services/     conversation, narration, memory, and provider orchestration
├── storage/      configurable campaign locations and persistence
├── audio/        devices, recording, playback, and push-to-talk
└── ui/           desktop user interface

tests/            automated tests
examples/
└── campaigns/
    └── sample/   tracked example campaign
```

## Campaign storage

The sample campaign is tracked under `examples/campaigns/sample` for development and documentation. It is not intended to become the fixed runtime storage location.

The application supports a configurable campaign root. A normal installation defaults to the operating system's user-data location, while portable mode uses a `campaigns` directory beside the application. Selecting a campaign folder in the UI saves that location in the user configuration. Campaign files must not contain API credentials.

Campaign locations are resolved in this order:

1. An explicit campaign root from the command line or configuration
2. A `campaigns` directory beside the application in portable mode
3. The operating system's per-user application-data directory

## Development

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run bandit -r src -c pyproject.toml
```

Run the desktop shell with the tracked sample campaign:

```powershell
uv run voice-assistant --campaign-root examples/campaigns
```

Run with the normal per-user campaign location:

```powershell
uv run voice-assistant
```

Run in portable mode:

```powershell
uv run voice-assistant --portable
```

## Campaign format

Each campaign has a `campaign.yaml` manifest and one directory per NPC:

```text
campaign.yaml
characters/<npc-id>/
├── profile.md
├── secrets.md
├── memory.md
└── voice.yaml
lore/
scripts/
audio/
sessions/
```

The profile's first level-one Markdown heading is the NPC's display name. Secret entries use a level-two heading as their stable ID, followed by `hint`, optional `mode`, and the secret body. Supported modes are `hesitate` and `deflect`.

Voice files map one NPC to provider-specific voice identifiers while retaining a shared provider-neutral style. API credentials are stored separately in the operating system keyring and never belong in campaign data.

## Current implementation

The initial desktop shell can:

- Resolve normal, explicit, and portable campaign roots
- Discover and validate campaign manifests
- Load NPC profiles, voices, memory, secrets, lore, and scripts
- Select campaigns and NPCs
- Display the NPC profile
- Keep player text visibly separate from private GM direction

RoomKit voice-session integration is the next vertical slice. The current Start Voice Session button remains disabled until an NPC is selected and is not yet connected to a provider.
