# Product Roadmap and Future Design Notes

## Current implementation status

The early alpha build currently supports:

- Conversational NPC vertical slice (Gemini Live, RoomKit rooms, per-NPC prompt, transcripts)
- Multi-NPC switching and isolation (two sample NPCs and automated tests)
- Campaign editing:
  - View and edit lore
  - Create new lore entries
  - Append NPC knowledge
  - Create and edit NPCs
  - Duplicate NPC as a starting template
  - Archive NPC (mark as archived in the create/edit dialog, shown in gray in the NPC list)
  - Change tracking and backups for lore, NPC, and profile edits
  - Propose public NPC facts into lore with GM review, and offer to do so automatically after creating or editing an NPC
- Campaign management: Choose a campaigns folder, jump up one level, and create a new campaign with a default narrator NPC from the main window
- 30 Gemini TTS voices with Male/Female filter
- Voice preview in the create/edit NPC dialog
- NPC home region and current location fields in the create/edit NPC dialog
- Cached Gemini clients for voice previews and NPC generation
- Debounced AI generation and capped prompt lore records
- Live session reconfigure for private GM instructions instead of full reconnect
- UI theming: light, dark, dungeon, and tavern
- Structured lore records with visibility, scopes, provenance, and status
- NPC prompt filtering for public/restricted lore; secret and GM-only lore is hidden
- NPC affiliations stored in profiles and used to filter restricted lore by scope
- Explainable knowledge resolution: Inspect context dialog shows why each lore record was included for an NPC
- Session summaries and proposed memory: Generate session notes from an NPC transcript, review the AI summary, and append proposed memory to the NPC with GM approval
- Proposed lore from sessions: Review and edit AI-proposed public facts from a session transcript and create new lore files with GM approval
- PC/speaker profiles: A `pcs/` directory for player and named speaker profiles, an editable speaker list, and active speaker context fed into the NPC prompt
- GM-controlled character TTS: A "Speak as NPC" button that lets the GM type text and speak it through the active NPC's configured Gemini voice without running the conversational AI
- NPC portrait or token image: Browse for a portrait image in the create/edit NPC dialog; the image is copied to `characters/<id>/portrait.*` and displayed in the dialog as a preview
- TTS mood tags: `[[whisper]]`, `[[nervously]]`, `[[/mood]]`, and similar tags in the typed line switch the TTS delivery for the following segment
- Play session recording: A "Record session" button that writes all player, GM, and NPC turns into a shared `sessions/table-<id>.jsonl` file, with a Session tab to review the transcript
- Conversation curation: Right-click a transcript line or selection to "Promote to lore" or "Promote to memory" for the active NPC
- Lore metadata buttons: Insert YAML front matter (public, restricted, secret, gm-only, proposed) and `<!-- scope: ... -->` grouping comments from the Lore tab
- In-document lore groupings: `<!-- scope: ... -->` HTML comments split a lore entry into sections, and only sections matching an NPC's affiliations are included in that NPC's prompt
- Spell check: A "Spell check" button for the Lore, NPC knowledge, and speaker editors, using a portable `campaign/dictionary.txt` and showing suggestions for unknown words

The next roadmap step is the next feature from the **## Future feature notes** section, likely one of play session audio transcription and speaker attribution, expanding spell check to NPC profiles and memories, or the Piper/local TTS provider plan.

## Product direction

The initial product is a portable RPG voice assistant, but its campaign, lore, NPC, organization, and session requirements may naturally develop into a larger campaign-management system.

Development should preserve that possibility without requiring the first release to implement an entire virtual tabletop or campaign database. Conversation and narration remain the initial vertical slices; campaign management should grow around a stable domain model.

## Future feature notes

### Lore page metadata and grouping controls

- Add buttons in the lore editor to insert YAML front matter (visibility, scopes, provenance, status) without requiring manual typing.
- Support in-document groupings so a single lore entry can contain sections with different visibility/scope rules.
- Use a lightweight Markdown convention, such as an HTML comment or a special heading marker, to flag a section as belonging to a group (for example, `<!-- scope: order-of-the-rose -->`).
- Allow groupings to be evaluated per NPC based on that NPC's affiliations, memberships, and relationships.
- Keep the raw Markdown human-readable and portable; an entry without annotations should remain public by default.

