from __future__ import annotations

from collections.abc import Iterable
import base64
import datetime
import hashlib
import hmac
import json
import os
import queue
import threading
import time
import urllib.parse
import uuid

from ..config import STTConfig
from ..interfaces import SpeechToTextEngine
from ..types import TranscriptionEvent


class XunfeiWebSocketStreamingSTT(SpeechToTextEngine):
    def __init__(self, cfg: STTConfig, *, sample_rate: int, channels: int):
        try:
            from websocket import WebSocketException, create_connection
        except Exception as e:
            raise RuntimeError("XunfeiWebSocketStreamingSTT 需要安装 websocket-client：pip install websocket-client") from e

        if channels != 1:
            raise RuntimeError("讯飞 STT 仅支持 mono（channels=1），请调整 AudioSource 输出为单声道")
        if sample_rate != 16000:
            raise RuntimeError("讯飞 STT 仅支持 16k 采样率（sample_rate=16000）")

        app_id = cfg.xunfei_app_id or os.getenv("V2WH_XUNFEI_APPID") or os.getenv("V2WH_XUNFEI_APP_ID")
        api_key = cfg.xunfei_api_key or os.getenv("V2WH_XUNFEI_APIKEY") or os.getenv("V2WH_XUNFEI_API_KEY")
        api_secret = cfg.xunfei_api_secret or os.getenv("V2WH_XUNFEI_APISECRET") or os.getenv("V2WH_XUNFEI_API_SECRET")
        base_ws_url = cfg.xunfei_ws_url or os.getenv("V2WH_XUNFEI_WS_URL") or "wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1"

        if not app_id or not api_key or not api_secret:
            raise RuntimeError("缺少讯飞鉴权信息：请设置 V2WH_XUNFEI_APPID/V2WH_XUNFEI_APIKEY/V2WH_XUNFEI_APISECRET（或在 STTConfig 中配置）")

        self._ws = None
        self._ws_lock = threading.Lock()
        self._connected = False
        self._session_id: str | None = None
        self._rx_thread: threading.Thread | None = None
        self._rx_stop = threading.Event()
        self._done = threading.Event()
        self._events: queue.Queue[TranscriptionEvent] = queue.Queue()
        self._last_partial: str = ""

        self._frame_bytes = 1280
        self._frame_interval_ms = 40
        self._send_buf = bytearray()
        self._send_started = False
        self._send_start_ms: float = 0.0
        self._frame_index = 0

        self._create_connection = create_connection
        self._ws_exc = WebSocketException

        full_ws_url = self._build_ws_url(base_ws_url, app_id=app_id, api_key=api_key, api_secret=api_secret)
        self._connect(full_ws_url)

    def _connect(self, full_ws_url: str) -> None:
        with self._ws_lock:
            if self._connected:
                return
            self._ws = self._create_connection(full_ws_url, timeout=15, enable_multithread=True)
            self._connected = True
            self._rx_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._rx_thread.start()

    def _utc_beijing(self) -> str:
        beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(beijing_tz)
        return now.strftime("%Y-%m-%dT%H:%M:%S%z")

    def _build_ws_url(self, base_ws_url: str, *, app_id: str, api_key: str, api_secret: str) -> str:
        params: dict[str, str] = {
            "accessKeyId": api_key,
            "appId": app_id,
            "uuid": uuid.uuid4().hex,
            "utc": self._utc_beijing(),
            "audio_encode": "pcm_s16le",
            "lang": "autodialect",
            "samplerate": "16000",
        }
        sorted_params = dict(sorted([(k, v) for k, v in params.items() if v is not None and str(v).strip() != ""]))
        base_str = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}" for k, v in sorted_params.items()
        )
        signature = hmac.new(api_secret.encode("utf-8"), base_str.encode("utf-8"), hashlib.sha1).digest()
        params["signature"] = base64.b64encode(signature).decode("utf-8")
        return f"{base_ws_url}?{urllib.parse.urlencode(params)}"

    def _recv_loop(self) -> None:
        while not self._rx_stop.is_set():
            ws = self._ws
            if ws is None:
                break
            try:
                msg = ws.recv()
                if not msg:
                    self._done.set()
                    break
                if not isinstance(msg, str):
                    continue
                try:
                    obj = json.loads(msg)
                except Exception:
                    continue
                self._handle_msg(obj)
            except self._ws_exc:
                self._done.set()
                break
            except OSError:
                self._done.set()
                break
            except Exception:
                self._done.set()
                break

    def _handle_msg(self, obj: dict) -> None:
        if obj.get("msg_type") == "action":
            data = obj.get("data") or {}
            sid = data.get("sessionId")
            if isinstance(sid, str) and sid:
                self._session_id = sid
            return

        if obj.get("msg_type") != "result" or obj.get("res_type") != "asr":
            return

        data = obj.get("data") or {}
        cn = data.get("cn") or {}
        st = cn.get("st") or {}
        rt = st.get("rt") or []
        parts: list[str] = []
        try:
            for r in rt:
                ws_list = (r or {}).get("ws") or []
                for wsi in ws_list:
                    cw_list = (wsi or {}).get("cw") or []
                    for cwi in cw_list:
                        w = (cwi or {}).get("w")
                        if isinstance(w, str):
                            parts.append(w)
        except Exception:
            return

        text = "".join(parts).strip()
        if not text:
            return

        ls = bool(st.get("ls"))
        typ = None
        try:
            if rt and isinstance(rt[0], dict):
                typ = rt[0].get("type")
        except Exception:
            typ = None

        if ls or typ == "0":
            self._events.put(TranscriptionEvent(kind="final", text=text))
            self._done.set()
            return

        if text != self._last_partial:
            self._last_partial = text
            self._events.put(TranscriptionEvent(kind="partial", text=text))

    def _pace_and_send_frame(self, ws, frame: bytes) -> None:
        if not self._send_started:
            self._send_started = True
            self._send_start_ms = time.time() * 1000
            self._frame_index = 0

        expected_send_ms = self._send_start_ms + (self._frame_index * self._frame_interval_ms)
        now_ms = time.time() * 1000
        diff_ms = expected_send_ms - now_ms
        if diff_ms > 0.5:
            time.sleep(diff_ms / 1000)

        ws.send_binary(frame)
        self._frame_index += 1

    def _drain_events(self) -> list[TranscriptionEvent]:
        out: list[TranscriptionEvent] = []
        while True:
            try:
                out.append(self._events.get_nowait())
            except queue.Empty:
                break
        return out

    def feed_pcm16le(self, chunk: bytes) -> Iterable[TranscriptionEvent]:
        ws = self._ws
        if ws is None or not self._connected:
            return ()

        if chunk:
            self._send_buf.extend(chunk)
            while len(self._send_buf) >= self._frame_bytes:
                frame = bytes(self._send_buf[: self._frame_bytes])
                del self._send_buf[: self._frame_bytes]
                try:
                    self._pace_and_send_frame(ws, frame)
                except Exception:
                    self._done.set()
                    break

        return tuple(self._drain_events())

    def finish(self) -> Iterable[TranscriptionEvent]:
        ws = self._ws
        if ws is None or not self._connected:
            return ()

        if self._send_buf:
            try:
                self._pace_and_send_frame(ws, bytes(self._send_buf))
            except Exception:
                self._done.set()
            finally:
                self._send_buf.clear()

        end_msg = {"end": True}
        if self._session_id:
            end_msg["sessionId"] = self._session_id
        try:
            ws.send(json.dumps(end_msg, ensure_ascii=False))
        except Exception:
            self._done.set()

        deadline = time.time() + 20
        collected: list[TranscriptionEvent] = []
        while not self._done.is_set() and time.time() < deadline:
            collected.extend(self._drain_events())
            time.sleep(0.05)

        collected.extend(self._drain_events())
        self.close()
        return tuple(collected)

    def close(self) -> None:
        self._rx_stop.set()
        with self._ws_lock:
            ws = self._ws
            self._ws = None
            self._connected = False
        if ws is not None:
            try:
                if getattr(ws, "connected", False):
                    ws.close(status=1000, reason="client close")
            except Exception:
                try:
                    ws.close()
                except Exception:
                    pass

