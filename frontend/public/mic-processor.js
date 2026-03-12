/**
 * AudioWorklet processor: resamples to 16kHz and sends Int16 PCM chunks.
 * Runs on the audio rendering thread — never drops buffers due to main thread load.
 */
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = []
    this._inputSampleRate = sampleRate // AudioWorkletGlobalScope.sampleRate
    this._targetSampleRate = 16000
    this._ratio = this._inputSampleRate / this._targetSampleRate
    // Send ~100ms chunks: 16000 * 0.1 = 1600 samples
    this._chunkSize = 1600
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true

    const samples = input[0] // Float32Array, mono

    // Resample to 16kHz
    const outputLen = Math.floor(samples.length / this._ratio)
    for (let i = 0; i < outputLen; i++) {
      const srcIdx = i * this._ratio
      const idx = Math.floor(srcIdx)
      const frac = srcIdx - idx
      const a = samples[idx] ?? 0
      const b = samples[Math.min(idx + 1, samples.length - 1)] ?? 0
      this._buffer.push(a + frac * (b - a))
    }

    // Emit in fixed-size chunks
    while (this._buffer.length >= this._chunkSize) {
      const chunk = this._buffer.splice(0, this._chunkSize)
      const int16 = new Int16Array(chunk.length)
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]))
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
      }
      this.port.postMessage(int16.buffer, [int16.buffer])
    }

    return true
  }
}

registerProcessor('mic-processor', MicProcessor)