### Speaker and PC profiles

- Add a `pcs/` or `speakers/` directory in the campaign for player character and named speaker profiles.
- Store per-speaker fields such as name, description, public background, affiliations, relationships, and preferred voice.
- Let the GM mark active player(s) before or during a session.
- Include only the appropriate speaker context in the NPC prompt so the AI knows who it is addressing while honoring the same visibility boundaries as lore.

### Play session transcription

- Record full play sessions with speaker attribution for both players and NPCs.
- Transcribe multiple microphones or a single table microphone and let the GM assign or correct speaker labels.
- Store the timestamped transcript alongside the NPC conversation so later session summaries can distinguish player speech, GM instruction, and NPC replies.
- Keep session transcription opt-in and expose visible recording controls with retention and export options.

### GM-controlled character TTS

- Let the GM type text and have it spoken in a selected character's configured voice without running the NPC AI.
- Support any campaign NPC or GM-defined voice so the GM can narrate, do side characters, or clarify in the same voice the players already heard.
- Support in-text tags such as `[[whisper]]` or `[[nervously]]` to switch delivery style or mood for a section of the spoken line.
- Keep the TTS control separate from the conversational AI response flow to avoid accidental model-generated replies.

### Provider-neutral and local TTS (Piper)

- Add a `speech` provider setting with options such as `gemini-live`, `piper`, and `system` (`pyttsx3` / `espeak`).
- Let each NPC store provider-specific voice configs in `voice.yaml` so the same NPC can have a `gemini` voice, a `piper` model, and a `system` voice.
- Add a global default TTS provider in `AppSettings.providers` and let the NPC dialog choose the preferred provider per NPC.
- Piper settings per voice:
  - `model` path to the `.onnx` model.
  - `config` path to the `.onnx.json` config.
  - `speaker_id` for multi-speaker models.
  - `length_scale`, `noise_scale`, `noise_w`, and `sentence_silence` synthesis parameters.
  - `sample_rate` and `channels` so the audio pipeline can resample to the output device.
- Audio output settings:
  - Output device selection.
  - Resampling from the provider sample rate to the selected device rate.
  - Buffer size and latency for `sounddevice`.
- Mood tag mapping per provider:
  - Gemini: keep the prompt-based `mood` wording.
  - Piper: map `[[whisper]]` / `[[nervously]]` / `[[shout]]` to `length_scale` and `noise_scale` overrides, or skip mood for unsupported providers.
  - System TTS: ignore mood tags and speak the text.
- Provider fallback chain: if the selected provider fails (quota, missing model, no API key), try the next configured provider and record the fallback in the log.
- Centralised voice/voices asset directory:
  - `voices/` for `.onnx` / `.json` Piper models and a `voices.yaml` registry that maps voice names to provider-specific files.
  - Let campaigns reference a voice by name instead of by absolute path, keeping campaigns portable.
- TTS preview should be provider-aware: play a test sample from the selected NPC and provider.
- Conversation TTS should also use the configured provider, with the same voice fallback and resampling.

### Spell check

- Provide spell checking for lore, NPC profiles, memories, and player text in the application.
- Respect campaign-specific names, places, and terms so the GM can add words to a campaign dictionary and avoid false positives.
- Keep the dictionary portable and editable alongside the campaign files.

### Conversation curation

- Add a right-click context menu on a line of dialog or a selected range in the conversation transcript to promote it to lore.
- Let the GM choose to append the snippet to an existing lore entry or create a new one.
- Pre-fill the lore with a default title, the speaker, the NPC, and a timestamp provenance.
- Keep the promotion flow in a review dialog so AI-generated or improvised dialogue cannot become canon without GM approval.

## Near-term requirements

### Lore and NPC knowledge management

