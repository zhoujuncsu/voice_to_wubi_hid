from __future__ import annotations

import json
import os
import sys

from ..interfaces import TextTranslator
from ..types import CodeToken


def _external_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class WubiSingleCharTranslator(TextTranslator):
    def __init__(self, dict_path: str, corrections_path: str | None = None):
        self._wubi_dict = self._load_single_char_dict(dict_path)

        if corrections_path is None:
            corrections_path = _external_path("corrections.json")

        self._corrections: dict[str, str] = {}
        if os.path.exists(corrections_path):
            with open(corrections_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
                if isinstance(obj, dict):
                    self._corrections = {str(k): str(v) for k, v in obj.items()}

        self._all_mappings = {**self._wubi_dict, **self._corrections}

        self._chinese_punct_to_key = {
            "，": ",",
            "。": ".",
            "、": "\\",
            "；": ";",
            "‘": "'",
            "’": "'",
            "【": "[",
            "】": "]",
            "《": "<",
            "》": ">",
            "（": "(",
            "）": ")",
        }

        self._chinese_shift_punct_to_key = {
            "！": "!",
            "？": "?",
            "：": ":",
            "“": '"',
            "”": '"',
            "—": "_",
            "·": "~",
            "￥": "$",
            "¥": "$",
        }

    def _load_single_char_dict(self, dict_path: str) -> dict[str, str]:
        if not os.path.exists(dict_path):
            raise FileNotFoundError(f"Dictionary file not found: {dict_path}")
        with open(dict_path, "r", encoding="utf-8") as f:
            full_dict = json.load(f)
        if not isinstance(full_dict, dict):
            raise ValueError("wubi.json 格式应为 {汉字: 五笔码} 的对象")
        return {str(k): str(v) for k, v in full_dict.items() if isinstance(k, str) and len(k) == 1}

    def text_to_tokens(self, text: str) -> list[CodeToken]:
        out: list[CodeToken] = []
        for ch in text:
            if ch in self._all_mappings:
                out.append(CodeToken(text=ch, code=self._all_mappings[ch], type="wubi"))
            elif ch in self._chinese_punct_to_key:
                out.append(CodeToken(text=ch, code=self._chinese_punct_to_key[ch], type="chinese_punct"))
            elif ch in self._chinese_shift_punct_to_key:
                out.append(
                    CodeToken(
                        text=ch,
                        code=self._chinese_shift_punct_to_key[ch],
                        type="chinese_punct_shift",
                    )
                )
            elif ord(ch) < 128:
                out.append(CodeToken(text=ch, code=ch, type="raw"))
            else:
                out.append(CodeToken(text=ch, code="", type="unknown"))
        return out

