from __future__ import annotations

import threading
import wave
from collections.abc import Iterator

from ..config import AudioConfig
from ..interfaces import AudioSource
from .utils import stereo_pcm16le_to_mono_pcm16le


class RespeakerPyAudioSource(AudioSource):
    def __init__(self, cfg: AudioConfig):
        self._cfg = cfg
        self._p = None
        self._stream = None

    @property
    def sample_rate(self) -> int:
        return self._cfg.sample_rate

    @property
    def channels(self) -> int:
        return self._cfg.output_channels

    @property
    def sample_width_bytes(self) -> int:
        return self._cfg.sample_width_bytes

    def _ensure_open(self) -> None:
        if self._stream is not None:
            return
        try:
            import pyaudio
        except Exception as e:
            raise RuntimeError("RespeakerPyAudioSource 需要安装 pyaudio") from e

        self._p = pyaudio.PyAudio()
        self._stream = self._p.open(
            rate=self._cfg.sample_rate,
            format=self._p.get_format_from_width(self._cfg.sample_width_bytes),
            channels=self._cfg.input_channels,
            input=True,
            input_device_index=self._cfg.pyaudio_device_index,
            frames_per_buffer=self._cfg.chunk_frames,
        )

    def frames(self, stop: threading.Event) -> Iterator[bytes]:
        self._ensure_open()
        assert self._stream is not None
        while not stop.is_set():
            data = self._stream.read(self._cfg.chunk_frames, exception_on_overflow=False)
            if self._cfg.input_channels == 2 and self._cfg.output_channels == 1:
                yield stereo_pcm16le_to_mono_pcm16le(data)
            else:
                yield data

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
            finally:
                self._stream.close()
            self._stream = None
        if self._p is not None:
            self._p.terminate()
            self._p = None


class WavFileAudioSource(AudioSource):
    def __init__(self, wav_path: str, *, chunk_frames: int = 320):
        self._wav_path = wav_path
        self._chunk_frames = chunk_frames
        self._wf: wave.Wave_read | None = None

    @property
    def sample_rate(self) -> int:
        self._ensure_open()
        assert self._wf is not None
        return self._wf.getframerate()

    @property
    def channels(self) -> int:
        self._ensure_open()
        assert self._wf is not None
        return self._wf.getnchannels()

    @property
    def sample_width_bytes(self) -> int:
        self._ensure_open()
        assert self._wf is not None
        return self._wf.getsampwidth()

    def _ensure_open(self) -> None:
        if self._wf is not None:
            return
        self._wf = wave.open(self._wav_path, "rb")
        if self._wf.getsampwidth() != 2:
            raise ValueError("WAV 仅支持 PCM16")

    def frames(self, stop: threading.Event) -> Iterator[bytes]:
        self._ensure_open()
        assert self._wf is not None
        while not stop.is_set():
            data = self._wf.readframes(self._chunk_frames)
            if not data:
                break
            yield data

    def close(self) -> None:
        if self._wf is not None:
            self._wf.close()
            self._wf = None