The GM must be able to view and maintain campaign knowledge from the application.

Required capabilities:

- Browse campaign lore from the main interface
- Create new lore entries
- Edit existing lore
- Append notes without replacing existing material
- Assign lore to one or more scopes
- Add private knowledge directly to an NPC
- Distinguish established facts from session notes and generated suggestions
- Record when and why an entry changed
- Reload updated lore into a conversation safely

The application should not require the GM to edit Markdown manually, although campaign files should remain human-readable and portable.

### Multiple NPCs in the sample campaign

The tracked sample campaign should contain at least two NPCs with deliberately different:

- Personalities
- Voices
- Organizations or affiliations
- Knowledge scopes
- Private memories
- Secrets

The sample should exercise switching NPCs and verify that one NPC's private knowledge and conversation history do not leak into another's context.

### NPC creation and editing

The UI needs an NPC-management workflow.

Initial fields:

- Stable NPC ID
- Display name
- Role and description
- Personality
- Speaking style
- Goals and motivations
- Relationships
- Affiliations
- Home region and current location
- Public knowledge
- Private knowledge
- Secrets
- Provider-specific voice mappings
- Voice selectors populated from each configured provider's available voices
- Mood, emotional tone, and speaking-style selectors with optional custom values
- A voice preview using the selected voice and mood before saving
- Portable provider-neutral voice and mood intent with provider-specific overrides
- Portrait or token image

Expected actions:

- Create NPC
- Edit NPC
- Duplicate NPC as a starting template
- Archive NPC
- Assign lore scopes and affiliations
- Preview the configured voice
- Add the NPC's relevant public facts to campaign lore when the NPC is saved

Public lore created from an NPC should capture facts other characters may reasonably know, such as Elara being the tavernkeeper or Duggar being the mayor. The GM should be able to review the proposed lore, choose its scopes, and resolve duplicates or conflicts before it becomes established canon. Private knowledge, secrets, and GM-only details must never be included automatically.

Deletion should be handled carefully once an NPC has transcripts, memories, or relationships. Archiving is safer than immediate destructive deletion.

### Multi-NPC conversations

A scene may include multiple voiced NPCs in the same conversation. This must not be implemented as one blended character prompt.

Required capabilities:

- Add and remove participating NPCs without changing the campaign roster
- Preserve each NPC's distinct voice, mood, personality, memory, secrets, and knowledge boundaries
- Route each response through the correct NPC identity and configured voice
- Let the GM address one NPC, selected NPCs, or the whole scene
- Support NPC-to-NPC dialogue without allowing an uncontrolled response loop
- Record the active speaker on every transcript event
- Maintain a shared scene transcript while updating only appropriate NPC memories
- Show clearly which NPC is listening, speaking, muted, or privately directed
- Prevent one NPC's restricted lore or private GM direction from leaking to another
- Allow the GM to control turn order or approve suggested NPC interjections

The initial implementation should favor explicit GM-controlled turns. Autonomous NPC-to-NPC exchanges require strict turn and chain-depth limits to prevent runaway conversations and provider costs.

### Conversation curation and canon promotion

The GM must be able to select useful player or NPC dialogue and promote it into persistent campaign lore. This handles improvised facts such as an NPC inventing a guildmaster's name, organization, location, event, or complete character during play.

Expected workflow:

1. Select one or more transcript entries or a text fragment.
2. Choose **Add to lore**.
3. Review and edit the proposed lore rather than saving it automatically.
4. Choose an existing lore entry to append to or create a new entry.
5. Assign title, type, visibility, distribution scopes, provenance, and related entities.
6. Confirm the change as established campaign canon.
7. Reload affected NPC context safely before later conversation turns.

Promoted material should retain provenance linking it to the campaign, session, speaker, timestamp, and original transcript entry. If selected dialogue contains an invented NPC, the review screen should offer to create an NPC record and related lore together. AI-generated dialogue never becomes canon merely because an NPC said it; GM approval is required.

### Pause, resume, and transcript correction

