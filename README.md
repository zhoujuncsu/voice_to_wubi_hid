# voice_to_wubi_hid

语音 → 流式转写 → 五笔编码 → USB HID 键盘输出（面向对象重构版）

Speech → Streaming STT → Wubi codes → USB HID keyboard output (OO refactor)

---

## 简介（中文）

本项目把整条链路抽象成可替换、可测试、可组合的流水线（Pipeline）：

1. **音频输入**：reSpeaker 2-Mics Pi HAT（PyAudio）或 WAV 文件  
2. **流式转写**：通过 `cognition` 中的 SiliconFlow STT + VAD 做分段转写  
3. **五笔翻译**：按字符（单字模式）把文本转换为五笔码；支持 `corrections.json` 覆盖与中文标点映射  
4. **HID 输出**：调用 `rpi_hid` 把字符/五笔码当作“键盘输入”发送到 `/dev/hidg0`

---

## Overview (English)

This project provides a composable and testable pipeline:

1. **Audio input**: reSpeaker 2-Mics Pi HAT (PyAudio) or a WAV file  
2. **Streaming STT**: segmenting transcription via `cognition` (SiliconFlow STT + VAD)  
3. **Wubi translation**: per-character (single-char mode) mapping to Wubi codes; supports `corrections.json` override and Chinese punctuation mapping  
4. **HID output**: sends keystrokes via `rpi_hid` to `/dev/hidg0` as a USB keyboard gadget

---

## 核心抽象 / Core Abstractions

这些组件通过接口解耦，便于替换与单元测试：

- **AudioSource**：产生 PCM16LE 音频帧（reSpeaker/WAV）
- **SpeechToTextEngine**：把 PCM16LE 帧转换为转写事件（partial/final）
- **TextTranslator**：把文本转换为五笔 token（含标点/ASCII 策略）
- **KeyEmitter**：把按键序列输出到 HID（或 stdout）
- **Orchestrator**：驱动整条流水线的生命周期（start/stop/finish）

代码入口参考：
- `voice_to_wubi_hid/orchestrator.py`
- `voice_to_wubi_hid/cli.py`

---

## 运行方式 / How to Run

在项目根目录执行 / Run in the project root:

### 1) WAV 模式（无硬件验证 / no hardware）

```bash
python -m voice_to_wubi_hid wav --wav path/to/16k_mono_pcm16.wav
```

说明：
- WAV 需要是 **PCM16**；建议 **16kHz / mono**（与默认流式转写配置一致）
- 若不想真实输出到 HID，请设置 `V2WH_HID_ENABLED=0`

### 2) reSpeaker 模式（按 Ctrl+C 停止 / Ctrl+C to stop）

```bash
python -m voice_to_wubi_hid respeaker
```

### 3) GPIO 按钮切换开始/停止（树莓派环境 / Raspberry Pi）

```bash
python -m voice_to_wubi_hid gpio --pin 17
```

说明：
- 按一下开始会话，再按一下停止会话
- LED（若可用）会在会话开始/结束时开关效果

---

## 配置（环境变量）/ Configuration (Env Vars)

这些环境变量用于覆盖默认配置（默认值见 `voice_to_wubi_hid/config.py`）：

- `V2WH_HID_ENABLED=0|1`：是否启用 HID 输出（0 时输出到 stdout）
- `V2WH_COMMIT_KEY`：每个五笔码后追加的提交键（例如空格/回车等；默认空）
- `V2WH_PYAUDIO_DEVICE_INDEX`：PyAudio 输入设备 index（reSpeaker）
- `V2WH_STT_MODEL`：覆盖 SiliconFlow 模型名
- `V2WH_STT_BASE_URL`：覆盖 SiliconFlow base_url
- `V2WH_WUBI_DICT`：五笔字典路径（默认 `wubi.json`）
- `V2WH_CORRECTIONS`：纠错表路径（默认 `corrections.json`）

安全提示 / Security:
- 不要把 API Key 写进代码或日志。SiliconFlow 的密钥应由 `cognition` 的配置读取机制提供。

---

## 依赖与运行环境 / Dependencies & Runtime

### 树莓派（reSpeaker + HID）/ Raspberry Pi (reSpeaker + HID)

- `pyaudio`（采集音频）
- `RPi.GPIO`（GPIO 按钮）
- `cognition`（流式转写封装，包含 SiliconFlow 相关实现）
- `rpi_hid`（USB HID Gadget 键盘输出；需要系统侧已配置 `/dev/hidg0`）

---

## 硬件安装与系统配置 / Hardware Setup

### ReSpeaker 2-Mics Pi HAT（录音硬件）/ ReSpeaker 2-Mics Pi HAT (Audio)

建议按官方文档完成硬件连接与驱动/配置：

- Seeed Studio Wiki（中文）：https://wiki.seeedstudio.com/cn/ReSpeaker_2_Mics_Pi_HAT_Raspberry/

常见要点 / Notes:
- 确认系统能识别声卡设备（ALSA 设备列表中可见）
- 若使用 PyAudio 采集：需要正确选择输入设备 index（见环境变量 `V2WH_PYAUDIO_DEVICE_INDEX`）

### Raspberry Pi Zero 2 W / 树莓派 Zero 2 W

本项目可运行在 Raspberry Pi Zero 2 W 上；Zero 2 W 资源较紧张时建议：
- 先用 WAV 模式验证流程，再切换到实时采集
- 适当降低并发输出（例如禁用 partial 或减少额外日志输出）

### USB Gadget（HID 键盘）/ USB Gadget (HID Keyboard)

HID 输出依赖树莓派启用 USB Gadget 模式，并创建 `/dev/hidg0` 设备节点。可以参考下列项目完成系统侧配置：

- GitHub: https://github.com/AbhirupRudra/RPI-HID

完成后检查 / Quick check:
- `/dev/hidg0` 存在且当前用户有写权限
- 连接到主机后，主机识别到一个 USB 键盘设备

### 无硬件环境（WAV 验证）/ No-hardware (WAV verification)

仅运行 WAV 模式时通常不需要 `pyaudio/RPi.GPIO`，但仍需要能导入 `cognition` 才能做真实转写。

如果只想验证翻译与按键串生成，可以先跑单元测试（见下节）。

---

## 测试 / Tests

运行最小单元测试（覆盖五笔翻译与按键串拼接）：

```bash
python -m unittest discover -s voice_to_wubi_hid\\tests -p "test_*.py" -q
```

---

## 常见问题 / FAQ

### Q: 16kHz/mono 为什么重要？
A: 流式转写模块通常对采样率/声道有假设。当前 reSpeaker 采集默认会把 2 声道混成 1 声道（mono），以匹配默认的 16kHz/mono 处理路径。

### Q: 五笔码怎么“上屏”？
A: 默认会把每个汉字的五笔码按键发送出去；如需在目标输入法中自动确认/上屏，可通过 `V2WH_COMMIT_KEY` 在每个码后追加一个提交键（例如空格）。

---

## 生成说明 / Generation Note

本项目的部分代码与文档由 Trae Solo（AI 编程助手）辅助生成，并由作者审核、集成与测试后提交。

Parts of this project (code and documentation) were generated with assistance from Trae Solo (an AI coding assistant) and then reviewed, integrated, and tested by the author.
