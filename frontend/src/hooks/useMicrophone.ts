import { useRef, useCallback, useEffect } from 'react'
import { bufferToBase64 } from '../lib/audio'

interface UseMicrophoneOptions {
  onChunk: (base64Pcm: string) => void
  /** 0..1 — 0.5 is unity gain, 1 doubles the input level */
  sensitivity?: number
}

const sensitivityToGain = (s: number) => Math.max(0, s) * 2

export function useMicrophone({ onChunk, sensitivity = 0.5 }: UseMicrophoneOptions) {
  const gainRef    = useRef<GainNode | null>(null)
  const streamRef  = useRef<MediaStream | null>(null)
  const ctxRef     = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const activeRef  = useRef(false)

  useEffect(() => {
    if (gainRef.current) gainRef.current.gain.value = sensitivityToGain(sensitivity)
  }, [sensitivity])

  const start = useCallback(async (): Promise<boolean> => {
    if (activeRef.current) return true
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

      const gain = ctx.createGain()
      gain.gain.value = sensitivityToGain(sensitivity)
      gainRef.current = gain

      source.connect(gain)
      gain.connect(worklet)
      // Do NOT connect worklet to ctx.destination — we process only, no playback echo
      activeRef.current = true
      return true
    } catch (e) {
      console.error('Mic error:', e)
      return false
    }
  }, [onChunk, sensitivity])

  const stop = useCallback(() => {
    activeRef.current = false
    workletRef.current?.disconnect()
    workletRef.current = null
    gainRef.current = null
    ctxRef.current?.close()
    ctxRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  return { start, stop }
}
