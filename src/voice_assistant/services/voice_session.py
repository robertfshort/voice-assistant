from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal
from roomkit import RealtimeVoiceChannel, RoomKit
from roomkit.providers.gemini.realtime import GeminiLiveProvider
from roomkit.voice.backends.local import LocalAudioBackend

from voice_assistant.domain.models import Campaign, Npc
from voice_assistant.services.conversation import (
    build_npc_prompt,
    private_gm_request,
    room_id,
)

logger = logging.getLogger(__name__)


class VoiceSessionController(QObject):
    state_changed = Signal(str)
    transcription = Signal(str, str, bool)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._kit: RoomKit | None = None
        self._channel: RealtimeVoiceChannel | None = None
        self._session: Any = None
        self._campaign: Campaign | None = None
        self._npc: Npc | None = None
        self._api_key = ""
        self._model = ""
        self._private_directions: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return self._session is not None

    async def start(
        self,
        campaign: Campaign,
        npc: Npc,
        api_key: str,
        *,
        model: str = "gemini-3.1-flash-live-preview",
    ) -> None:
        if self.active:
            await self.stop()
        if (
            self._campaign is None
            or self._npc is None
            or self._campaign.manifest.id != campaign.manifest.id
            or self._npc.id != npc.id
        ):
            self._private_directions = ()
        self._campaign = campaign
        self._npc = npc
        self._api_key = api_key
        self._model = model
        self.state_changed.emit("connecting")
        try:
            provider = GeminiLiveProvider(api_key=api_key, model=model)
            provider.on_transcription(self._on_transcription)
            transport = LocalAudioBackend(
                input_sample_rate=24000,
                output_sample_rate=24000,
                block_duration_ms=20,
                mute_mic_during_playback=True,
            )
            voice = npc.voice.providers.get("gemini")
            channel = RealtimeVoiceChannel(
                "voice",
                provider=provider,
                transport=transport,
                system_prompt=build_npc_prompt(
                    campaign, npc, private_directions=self._private_directions
                ),
                voice=voice.voice if voice else "Aoede",
                input_sample_rate=24000,
            )
            kit = RoomKit()
            kit.register_channel(channel)
            stable_room_id = room_id(campaign.manifest.id, npc.id)
            await kit.create_room(room_id=stable_room_id)
            await kit.attach_channel(stable_room_id, "voice")
            session = await channel.start_session(
                stable_room_id,
                "local-player",
                connection=None,
            )
            self._kit = kit
            self._channel = channel
            self._session = session
            self.state_changed.emit("active")
        except Exception as exc:
            logger.exception("Unable to start voice session")
            await self.stop()
            self.error.emit(str(exc))
            self.state_changed.emit("idle")

    async def stop(self) -> None:
        channel, session, kit = self._channel, self._session, self._kit
        self._channel = None
        self._session = None
        self._kit = None
        try:
            if channel is not None and session is not None:
                await channel.end_session(session)
            if kit is not None:
                await kit.close()
        except Exception:
            logger.exception("Unable to stop voice session cleanly")
        self.state_changed.emit("idle")

    async def send_player_text(self, text: str) -> None:
        if self._channel is None or self._session is None:
            return
        await self._channel.inject_text(self._session, text, role="user")

    async def send_gm_instruction(self, text: str, *, request_response: bool = False) -> None:
        if self._channel is None or self._session is None:
            return
        if request_response:
            await self._channel.inject_text(
                self._session,
                private_gm_request(text),
                role="user",
                silent=False,
            )
            return
        if self._campaign is None or self._npc is None:
            return
        self._private_directions = (*self._private_directions, text.strip())
        updated_prompt = build_npc_prompt(
            self._campaign,
            self._npc,
            private_directions=self._private_directions,
        )
        try:
            await self._channel.reconfigure_session(self._session, system_prompt=updated_prompt)
        except Exception:
            logger.exception("Reconfigure failed; restarting voice session")
            campaign, npc, api_key, model = (
                self._campaign,
                self._npc,
                self._api_key,
                self._model,
            )
            await self.stop()
            await self.start(campaign, npc, api_key, model=model)

    def _on_transcription(self, _session: Any, text: str, role: str, is_final: bool) -> None:
        self.transcription.emit(text, role, is_final)
