import { useState, useRef, useCallback, useEffect } from 'react'
import { useARIAStore } from '../store/ariaStore'
import { useARIASession } from '../hooks/useARIASession'
import { useMicrophone } from '../hooks/useMicrophone'
import { useScreenCapture } from '../hooks/useScreenCapture'

export function ControlBar() {
  const connected = useARIAStore((s) => s.connected)
  const micActive = useARIAStore((s) => s.micActive)
  const screenShareActive = useARIAStore((s) => s.screenShareActive)
  const ariaState = useARIAStore((s) => s.ariaState)
  const micSensitivity = useARIAStore((s) => s.settings.micSensitivity)
  const screenshotIntervalMs = useARIAStore((s) => s.settings.screenshotIntervalMs)
  const setMicActive = useARIAStore((s) => s.setMicActive)
  const setScreenShareActive = useARIAStore((s) => s.setScreenShareActive)
  const setSettingsOpen = useARIAStore((s) => s.setSettingsOpen)
  const pushToast = useARIAStore((s) => s.pushToast)

  const { connect, disconnect, sendText, sendAudio, sendScreenshot, interrupt } = useARIASession()
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Use refs to keep stable callback references for hooks
  const sendAudioRef = useRef(sendAudio)
  const sendScreenshotRef = useRef(sendScreenshot)
  useEffect(() => { sendAudioRef.current = sendAudio }, [sendAudio])
  useEffect(() => { sendScreenshotRef.current = sendScreenshot }, [sendScreenshot])

  const mic = useMicrophone({
    onChunk: useCallback((b64: string) => sendAudioRef.current(b64), []),
    sensitivity: micSensitivity,
  })
  const screen = useScreenCapture({
    intervalMs: screenshotIntervalMs,
    onFrame: useCallback((b64: string) => sendScreenshotRef.current(b64), []),
  })

  const toggleMic = useCallback(async () => {
    if (micActive) { mic.stop(); setMicActive(false) }
    else { await mic.start(); setMicActive(true) }
  }, [micActive, mic, setMicActive])

  const toggleScreen = useCallback(async () => {
    if (screenShareActive) { screen.stop(); setScreenShareActive(false) }
    else {
      const ok = await screen.start()
      if (ok) setScreenShareActive(true)
      else pushToast('Screen share permission denied', 'warning')
    }
  }, [screenShareActive, screen, setScreenShareActive, pushToast])

  const handleSend = () => {
    if (!text.trim() || !connected) return
    sendText(text.trim()); setText(''); inputRef.current?.focus()
  }

  /* Generic icon button */
  const Btn = ({ onClick, disabled = false, title, children, active = false, danger = false }: {
    onClick: () => void; disabled?: boolean; title: string;
    children: React.ReactNode; active?: boolean; danger?: boolean
  }) => (
    <button onClick={onClick} disabled={disabled} title={title}
      className="flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-150 disabled:opacity-25"
      style={{
        background: danger ? 'rgba(239,68,68,0.1)' : active ? 'rgba(59,130,246,0.15)' : 'var(--bg-pill)',
        border: danger
          ? '1px solid rgba(239,68,68,0.32)'
          : active
            ? '1px solid var(--border-focus)'
            : '1px solid var(--border)',
        boxShadow: active ? '0 0 14px rgba(59,130,246,0.18)' : 'none',
      }}>
      {children}
    </button>
  )

  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-2xl"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-bright)',
        backdropFilter: 'blur(20px)',
      }}>

      {/* Session toggle */}
      <Btn onClick={connected ? disconnect : connect}
        title={connected ? 'End session' : 'Start session'}
        danger={connected} active={!connected}>
        {connected
          ? <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-red)" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
          : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        }
      </Btn>

      {/* Screen share */}
      <Btn onClick={toggleScreen} disabled={!connected} title="Toggle screen share" active={screenShareActive}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke={screenShareActive ? 'var(--accent-cyan)' : 'var(--text-muted)'} strokeWidth="1.5">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      </Btn>

      {/* ── Mic hero button ── */}
      <div className="flex-1 flex justify-center">
        <button onClick={toggleMic} disabled={!connected}
          className="relative flex items-center justify-center rounded-2xl transition-all duration-200 disabled:opacity-25"
          style={{
            width: 56, height: 56,
            background: micActive
              ? 'linear-gradient(135deg, rgba(59,130,246,0.28), rgba(6,182,212,0.18))'
              : 'var(--bg-pill)',
            border: micActive
              ? '1px solid var(--border-focus)'
              : '1px solid var(--border)',
            boxShadow: micActive ? '0 0 22px rgba(59,130,246,0.25)' : 'none',
          }}>
          {micActive
            ? (
              <div className="flex items-end gap-0.5" style={{ height: 22 }}>
                {Array.from({ length: 7 }).map((_, i) => (
                  <div key={i} className="waveform-bar" style={{ animationDelay: `${i * 0.07}s` }} />
                ))}
              </div>
            )
            : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                stroke="var(--text-muted)" strokeWidth="1.5">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            )
          }
        </button>
      </div>

      {/* Text input */}
      <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl"
        style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
        <input ref={inputRef} type="text" value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder={connected ? 'Type a command...' : 'Connect to start'}
          disabled={!connected}
          className="flex-1 bg-transparent font-mono text-sm outline-none disabled:opacity-30"
          style={{ minWidth: 0, color: 'var(--text-primary)', caretColor: 'var(--accent-blue)' }}
        />
        <button onClick={handleSend} disabled={!connected || !text.trim()}
          className="flex-shrink-0 flex items-center justify-center w-7 h-7 rounded-lg transition-all disabled:opacity-20"
          style={{ background: 'rgba(59,130,246,0.14)', border: '1px solid var(--border-focus)' }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="var(--accent-blue)" strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>

      {/* Interrupt */}
      <Btn onClick={interrupt} disabled={!connected || ariaState === 'idle'}
        title="Interrupt ARIA" danger>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="var(--accent-red)" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <rect x="9" y="9" width="6" height="6"/>
        </svg>
      </Btn>

      {/* Settings */}
      <Btn onClick={() => setSettingsOpen(true)} title="Settings">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="var(--text-muted)" strokeWidth="1.5">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </Btn>
    </div>
  )
}
