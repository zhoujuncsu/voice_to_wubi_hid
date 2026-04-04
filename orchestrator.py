from __future__ import annotations

import threading
from collections.abc import Callable

from .config import TranslateConfig
from .formatters import tokens_to_keystrokes
from .interfaces import AudioSource, KeyEmitter, LedController, SpeechToTextEngine, TextTranslator


class Orchestrator:
    def __init__(
        self,
        *,
        stt: SpeechToTextEngine,
        translator: TextTranslator,
        emitter: KeyEmitter,
        translate_cfg: TranslateConfig,
        led: LedController | None = None,
        on_text: Callable[[str], None] | None = None,
        on_partial: Callable[[str], None] | None = None,
        enable_partial: bool = False,
    ):
        self._stt = stt
        self._translator = translator
        self._emitter = emitter
        self._translate_cfg = translate_cfg
        self._led = led
        self._on_text = on_text
        self._on_partial = on_partial
        self._enable_partial = enable_partial

    @property
    def emitter(self) -> KeyEmitter:
        return self._emitter

    def close(self) -> None:
        self._emitter.close()

    def run(self, audio: AudioSource, stop: threading.Event) -> str:
        if self._led is not None:
            self._led.on_recording_start()

        final_text_parts: list[str] = []
        try:
            for chunk in audio.frames(stop):
                for ev in self._stt.feed_pcm16le(chunk):
                    if ev.kind == "partial":
                        if self._enable_partial and self._on_partial is not None:
                            self._on_partial(ev.text)
                        continue

                    text = ev.text
                    if not text:
                        continue
                    final_text_parts.append(text)
                    if self._on_text is not None:
                        self._on_text(text)

                    tokens = self._translator.text_to_tokens(text)
                    keystrokes = tokens_to_keystrokes(tokens, commit_key=self._translate_cfg.commit_key)
                    if keystrokes:
                        self._emitter.send_text(keystrokes)

            for ev in self._stt.finish():
                if ev.kind == "partial":
                    continue
                text = ev.text
                if not text:
                    continue
                final_text_parts.append(text)
                if self._on_text is not None:
                    self._on_text(text)
                tokens = self._translator.text_to_tokens(text)
                keystrokes = tokens_to_keystrokes(tokens, commit_key=self._translate_cfg.commit_key)
                if keystrokes:
                    self._emitter.send_text(keystrokes)

        finally:
            if self._led is not None:
                self._led.on_recording_stop()

        return "".join(final_text_parts)
