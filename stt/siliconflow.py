from __future__ import annotations

from collections.abc import Iterable

from ..config import STTConfig
from ..interfaces import SpeechToTextEngine
from ..types import TranscriptionEvent


class SiliconFlowStreamingSTT(SpeechToTextEngine):
    def __init__(self, cfg: STTConfig, *, sample_rate: int, channels: int):
        try:
            from cognition import (
                SegmentingStreamTranscriber,
                SiliconFlowConfig,
                SiliconFlowSTTEngine,
                load_siliconflow_config,
            )
            from cognition.streaming import EnergyVAD, EnergyVADConfig
        except Exception as e:
            raise RuntimeError("SiliconFlowStreamingSTT 需要安装/可导入 cognition 包") from e

        cfg0 = load_siliconflow_config()
        sf_cfg = SiliconFlowConfig(
            api_key=cfg0.api_key,
            model=(cfg.model or cfg0.model),
            base_url=(cfg.base_url or cfg0.base_url),
            timeout_s=cfg0.timeout_s,
        )
        stt_engine = SiliconFlowSTTEngine(sf_cfg)

        vad_cfg = EnergyVADConfig(
            sample_rate=sample_rate,
            frame_ms=cfg.frame_ms,
            speech_start_frames=cfg.speech_start_frames,
            speech_end_silence_ms=cfg.speech_end_silence_ms,
        )

        self._transcriber = SegmentingStreamTranscriber(
            stt_engine=stt_engine,
            model=cfg.model,
            sample_rate=sample_rate,
            channels=channels,
            vad=EnergyVAD(vad_cfg),
            partial_interval_s=(cfg.partial_interval_s if cfg.partial else None),
            partial_window_s=cfg.partial_window_s,
        )

    def feed_pcm16le(self, chunk: bytes) -> Iterable[TranscriptionEvent]:
        for ev in self._transcriber.feed_pcm16le(chunk):
            yield TranscriptionEvent(kind=ev.kind, text=ev.text)

    def finish(self) -> Iterable[TranscriptionEvent]:
        for ev in self._transcriber.finish():
            yield TranscriptionEvent(kind=ev.kind, text=ev.text)

