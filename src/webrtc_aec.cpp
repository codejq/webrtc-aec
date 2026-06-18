// webrtc_aec.cpp — a thin C ABI around WebRTC's Audio Processing Module (APM)
// echo canceller (AEC3), compiled to a shared library (.dll / .so) that MAYA's
// STT loads via ctypes. One binary works for any Python 3.x — no wheels.
//
// AEC3 lives in webrtc-audio-processing v1.x+ (the old apt v0.3 only has the
// legacy AEC), so the CI builds v1.x from source and links it here.
//
// Usage (per 10 ms mono frame, int16 @ sample_rate; frame = sample_rate/100):
//   void* h = WebRtcAec_Create(16000);
//   WebRtcAec_Process(h, mic, ref, out, 160, delay_ms);  // out = mic with echo removed
//   WebRtcAec_Destroy(h);

#include <cstdint>
#include <vector>

#include "modules/audio_processing/include/audio_processing.h"

using webrtc::AudioProcessing;
using webrtc::AudioProcessingBuilder;
using webrtc::StreamConfig;

#if defined(_WIN32)
#define AEC_API extern "C" __declspec(dllexport)
#else
#define AEC_API extern "C" __attribute__((visibility("default")))
#endif

namespace {
struct AecHandle {
  rtc::scoped_refptr<AudioProcessing> apm;
  StreamConfig config;
  int rate = 16000;
};
}  // namespace

// Create an echo canceller for the given sample rate (8000/16000/32000/48000).
AEC_API void* WebRtcAec_Create(int sample_rate) {
  auto* h = new AecHandle();
  h->rate = sample_rate;
  h->apm = AudioProcessingBuilder().Create();
  if (!h->apm) {
    delete h;
    return nullptr;
  }
  AudioProcessing::Config cfg;
  cfg.echo_canceller.enabled = true;
  cfg.echo_canceller.mobile_mode = false;   // full AEC3 (not the mobile AECM)
  cfg.high_pass_filter.enabled = true;
  cfg.gain_controller1.enabled = false;     // leave gain to the mic; we only want echo gone
  cfg.noise_suppression.enabled = true;
  cfg.noise_suppression.level =
      AudioProcessing::Config::NoiseSuppression::Level::kModerate;
  h->apm->ApplyConfig(cfg);
  h->config = StreamConfig(sample_rate, /*num_channels=*/1);
  return h;
}

// Process one mono int16 frame of `num_samples` (must equal sample_rate/100,
// i.e. a 10 ms frame). `mic` = captured audio (your voice + echo of the speaker),
// `ref` = the audio currently going to the speakers (MAYA's TTS / playback).
// `out` receives the echo-cancelled mic (may alias `mic`). `delay_ms` is the
// estimated round-trip speaker->mic latency. Returns 0 on success.
AEC_API int WebRtcAec_Process(void* handle, const int16_t* mic, const int16_t* ref,
                              int16_t* out, int num_samples, int delay_ms) {
  auto* h = static_cast<AecHandle*>(handle);
  if (!h || !h->apm) return -1;

  // Feed the far-end (render/reverse) stream first — what the speakers play.
  std::vector<int16_t> ref_out(static_cast<size_t>(num_samples));
  int r = h->apm->ProcessReverseStream(ref, h->config, h->config, ref_out.data());
  if (r != AudioProcessing::kNoError) return r;

  h->apm->set_stream_delay_ms(delay_ms);

  // Process the near-end (capture) stream — the mic — removing the echo.
  return h->apm->ProcessStream(mic, h->config, h->config, out);
}

AEC_API void WebRtcAec_Destroy(void* handle) {
  delete static_cast<AecHandle*>(handle);
}
