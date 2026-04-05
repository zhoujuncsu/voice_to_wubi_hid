from __future__ import annotations

import argparse
import sys
import threading

from .config import AppConfig, load_app_config
from .audio.sources import RespeakerPyAudioSource, WavFileAudioSource
from .hardware.gpio_button import GpioButtonToggle
from .hardware.led import NullLedController, PixelsLedController
from .hid.emitter import RpiHidKeyEmitter, StdoutKeyEmitter
from .orchestrator import Orchestrator
from .stt.xunfei import XunfeiWebSocketStreamingSTT
from .translate.wubi import WubiSingleCharTranslator


def _build_orchestrator(cfg: AppConfig) -> Orchestrator:
    emitter = RpiHidKeyEmitter(inter_key_delay_s=cfg.hid.inter_key_delay_s) if cfg.hid.enabled else StdoutKeyEmitter()
    translator = WubiSingleCharTranslator(cfg.translate.dict_path, cfg.translate.corrections_path)
    stt = XunfeiWebSocketStreamingSTT(cfg.stt, sample_rate=cfg.audio.sample_rate, channels=cfg.audio.output_channels)
    led = PixelsLedController()
    if getattr(led, "_pixels", None) is None:
        led = NullLedController()

    def on_text(t: str) -> None:
        sys.stdout.write(t)
        if not t.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()

    return Orchestrator(
        stt=stt,
        translator=translator,
        emitter=emitter,
        translate_cfg=cfg.translate,
        led=led,
        on_text=on_text,
        enable_partial=cfg.stt.partial,
    )


def _run_wav(cfg: AppConfig, wav_path: str) -> int:
    stop = threading.Event()
    audio = WavFileAudioSource(wav_path, chunk_frames=int(cfg.audio.sample_rate * cfg.stt.frame_ms / 1000))
    orch = _build_orchestrator(cfg)
    with audio, orch.emitter:
        orch.run(audio, stop)
    return 0


def _run_respeaker(cfg: AppConfig) -> int:
    stop = threading.Event()
    audio = RespeakerPyAudioSource(cfg.audio)
    orch = _build_orchestrator(cfg)
    try:
        with audio, orch.emitter:
            orch.run(audio, stop)
    except KeyboardInterrupt:
        stop.set()
    return 0


def _run_gpio(cfg: AppConfig, pin: int) -> int:
    toggle = GpioButtonToggle(pin=pin)
    toggle.setup()

    active_lock = threading.Lock()
    active = {"running": False, "stop": None, "thread": None}

    def start_session() -> None:
        stop = threading.Event()
        audio = RespeakerPyAudioSource(cfg.audio)
        orch = _build_orchestrator(cfg)

        def worker():
            with audio, orch.emitter:
                orch.run(audio, stop)

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        active["running"] = True
        active["stop"] = stop
        active["thread"] = th

    def stop_session() -> None:
        stop = active["stop"]
        th = active["thread"]
        if stop is not None:
            stop.set()
        if th is not None:
            th.join()
        active["running"] = False
        active["stop"] = None
        active["thread"] = None

    def on_toggle() -> None:
        with active_lock:
            if not active["running"]:
                start_session()
            else:
                stop_session()

    stop = threading.Event()
    try:
        toggle.loop(stop, on_toggle=on_toggle)
    except KeyboardInterrupt:
        stop.set()
        with active_lock:
            if active["running"]:
                stop_session()
    finally:
        toggle.cleanup()
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="voice_to_wubi_hid")
    sub = p.add_subparsers(dest="mode", required=True)

    wav_p = sub.add_parser("wav")
    wav_p.add_argument("--wav", required=True)

    mic_p = sub.add_parser("respeaker")

    gpio_p = sub.add_parser("gpio")
    gpio_p.add_argument("--pin", type=int, default=17)

    args = p.parse_args(argv)
    cfg = load_app_config()

    if args.mode == "wav":
        return _run_wav(cfg, args.wav)
    if args.mode == "respeaker":
        return _run_respeaker(cfg)
    if args.mode == "gpio":
        return _run_gpio(cfg, args.pin)
    raise ValueError(args.mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