The GM needs immediate control when table discussion goes out of character or a generated/player statement should not influence the campaign.

Pause behavior:

- Provide a prominent pause/resume control and configurable shortcut.
- Stop microphone audio from reaching the provider while paused.
- Stop or suppress NPC output promptly.
- Display an unmistakable paused state.
- Preserve the active scene and transcript so play can resume cleanly.
- Do not transcribe, summarize, memorize, or derive lore from paused table discussion.

Transcript correction behavior:

- Let the GM strike a complete player/NPC turn or selected text within a turn.
- Mark struck material as excluded from AI context, memory extraction, summaries, and lore proposals.
- Visually retain struck material in the GM transcript by default so corrections remain understandable.
- Never show struck material in player-facing exports unless explicitly requested.
- Record who struck it and when, with undo support.
- Offer deliberate permanent deletion separately for privacy-sensitive content.
- If content was already sent to a realtime provider, clearly indicate that striking prevents future reuse but cannot erase the provider's current internal context; restart or rebuild the session context when strict removal is required.

This requires transcript entries to have stable IDs and lifecycle states such as `active`, `struck`, and `promoted`, rather than treating the JSONL transcript as display-only text.

### Session transcription

Play-session transcription should be a planned feature.

Possible modes:

- NPC conversation only
- GM and player microphone channels
- Full table transcription
- Manual notes mixed with automatic transcription

Potential outputs:

- Raw timestamped transcript
- Speaker-labelled transcript when identification is reliable
- Session summary
- NPC-specific memories extracted from the session
- Proposed lore updates requiring GM approval
- Open plot threads
- Mentioned people, places, organizations, and items

Transcription must be opt-in and visibly active. The application should expose retention controls because session recordings and transcripts may contain private player conversations.

## GM generation assistant

Add a separate conversational assistant for campaign creation and maintenance. This assistant is not an NPC and should never share the NPC's in-character prompt.

Example request:

> Define a tavern at the major crossroads and information regarding caravan trade between the nearest two countries.

The GM assistant should be able to:

- Ask clarifying questions
- Read selected existing campaign lore
- Draft people, places, organizations, regions, events, and relationships
- Detect likely conflicts with established facts
- Produce structured proposed changes
- Show a preview or diff
- Save approved output to lore
- Reject or revise output without altering the campaign

Generated material should never become established campaign truth automatically. Use a review flow:

```text
GM conversation
  → generated proposal
  → validation and conflict check
  → GM review/edit
  → approve
  → write to lore
```

Each accepted entry should record provenance such as `gm-authored`, `ai-drafted`, `session-derived`, or `imported`.

## Lore model

Lore needs more structure than one undifferentiated directory. Visibility and distribution are separate concerns and should not be represented by a single label.

### Suggested visibility levels

- Public: common knowledge available broadly
- Restricted: known only to selected groups or people
- Secret: deliberately concealed knowledge
- GM only: never available to NPC reasoning unless explicitly released

### Suggested distribution scopes

- Global
- Country or nation
- Region
- Settlement or local area
- Organization
- Family or faction
- Profession or social group
- Individual NPC

### Suggested familiarity levels

An NPC's relationship to an eligible lore entry may be:

- Certain: the NPC definitely knows it
- Likely: include or retrieve it when contextually relevant
- Possible: the NPC may know it, subject to a rule or check
- Rumor: the NPC knows an uncertain or distorted version
- Unknown: exclude it

These dimensions allow examples such as:

```text
Visibility: Public
Scope: Region — Northern March
Familiarity for Elara: Certain
```

and:

```text
Visibility: Restricted
Scope: Organization — Crossroads Smugglers
Familiarity for Elara: Certain
Familiarity for Captain Rell: Rumor
```

### Preliminary lore record

A future lore record may include:

```yaml
id: crossroads-caravan-trade
title: Caravan trade at the Three Roads
kind: trade
visibility: public
scopes:
  regions:
    - western-border
  settlements:
    - three-roads
  organizations:
    - merchants-league
provenance: gm-authored
status: established
tags:
  - caravans
  - trade
  - roads
content_file: crossroads-caravan-trade.md
```

