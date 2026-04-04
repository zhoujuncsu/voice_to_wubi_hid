from __future__ import annotations

from collections.abc import Iterable
import os
import tempfile
import wave

from ..config import STTConfig
from ..interfaces import SpeechToTextEngine
from ..types import TranscriptionEvent


class SiliconFlowStreamingSTT(SpeechToTextEngine):
    def __init__(self, cfg: STTConfig, *, sample_rate: int, channels: int):
        try:
            from openai import OpenAI
        except Exception as e:
            raise RuntimeError("SiliconFlowStreamingSTT 需要安装 openai：pip install openai") from e

        api_key = cfg.api_key or os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            raise RuntimeError("缺少 SiliconFlow API Key：请设置 V2WH_SILICONFLOW_API_KEY（或 V2WH_STT_API_KEY）")

        base_url = cfg.base_url or "https://api.siliconflow.cn/v1"
        model = cfg.model or "FunAudioLLM/SenseVoiceSmall"

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._sample_rate = sample_rate
        self._channels = channels
        self._buf: list[bytes] = []

    def feed_pcm16le(self, chunk: bytes) -> Iterable[TranscriptionEvent]:
        self._buf.append(chunk)
        return ()

    def finish(self) -> Iterable[TranscriptionEvent]:
        if not self._buf:
            return ()

        if self._channels != 1:
            raise RuntimeError("当前 STT 仅支持 mono（channels=1），请调整 AudioSource 输出为单声道")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        try:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(self._channels)
                wf.setsampwidth(2)
                wf.setframerate(self._sample_rate)
                wf.writeframes(b"".join(self._buf))

            with open(wav_path, "rb") as audio_file:
                tr = self._client.audio.transcriptions.create(model=self._model, file=audio_file)
            text = getattr(tr, "text", None) or ""
            if text:
                return (TranscriptionEvent(kind="final", text=text),)
            return ()
        finally:
            self._buf.clear()
            try:
                os.remove(wav_path)
            except Exception:
                pass
