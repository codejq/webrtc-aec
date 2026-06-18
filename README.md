# webrtc-aec — WebRTC AEC3 echo canceller for MAYA (Windows + Linux)

WebRTC's AEC3 has no pip wheel on Windows (it needs the full WebRTC C++ tree to
compile). So this repo lets **GitHub Actions** compile it for every platform MAYA
runs on, and ships a tiny C shared library you load from Python via `ctypes` — one
binary works for any Python 3.x, no wheels.

**Goal:** let MAYA hear you *while she is speaking* (barge-in). The current STT uses
an echo **gate** that mutes listening whenever the speakers are active. AEC instead
*subtracts* MAYA's voice from the mic, so she can listen and talk at the same time.

## How it works

```
mic (your voice + echo of MAYA)  ─┐
                                  ├─► WebRtcAec_Process ─► clean mic (your voice) ─► Vosk/Moonshine
speaker reference (MAYA's TTS) ───┘
```

- `src/webrtc_aec.cpp` — thin C ABI over the WebRTC APM AEC3.
- `CMakeLists.txt` — builds it into `webrtc_aec.dll` / `libwebrtc_aec.so`, linking
  `webrtc-audio-processing` **v1.x** (the version that has AEC3 — the apt `v0.3`
  only has the legacy AEC).
- `.github/workflows/build.yml` — builds `webrtc-audio-processing` v1.x from source
  (meson) + this wrapper for **windows-x64**, **linux-x86_64**, **linux-aarch64**
  (Pi 5 / Jetson), and uploads each as an artifact.
- `python/webrtc_aec.py` — pure-ctypes loader that picks the right binary per platform.
- `spike/test_aec.py` — proves the binary actually cancels echo (offline + live).

## Use it

1. Push this folder to GitHub:
   ```
   git remote add origin https://github.com/<you>/webrtc-aec.git
   git push -u origin main
   ```
2. Open the **Actions** tab → wait for `build-webrtc-aec` → download the three
   artifacts (`webrtc_aec-windows-x64`, `webrtc_aec-linux-x86_64`,
   `webrtc_aec-linux-aarch64`).
3. Drop the binaries into `python/lib/` (keep the platform-suffixed names).
4. Validate:
   ```
   python spike/test_aec.py          # offline ERLE check
   python spike/test_aec.py --live   # real speaker+mic cancellation
   ```
5. Once proven, wire `EchoCanceller` into the STT **before** the VAD/recognizer, and
   relax the echo gate so MAYA stays listening while she speaks.

## Notes / expectations

- **AEC3 requires `webrtc-audio-processing` v1.x.** Building it from source (meson +
  abseil subproject) on **Windows/MSVC** is the fragile part — the first CI run may
  fail and need a tweak or two (that's normal for cross-platform native builds). The
  Linux builds are the well-trodden path.
- `delay_ms` in `process()` is the speaker→mic round-trip latency; tune it on real
  hardware (the live spike helps). Wrong delay = poor cancellation.
- Frames are **10 ms mono int16** (`sample_rate // 100` samples) — the APM's required
  block size.
