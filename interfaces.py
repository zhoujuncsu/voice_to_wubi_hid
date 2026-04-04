from __future__ import annotations

import abc
import threading
from collections.abc import Iterable, Iterator

from .types import CodeToken, TranscriptionEvent


class AudioSource(abc.ABC):
    @property
    @abc.abstractmethod
    def sample_rate(self) -> int: ...

    @property
    @abc.abstractmethod
    def channels(self) -> int: ...

    @property
    @abc.abstractmethod
    def sample_width_bytes(self) -> int: ...

    @abc.abstractmethod
    def frames(self, stop: threading.Event) -> Iterator[bytes]:
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "AudioSource":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class SpeechToTextEngine(abc.ABC):
    @abc.abstractmethod
    def feed_pcm16le(self, chunk: bytes) -> Iterable[TranscriptionEvent]:
        raise NotImplementedError

    @abc.abstractmethod
    def finish(self) -> Iterable[TranscriptionEvent]:
        raise NotImplementedError


class TextTranslator(abc.ABC):
    @abc.abstractmethod
    def text_to_tokens(self, text: str) -> list[CodeToken]:
        raise NotImplementedError


class KeyEmitter(abc.ABC):
    @abc.abstractmethod
    def send_text(self, text: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "KeyEmitter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class LedController(abc.ABC):
    @abc.abstractmethod
    def on_recording_start(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def on_recording_stop(self) -> None:
        raise NotImplementedError

