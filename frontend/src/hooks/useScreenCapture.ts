import { useRef, useCallback } from 'react'

interface UseScreenCaptureOptions {
  intervalMs?: number
  onFrame: (base64Png: string) => void
}

export function useScreenCapture({ intervalMs = 2000, onFrame }: UseScreenCaptureOptions) {
  const streamRef   = useRef<MediaStream | null>(null)
  const videoRef    = useRef<HTMLVideoElement | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const canvasRef   = useRef<HTMLCanvasElement | null>(null)

  const start = useCallback(async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 1, width: { ideal: 1280 }, height: { ideal: 800 } },
      })
      streamRef.current = stream

      const video = document.createElement('video')
      video.srcObject = stream
      video.muted = true
      await video.play()
      videoRef.current = video

      const canvas = document.createElement('canvas')
      canvas.width = 1280
      canvas.height = 800
      canvasRef.current = canvas

      intervalRef.current = setInterval(() => {
        if (!videoRef.current || !canvasRef.current) return
        if (videoRef.current.readyState < 2) return // not enough data yet
        const ctx = canvasRef.current.getContext('2d')
        if (!ctx) return
        ctx.drawImage(videoRef.current, 0, 0, 1280, 800)
        const b64 = canvasRef.current.toDataURL('image/jpeg', 0.75).split(',')[1]
        if (b64) onFrame(b64)
      }, intervalMs)

      stream.getVideoTracks()[0].onended = () => stop()
      return true
    } catch (e) {
      console.error('Screen capture error:', e)
      return false
    }
  }, [intervalMs, onFrame])

  const stop = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = null
    videoRef.current?.pause()
    videoRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    canvasRef.current = null
  }, [])

  return { start, stop }
}
