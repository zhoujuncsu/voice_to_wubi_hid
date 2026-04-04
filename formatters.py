from __future__ import annotations

from .types import CodeToken


def tokens_to_keystrokes(tokens: list[CodeToken], *, commit_key: str = "") -> str:
    parts: list[str] = []
    for t in tokens:
        if t.type == "wubi":
            if not t.code:
                continue
            parts.append(t.code)
            if commit_key:
                parts.append(commit_key)
        elif t.type in {"raw", "chinese_punct", "chinese_punct_shift"}:
            if t.code:
                parts.append(t.code)
        else:
            continue
    return "".join(parts)

