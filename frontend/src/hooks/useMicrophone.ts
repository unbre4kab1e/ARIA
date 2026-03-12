import { useRef, useCallback } from 'react'
import { bufferToBase64 } from '../lib/audio'

interface UseMicrophoneOptions {
  onChunk: (base64Pcm: string) => void
}

export function useMicrophone({ onChunk }: UseMicrophoneOptions) {
  const streamRef  = useRef<MediaStream | null>(null)
  const ctxRef     = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const activeRef  = useRef(false)

  const start = useCallback(async () => {
    if (activeRef.current) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000, // hint — browser may honour it, eliminating resampling
        },
      })
      streamRef.current = stream

      const ctx = new AudioContext()
      ctxRef.current = ctx

      // AudioWorklet runs on the audio rendering thread — never drops buffers due to main thread load
      await ctx.audioWorklet.addModule('/mic-processor.js')

      const source  = ctx.createMediaStreamSource(stream)
      const worklet = new AudioWorkletNode(ctx, 'mic-processor')
      workletRef.current = worklet

      worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        if (!activeRef.current) return
        onChunk(bufferToBase64(e.data))
      }

      source.connect(worklet)
      // Do NOT connect worklet to ctx.destination — we process only, no playback echo
      activeRef.current = true
    } catch (e) {
      console.error('Mic error:', e)
    }
  }, [onChunk])

  const stop = useCallback(() => {
    activeRef.current = false
    workletRef.current?.disconnect()
    workletRef.current = null
    ctxRef.current?.close()
    ctxRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  return { start, stop }
}
