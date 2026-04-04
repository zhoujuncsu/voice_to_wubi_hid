from __future__ import annotations

from array import array


def stereo_pcm16le_to_mono_pcm16le(data: bytes) -> bytes:
    samples = array("h")
    samples.frombytes(data)
    if len(samples) % 2 != 0:
        samples = samples[: len(samples) - 1]
    out = array("h", [0]) * (len(samples) // 2)
    j = 0
    for i in range(0, len(samples), 2):
        out[j] = int((samples[i] + samples[i + 1]) / 2)
        j += 1
    return out.tobytes()

