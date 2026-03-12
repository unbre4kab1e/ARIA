import { useRef, useCallback } from 'react'
import { base64ToBuffer } from '../lib/audio'

export function useAudioOutput() {
  const ctxRef = useRef<AudioContext | null>(null)
  const nextStartTime = useRef<number>(0)

  const enqueue = useCallback((base64Pcm: string) => {
    try {
      // 1. Initialize a single AudioContext on the first chunk
      if (!ctxRef.current || ctxRef.current.state === 'closed') {
        ctxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 })
        nextStartTime.current = ctxRef.current.currentTime
      }

      const ctx = ctxRef.current

      // Resume if suspended (browser autoplay policy)
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {})
      }

      // 2. Decode the incoming Int16 base64 PCM data to Float32
      const raw = base64ToBuffer(base64Pcm)
      if (raw.byteLength === 0) return

      const int16 = new Int16Array(raw)
      const float32 = new Float32Array(int16.length)
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768
      }

      // 3. Create an audio buffer
      const audioBuffer = ctx.createBuffer(1, float32.length, 24000)
      audioBuffer.copyToChannel(float32, 0)

      // 4. Create source and schedule it to play exactly after the previous chunk finishes
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)

      // Reset scheduling if there's been a gap (e.g. silence between turns)
      const now = ctx.currentTime
      if (nextStartTime.current < now) {
        nextStartTime.current = now
      }

      source.start(nextStartTime.current)
      nextStartTime.current += audioBuffer.duration
    } catch (err) {
      console.warn('Audio output error:', err)
    }
  }, [])

  // Call on interrupt to immediately stop all queued audio
  const stop = useCallback(() => {
    if (ctxRef.current && ctxRef.current.state !== 'closed') {
      ctxRef.current.close().catch(() => {})
      ctxRef.current = null
    }
    nextStartTime.current = 0
  }, [])

  return { enqueue, stop }
}
