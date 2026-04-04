from __future__ import annotations

import time
import threading


class GpioButtonToggle:
    def __init__(self, *, pin: int = 17, debounce_s: float = 0.2, poll_s: float = 0.01):
        try:
            import RPi.GPIO as GPIO
        except Exception as e:
            raise RuntimeError("GpioButtonToggle 需要在树莓派环境安装 RPi.GPIO") from e

        self._GPIO = GPIO
        self._pin = pin
        self._debounce_s = debounce_s
        self._poll_s = poll_s
        self._last_state = None
        self._last_edge_ts = 0.0

    def setup(self) -> None:
        GPIO = self._GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self._last_state = GPIO.input(self._pin)

    def loop(self, stop: threading.Event, *, on_toggle) -> None:
        GPIO = self._GPIO
        if self._last_state is None:
            self.setup()

        while not stop.is_set():
            state = GPIO.input(self._pin)
            if state != self._last_state:
                now = time.time()
                if now - self._last_edge_ts >= self._debounce_s:
                    if state == GPIO.LOW:
                        on_toggle()
                    self._last_edge_ts = now
                self._last_state = state
            time.sleep(self._poll_s)

    def cleanup(self) -> None:
        try:
            self._GPIO.cleanup()
        except Exception:
            pass

