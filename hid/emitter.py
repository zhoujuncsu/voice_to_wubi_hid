from __future__ import annotations

import os
import sys
import time

from ..interfaces import KeyEmitter


def _import_rpi_hid_keyboard():
    try:
        from rpi_hid.keyboard import Keyboard

        return Keyboard
    except Exception:
        here = os.path.abspath(os.path.dirname(__file__))
        root = os.path.abspath(os.path.join(here, "..", ".."))
        candidate = os.path.join(root, "rpi_hid-1.2.5")
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)
        from rpi_hid.keyboard import Keyboard

        return Keyboard


class RpiHidKeyEmitter(KeyEmitter):
    def __init__(self, *, inter_key_delay_s: float = 0.02):
        Keyboard = _import_rpi_hid_keyboard()
        self._kbd = Keyboard(delay=inter_key_delay_s)

    def send_text(self, text: str) -> None:
        self._kbd.type(text)

    def close(self) -> None:
        self._kbd.close()


class StdoutKeyEmitter(KeyEmitter):
    def __init__(self, *, out=None, flush_interval_s: float = 0.0):
        self._out = out or sys.stdout
        self._flush_interval_s = flush_interval_s
        self._last_flush = time.time()

    def send_text(self, text: str) -> None:
        self._out.write(text)
        now = time.time()
        if self._flush_interval_s == 0.0 or now - self._last_flush >= self._flush_interval_s:
            self._out.flush()
            self._last_flush = now

    def close(self) -> None:
        try:
            self._out.flush()
        except Exception:
            pass

