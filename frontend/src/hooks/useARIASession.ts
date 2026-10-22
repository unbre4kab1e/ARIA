import { useCallback, useRef } from 'react'
import { api, wsBaseUrl } from '../lib/api'
import { ARIAWebSocket } from '../lib/websocket'
import { useARIAStore } from '../store/ariaStore'
import { useAudioOutput } from './useAudioOutput'

export function useARIASession() {
  const wsRef = useRef<ARIAWebSocket | null>(null)
  const audioOutput = useAudioOutput()

  const connect = useCallback(async () => {
    const { setSessionId, setConnected, setARIAState, addTranscript, updateLastARIA, incrementActionCount, pushToast, setBrowserFrame, setLastClickPos } = useARIAStore.getState()
    try {
      const { session_id } = await api.createSession()
      setSessionId(session_id)

      const health = await api.health().catch(() => null)
      if (health && !health.gemini_configured) pushToast('Backend has no GOOGLE_API_KEY — Gemini calls will fail', 'warning')
      if (health && !health.browser_ready) pushToast('Backend browser unavailable — run `playwright install chromium`', 'warning')

      const ws = new ARIAWebSocket(session_id, wsBaseUrl())
      wsRef.current = ws

      ws.onMessage((msg) => {
        const { settings: currentSettings } = useARIAStore.getState()
        switch (msg.type) {
          case 'state':
            if (msg.state) setARIAState(msg.state)
            // Barge-in or manual interrupt: drop whatever audio is still queued
            if (msg.state === 'interrupted') audioOutput.stop()
            break
          case 'text':
            if (msg.role === 'user') {
              addTranscript({ type: 'user', content: msg.content ?? '', timestamp: Date.now(), final: true })
            } else if (msg.content) {
              // Streaming transcript: update the open bubble, close it on final
              updateLastARIA(msg.content, !!msg.final)
            }
            break
          case 'audio':
            if (msg.data && currentSettings.voiceEnabled) {
              audioOutput.enqueue(msg.data)
            }
            break
          case 'action':
            addTranscript({
              type: 'action',
              content: `→ ${msg.action ?? ''}${msg.detail ? ': ' + msg.detail : ''}`,
              timestamp: Date.now(),
            })
            incrementActionCount()
            if (msg.action === 'click_element' && msg.x != null && msg.y != null) {
              setLastClickPos({ x: msg.x, y: msg.y })
            }
            break
          case 'browser_frame':
            if (msg.data) setBrowserFrame(msg.data)
            break
          case 'notification':
            pushToast(msg.message ?? '', msg.level ?? 'info')
            break
          case 'error':
            pushToast(msg.message ?? 'Unknown error', 'error')
            addTranscript({ type: 'system', content: msg.message ?? 'Unknown error', timestamp: Date.now() })
            break
        }
      })

      await ws.connect()
      setConnected(true)
      pushToast('Connected to ARIA', 'success')
    } catch (e) {
      useARIAStore.getState().pushToast(`Connection failed: ${(e as Error).message}`, 'error')
    }
  }, [audioOutput])

  const disconnect = useCallback(async () => {
    wsRef.current?.disconnect()
    wsRef.current = null
    const { sessionId, reset, pushToast } = useARIAStore.getState()
    if (sessionId) await api.deleteSession(sessionId).catch(() => {})
    reset()
    pushToast('Session ended', 'info')
  }, [])

  const sendText = useCallback((content: string) => {
    wsRef.current?.sendText(content)
    useARIAStore.getState().addTranscript({ type: 'user', content, timestamp: Date.now() })
  }, [])

  const sendAudio      = useCallback((b64: string) => wsRef.current?.sendAudio(b64), [])
  const sendScreenshot = useCallback((b64: string) => {
    wsRef.current?.sendScreenshot(b64)
    useARIAStore.getState().setLastScreenshot(b64)
  }, [])

  const interrupt = useCallback(() => {
    wsRef.current?.sendInterrupt()
    audioOutput.stop() // immediately stop any queued audio
    const { setARIAState, addTranscript } = useARIAStore.getState()
    setARIAState('interrupted')
    addTranscript({ type: 'system', content: 'Interrupted', timestamp: Date.now() })
  }, [audioOutput])

  return { connect, disconnect, sendText, sendAudio, sendScreenshot, interrupt, ws: wsRef }
}
