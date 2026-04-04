from __future__ import annotations

from ..interfaces import LedController


class NullLedController(LedController):
    def on_recording_start(self) -> None:
        return

    def on_recording_stop(self) -> None:
        return


class PixelsLedController(LedController):
    def __init__(self):
        try:
            from pixels import pixels
        except Exception:
            pixels = None
        self._pixels = pixels

    def on_recording_start(self) -> None:
        if self._pixels is None:
            return
        self._pixels.speak()

    def on_recording_stop(self) -> None:
        if self._pixels is None:
            return
        self._pixels.off()

