from __future__ import annotations

import sys as _sys

_here = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]
if _sys.path:
    head = _sys.path[0]
    if head in {"", ".", _here}:
        _sys.path.pop(0)

import argparse
import getpass
import os


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v not in {"0", "false", "False"}


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _mask(s: str) -> str:
    if not s:
        return ""
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def _prompt_text(label: str, default: str, *, allow_empty: bool) -> str:
    shown = default
    prompt = f"{label}"
    if shown != "":
        prompt += f" [默认: {shown}]"
    prompt += ": "
    while True:
        v = input(prompt)
        if v == "":
            v = default
        if v == "" and not allow_empty:
            continue
        return v


def _prompt_secret(label: str, default: str, *, allow_empty: bool) -> str:
    prompt = f"{label}"
    if default != "":
        prompt += f" [默认: {_mask(default)}]"
    prompt += ": "
    while True:
        v = getpass.getpass(prompt)
        if v == "":
            v = default
        if v == "" and not allow_empty:
            continue
        return v


def _prompt_bool(label: str, default: bool) -> bool:
    d = "y" if default else "n"
    prompt = f"{label} (y/n) [默认: {d}]: "
    while True:
        v = input(prompt).strip().lower()
        if v == "":
            return default
        if v in {"y", "yes", "1", "true"}:
            return True
        if v in {"n", "no", "0", "false"}:
            return False


def _prompt_int(label: str, default: int, *, min_value: int | None = None) -> int:
    prompt = f"{label} [默认: {default}]: "
    while True:
        v = input(prompt).strip()
        if v == "":
            return default
        try:
            n = int(v)
        except Exception:
            continue
        if min_value is not None and n < min_value:
            continue
        return n


def _escape_env_value(v: str) -> str:
    if v == "":
        return '""'
    need_quote = any(ch.isspace() for ch in v) or any(ch in v for ch in ['"', "\\", "#"])
    if not need_quote:
        return v
    v = v.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{v}"'


def _write_env_file(path: str, values: dict[str, str]) -> None:
    lines = [f"{k}={_escape_env_value(v)}" for k, v in values.items()]
    data = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="generate_config_txt.py")
    ap.add_argument("--output", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt"))
    ap.add_argument("--accept-defaults", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    defaults = {
        "V2WH_HID_ENABLED": "1" if _env_bool("V2WH_HID_ENABLED", True) else "0",
        "V2WH_COMMIT_KEY": os.getenv("V2WH_COMMIT_KEY", ""),
        "V2WH_PYAUDIO_DEVICE_INDEX": str(_env_int("V2WH_PYAUDIO_DEVICE_INDEX", 0)),
        "V2WH_SILICONFLOW_API_KEY": os.getenv("V2WH_SILICONFLOW_API_KEY", os.getenv("V2WH_STT_API_KEY", "")),
        "V2WH_STT_MODEL": os.getenv("V2WH_STT_MODEL", ""),
        "V2WH_STT_BASE_URL": os.getenv("V2WH_STT_BASE_URL", ""),
        "V2WH_WUBI_DICT": os.getenv("V2WH_WUBI_DICT", "wubi.json"),
        "V2WH_CORRECTIONS": os.getenv("V2WH_CORRECTIONS", "corrections.json"),
    }

    values = dict(defaults)

    out_path = os.path.abspath(args.output)
    if os.path.exists(out_path) and not args.force and not args.accept_defaults:
        ans = input(f"文件已存在，是否覆盖？{out_path} (y/n) [默认: n]: ").strip().lower()
        if ans not in {"y", "yes"}:
            return 2

    if not args.accept_defaults:
        values["V2WH_HID_ENABLED"] = "1" if _prompt_bool("是否启用 HID 输出（0 时输出到 stdout）", values["V2WH_HID_ENABLED"] != "0") else "0"
        values["V2WH_COMMIT_KEY"] = _prompt_text("每个五笔码后追加的提交键（默认空；如需空格请输入一个空格）", values["V2WH_COMMIT_KEY"], allow_empty=True)
        values["V2WH_PYAUDIO_DEVICE_INDEX"] = str(_prompt_int("PyAudio 输入设备 index", int(values["V2WH_PYAUDIO_DEVICE_INDEX"]), min_value=0))
        values["V2WH_SILICONFLOW_API_KEY"] = _prompt_secret("SiliconFlow API Key（可留空）", values["V2WH_SILICONFLOW_API_KEY"], allow_empty=True)
        values["V2WH_STT_MODEL"] = _prompt_text("STT 模型名（可留空）", values["V2WH_STT_MODEL"], allow_empty=True)
        values["V2WH_STT_BASE_URL"] = _prompt_text("STT base_url（可留空）", values["V2WH_STT_BASE_URL"], allow_empty=True)
        values["V2WH_WUBI_DICT"] = _prompt_text("五笔字典路径", values["V2WH_WUBI_DICT"], allow_empty=False)
        values["V2WH_CORRECTIONS"] = _prompt_text("纠错表路径", values["V2WH_CORRECTIONS"], allow_empty=False)

    _write_env_file(out_path, values)
    print(f"已写入: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
