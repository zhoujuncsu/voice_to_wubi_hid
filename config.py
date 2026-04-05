from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16000
    input_channels: int = 2
    output_channels: int = 1
    sample_width_bytes: int = 2
    pyaudio_device_index: int = 0
    chunk_frames: int = 1024


@dataclass(frozen=True)
class STTConfig:
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    xunfei_app_id: str | None = None
    xunfei_api_key: str | None = None
    xunfei_api_secret: str | None = None
    xunfei_ws_url: str | None = None
    frame_ms: int = 20
    speech_start_frames: int = 3
    speech_end_silence_ms: int = 500
    partial: bool = False
    partial_interval_s: float = 1.0
    partial_window_s: float = 4.0


@dataclass(frozen=True)
class TranslateConfig:
    dict_path: str = "wubi.json"
    corrections_path: str = "corrections.json"
    commit_key: str = ""


@dataclass(frozen=True)
class HIDConfig:
    enabled: bool = True
    inter_key_delay_s: float = 0.02


@dataclass(frozen=True)
class AppConfig:
    audio: AudioConfig = AudioConfig()
    stt: STTConfig = STTConfig()
    translate: TranslateConfig = TranslateConfig()
    hid: HIDConfig = HIDConfig()


def load_app_config() -> AppConfig:
    commit_key = os.getenv("V2WH_COMMIT_KEY", "")
    hid_enabled = os.getenv("V2WH_HID_ENABLED", "1") not in {"0", "false", "False"}
    device_index = int(os.getenv("V2WH_PYAUDIO_DEVICE_INDEX", "0"))
    api_key = os.getenv("V2WH_SILICONFLOW_API_KEY") or os.getenv("V2WH_STT_API_KEY") or None
    model = os.getenv("V2WH_STT_MODEL") or None
    base_url = os.getenv("V2WH_STT_BASE_URL") or None
    xunfei_app_id = os.getenv("V2WH_XUNFEI_APPID") or os.getenv("V2WH_XUNFEI_APP_ID") or None
    xunfei_api_key = os.getenv("V2WH_XUNFEI_APIKEY") or os.getenv("V2WH_XUNFEI_API_KEY") or None
    xunfei_api_secret = os.getenv("V2WH_XUNFEI_APISECRET") or os.getenv("V2WH_XUNFEI_API_SECRET") or None
    xunfei_ws_url = os.getenv("V2WH_XUNFEI_WS_URL") or None
    dict_path = os.getenv("V2WH_WUBI_DICT", "wubi.json")
    corrections_path = os.getenv("V2WH_CORRECTIONS", "corrections.json")

    return AppConfig(
        audio=AudioConfig(pyaudio_device_index=device_index),
        stt=STTConfig(
            api_key=api_key,
            model=model,
            base_url=base_url,
            xunfei_app_id=xunfei_app_id,
            xunfei_api_key=xunfei_api_key,
            xunfei_api_secret=xunfei_api_secret,
            xunfei_ws_url=xunfei_ws_url,
        ),
        translate=TranslateConfig(
            dict_path=dict_path,
            corrections_path=corrections_path,
            commit_key=commit_key,
        ),
        hid=HIDConfig(enabled=hid_enabled),
    )
