import { create } from 'zustand'
import type { ARIAState } from '../lib/websocket'

export interface TranscriptEntry {
  id: string
  type: 'user' | 'aria' | 'action' | 'system'
  content: string
  timestamp: number
  final?: boolean
}

export interface ToastItem {
  id: string
  message: string
  level: 'info' | 'success' | 'warning' | 'error'
}

export interface ARIASettings {
  apiUrl: string
  micSensitivity: number
  screenshotIntervalMs: number
  voiceEnabled: boolean
  theme: 'dark' | 'light'
}

interface ARIAStore {
  // Session
  sessionId: string | null
  connected: boolean
  ariaState: ARIAState
  actionCount: number
  sessionStartTime: number | null
  // Feed
  transcript: TranscriptEntry[]
  // Screen
  lastScreenshot: string | null
  screenShareActive: boolean
  lastClickPos: { x: number; y: number } | null
  // Mic
  micActive: boolean
  // Settings
  settings: ARIASettings
  settingsOpen: boolean
  // Onboarding
  onboardingDone: boolean
  // Toasts
  toasts: ToastItem[]

  // Actions
  setSessionId: (id: string | null) => void
  setConnected: (v: boolean) => void
  setARIAState: (s: ARIAState) => void
  addTranscript: (entry: Omit<TranscriptEntry, 'id'>) => void
  updateLastARIA: (content: string, final: boolean) => void
  setLastScreenshot: (b64: string | null) => void
  setScreenShareActive: (v: boolean) => void
  setLastClickPos: (pos: { x: number; y: number } | null) => void
  setMicActive: (v: boolean) => void
  incrementActionCount: () => void
  pushToast: (msg: string, level: ToastItem['level']) => void
  dismissToast: (id: string) => void
  setSettings: (s: Partial<ARIASettings>) => void
  setSettingsOpen: (v: boolean) => void
  completeOnboarding: () => void
  reset: () => void
}

const loadSettings = (): Partial<ARIASettings> => {
  try { return JSON.parse(localStorage.getItem('aria_settings') || '{}') } catch { return {} }
}

let _toastId = 0

export const useARIAStore = create<ARIAStore>((set, get) => ({
  sessionId: null,
  connected: false,
  ariaState: 'idle',
  actionCount: 0,
  sessionStartTime: null,
  transcript: [],
  lastScreenshot: null,
  screenShareActive: false,
  lastClickPos: null,
  micActive: false,
  settings: {
    apiUrl: 'http://127.0.0.1:8888',
    micSensitivity: 0.7,
    screenshotIntervalMs: 2000,
    voiceEnabled: true,
    theme: 'dark',
    ...loadSettings(),
  },
  settingsOpen: false,
  onboardingDone: localStorage.getItem('aria_onboarding_done') === 'true',
  toasts: [],

  setSessionId: (id) => set({ sessionId: id, sessionStartTime: id ? Date.now() : null }),
  setConnected: (v) => set({ connected: v }),
  setARIAState: (s) => set({ ariaState: s }),

  addTranscript: (entry) =>
    set((state) => ({
      transcript: [
        ...state.transcript,
        { ...entry, id: `t-${Date.now()}-${_toastId++}` },
      ],
    })),

  updateLastARIA: (content, final) =>
    set((state) => {
      const list = [...state.transcript]
      const idx = list.findLastIndex((e) => e.type === 'aria' && !e.final)
      if (idx >= 0) {
        list[idx] = { ...list[idx], content, final }
        return { transcript: list }
      }
      return {
        transcript: [
          ...list,
          { id: `t-${Date.now()}`, type: 'aria', content, timestamp: Date.now(), final },
        ],
      }
    }),

  setLastScreenshot: (b64) => set({ lastScreenshot: b64 }),
  setScreenShareActive: (v) => set({ screenShareActive: v }),
  setLastClickPos: (pos) => set({ lastClickPos: pos }),
  setMicActive: (v) => set({ micActive: v }),
  incrementActionCount: () => set((s) => ({ actionCount: s.actionCount + 1 })),

  pushToast: (message, level) => {
    const id = `toast-${++_toastId}`
    set((s) => ({ toasts: [...s.toasts, { id, message, level }] }))
    setTimeout(() => get().dismissToast(id), 4000)
  },

  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  setSettings: (partial) =>
    set((s) => {
      const next = { ...s.settings, ...partial }
      localStorage.setItem('aria_settings', JSON.stringify(next))
      if (partial.apiUrl) localStorage.setItem('aria_api_url', partial.apiUrl)
      return { settings: next }
    }),

  setSettingsOpen: (v) => set({ settingsOpen: v }),

  completeOnboarding: () => {
    localStorage.setItem('aria_onboarding_done', 'true')
    set({ onboardingDone: true })
  },

  reset: () =>
    set({
      sessionId: null,
      connected: false,
      ariaState: 'idle',
      actionCount: 0,
      sessionStartTime: null,
      transcript: [],
      lastScreenshot: null,
      screenShareActive: false,
      lastClickPos: null,
      micActive: false,
    }),
}))
