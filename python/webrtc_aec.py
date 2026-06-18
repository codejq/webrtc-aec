"""
webrtc_aec — pure-ctypes loader for the webrtc_aec shared library (WebRTC AEC3).

Drop the CI-built binaries into python/lib/:
    python/lib/webrtc_aec-windows-x64.dll
    python/lib/webrtc_aec-linux-x86_64.so
    python/lib/webrtc_aec-linux-aarch64.so

Then in the STT, before feeding a frame to Vosk/Moonshine:
    from webrtc_aec import EchoCanceller
    aec = EchoCanceller(16000)
    clean = aec.process(mic_frame_i16, ref_frame_i16, delay_ms=40)

`mic_frame` and `ref_frame` are 10 ms mono int16 numpy arrays (sample_rate//100
samples). `ref` is what's playing on the speakers (the Stereo-Mix loopback or the
TTS PCM). Returns the echo-cancelled mic frame (int16 numpy array).
"""

import ctypes
import os
import platform

import numpy as np

_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")


def _lib_name() -> str:
    sysname = platform.system()
    machine = platform.machine().lower()
    if sysname == "Windows":
        return "webrtc_aec-windows-x64.dll"
    if sysname == "Linux":
        if machine in ("aarch64", "arm64"):
            return "webrtc_aec-linux-aarch64.so"
        return "webrtc_aec-linux-x86_64.so"
    raise RuntimeError(f"webrtc_aec: unsupported platform {sysname}/{machine}")


def _load():
    path = os.path.join(_LIB_DIR, _lib_name())
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"webrtc_aec binary not found: {path}\n"
            "Download it from the GitHub Actions 'build-webrtc-aec' run and place it in python/lib/."
        )
    lib = ctypes.CDLL(path)
    lib.WebRtcAec_Create.argtypes = [ctypes.c_int]
    lib.WebRtcAec_Create.restype = ctypes.c_void_p
    lib.WebRtcAec_Process.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int16),
        ctypes.POINTER(ctypes.c_int16),
        ctypes.POINTER(ctypes.c_int16),
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.WebRtcAec_Process.restype = ctypes.c_int
    lib.WebRtcAec_Destroy.argtypes = [ctypes.c_void_p]
    return lib


class EchoCanceller:
    """WebRTC AEC3 echo canceller. Process audio in 10 ms mono int16 frames."""

    def __init__(self, sample_rate: int = 16000):
        self._lib = _load()
        self.sample_rate = sample_rate
        self.frame = sample_rate // 100  # 10 ms
        self._h = self._lib.WebRtcAec_Create(sample_rate)
        if not self._h:
            raise RuntimeError("webrtc_aec: failed to create echo canceller")

    def process(self, mic: np.ndarray, ref: np.ndarray, delay_ms: int = 40) -> np.ndarray:
        """Return `mic` with the echo of `ref` removed. Both must be int16 mono
        arrays of exactly sample_rate//100 samples (a 10 ms frame)."""
        mic = np.ascontiguousarray(mic, dtype=np.int16)
        ref = np.ascontiguousarray(ref, dtype=np.int16)
        if len(mic) != self.frame or len(ref) != self.frame:
            raise ValueError(f"frames must be {self.frame} samples (10 ms @ {self.sample_rate} Hz)")
        out = np.empty(self.frame, dtype=np.int16)
        rc = self._lib.WebRtcAec_Process(
            self._h,
            mic.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            ref.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            self.frame,
            delay_ms,
        )
        if rc != 0:
            # Non-fatal: on error, fall back to the raw mic frame.
            return mic
        return out

    def close(self):
        if getattr(self, "_h", None):
            self._lib.WebRtcAec_Destroy(self._h)
            self._h = None

    def __del__(self):
        self.close()
