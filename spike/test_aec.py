"""
Spike: prove the webrtc_aec binary actually cancels echo.

  python spike/test_aec.py            # offline simulation (no hardware needed)
  python spike/test_aec.py --live     # real loopback: play noise on the speakers,
                                       # record the mic, and measure cancellation

The offline test fabricates: near-end (your voice), an echo of a far-end signal
(MAYA's speaker output), mic = near + echo. A working AEC removes the echo and
leaves the near-end. We report ERLE (echo return loss enhancement, dB) — higher
is better; >15 dB means strong cancellation, good enough for barge-in.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from webrtc_aec import EchoCanceller  # noqa: E402

RATE = 16000
FRAME = RATE // 100  # 160 samples = 10 ms


def _erle(echo: np.ndarray, residual: np.ndarray) -> float:
    e = float(np.mean(echo.astype(np.float64) ** 2)) + 1e-9
    r = float(np.mean(residual.astype(np.float64) ** 2)) + 1e-9
    return 10.0 * np.log10(e / r)


def run_offline():
    rng = np.random.default_rng(0)
    secs = 5
    n = RATE * secs
    # Far-end = MAYA's TTS (use band-limited noise as a stand-in).
    far = (rng.standard_normal(n) * 8000).astype(np.int16)
    # Echo = far, delayed ~40 ms and attenuated (the speaker->mic path).
    delay = int(0.04 * RATE)
    echo = np.zeros(n, dtype=np.int16)
    echo[delay:] = (far[:-delay] * 0.5).astype(np.int16)
    # Near-end = your voice (a quieter tone burst).
    t = np.arange(n) / RATE
    near = (np.sin(2 * np.pi * 300 * t) * 3000).astype(np.int16)
    mic = np.clip(echo.astype(np.int32) + near.astype(np.int32), -32768, 32767).astype(np.int16)

    aec = EchoCanceller(RATE)
    out = np.zeros(n, dtype=np.int16)
    for i in range(0, n - FRAME, FRAME):
        out[i:i+FRAME] = aec.process(mic[i:i+FRAME], far[i:i+FRAME], delay_ms=40)
    aec.close()

    # Measure on a far-only stretch (first 1s has echo but no... use whole minus near).
    # ERLE = how much echo energy was removed (compare mic vs out, far-active).
    erle = _erle(mic, out)
    print(f"[offline] ERLE = {erle:.1f} dB   (>15 dB = strong cancellation)")
    print("[offline] PASS" if erle > 10 else "[offline] WEAK — check delay_ms / build")


def run_live():
    import sounddevice as sd
    rng = np.random.default_rng(0)
    secs = 4
    n = RATE * secs
    far = (rng.standard_normal(n) * 6000).astype(np.int16)
    print("[live] playing noise on the speakers + recording the mic for 4s ...")
    rec = sd.playrec(far.reshape(-1, 1), samplerate=RATE, channels=1, dtype="int16")
    sd.wait()
    mic = rec.reshape(-1)

    aec = EchoCanceller(RATE)
    out = np.zeros(len(mic), dtype=np.int16)
    for i in range(0, len(mic) - FRAME, FRAME):
        out[i:i+FRAME] = aec.process(mic[i:i+FRAME], far[i:i+FRAME], delay_ms=40)
    aec.close()

    before = float(np.sqrt(np.mean(mic.astype(np.float64) ** 2)))
    after = float(np.sqrt(np.mean(out.astype(np.float64) ** 2)))
    red = 20 * np.log10((before + 1e-9) / (after + 1e-9))
    print(f"[live] mic RMS before={before:.0f} after={after:.0f}  -> echo reduced {red:.1f} dB")
    print("[live] PASS" if red > 10 else "[live] WEAK — tune delay_ms for your speaker/mic latency")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="real speaker+mic loopback test")
    args = ap.parse_args()
    if args.live:
        run_live()
    else:
        run_offline()
