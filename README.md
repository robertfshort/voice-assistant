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

The application will support a configurable campaign root. A normal installation can default to the operating system's user-data location, while portable mode can use a `campaigns` directory beside the application. Campaign files must not contain API credentials.