The exact schema should be designed and tested before implementation.

## Organizations, geography, and inherited knowledge

If campaign management expands, NPC knowledge should be partly derived from relationships rather than copied into every character profile.

Potential entities:

- World
- Country
- Region
- Settlement
- Location
- Organization
- Faction
- Family
- NPC
- Event
- Item
- Lore entry
- Relationship

An NPC could belong to multiple structures:

```text
Elara Voss
├── lives in: Three Roads
├── region: Western Border
├── member of: Tavern Keepers Guild
├── former member of: Crossroads Smugglers
└── relationship: distrusts Captain Rell
```

Knowledge assembly could then follow rules such as:

1. Include lore the NPC knows individually.
2. Include certain lore inherited from current organizations.
3. Include selected historical lore from former affiliations.
4. Include public lore for the NPC's location and region.
5. Retrieve likely or possible lore only when relevant.
6. Exclude GM-only and inaccessible restricted lore.
7. Apply rumor variants instead of canonical facts where configured.

The application must show the GM why an NPC received a piece of lore. A future context inspector should display sources such as:

```text
Included because:
Elara Voss → former member of Crossroads Smugglers → restricted organization lore
```

This explainability will be important for diagnosing unexpected NPC answers.

## Campaign-management expansion

Potential future modules include:

- Campaign dashboard
- Calendar and timeline
- Locations and maps
- Countries, regions, and settlements
- Organizations and factions
- NPC relationships
- Plot threads and quests
- Session planning
- Session transcription and summaries
- Lore conflict detection
- Search and cross-references
- Import/export and backups
- Foundry VTT or other tabletop integrations

These are possibilities, not immediate commitments. New features should support the voice-assistant workflow instead of turning the project into a generic campaign manager before NPC conversation works reliably.

## Storage implications

Human-readable campaign files remain desirable for portability, version control, and manual recovery. As relationships grow, a hybrid approach may be appropriate:

- YAML and Markdown as portable source data
- SQLite as a rebuildable index, search cache, transcript store, or relationship projection
- Media files stored directly in campaign folders
- Machine configuration and credentials stored outside campaigns

The application should avoid absolute paths inside campaign data. IDs and paths should remain relative to the campaign root.

## Proposed delivery order

### Milestone 1 — Conversational NPC vertical slice

- Secure provider configuration
- Stable RoomKit room per campaign and NPC
- Gemini Live connection
- NPC prompt assembled from profile and eligible lore
- Separate private GM direction
- Per-NPC transcript and memory

### Milestone 2 — Multi-NPC validation

- Add a second sample NPC
- Switch active NPCs
- Verify voice, memory, lore, and secret isolation
- Add automated isolation tests

### Milestone 3 — Campaign editing

- View and edit lore
- Append NPC knowledge
- Create and edit NPCs
- Validate and atomically save campaign files
- Add change tracking and backup behavior

### Milestone 4 — Knowledge model

- Structured lore records
- Visibility and distribution scopes
- Organizations and geography
- NPC affiliations
- Explainable knowledge resolution

### Milestone 5 — Session tools

- Optional session transcription
- Session summaries
- Proposed NPC memory updates
- Proposed lore updates requiring GM approval

### Milestone 6 — GM generation assistant

- Separate GM-to-AI conversation
- Structured generation proposals
- Conflict checks
- Preview, edit, approve, and save to lore

### Milestone 7 — Broader campaign management

- Relationships, timelines, locations, organizations, plot threads, integrations, and other modules selected from actual play needs

## Design principles

- The GM remains the authority over campaign truth.
- AI-generated and session-derived content requires approval before becoming established lore.
- GM-only material must never enter player-facing output.
- NPC knowledge must be explainable and testable.
- Per-NPC memory and secrets must remain isolated.
- Campaigns must remain portable across machines.
- Provider-specific configuration must not dominate the campaign domain model.
- Build the voice-assistant workflow first and expand campaign management incrementally.
