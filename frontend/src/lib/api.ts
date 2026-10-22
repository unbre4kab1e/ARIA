import { useARIAStore } from '../store/ariaStore'

/** Backend base URL. Empty = same origin (Vite dev proxy / nginx in Docker). */
export const apiBaseUrl = () => useARIAStore.getState().settings.apiUrl.trim().replace(/\/+$/, '')

/** WebSocket base URL derived from the API URL (or from the page origin). */
export const wsBaseUrl = () => {
  const base = apiBaseUrl()
  if (base) return base.replace(/^http/, 'ws')
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
}

const BASE_URL = apiBaseUrl

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API ${path} (${res.status}): ${err}`)
  }
  return res.json()
}

export const api = {
  createSession: () =>
    request<{ session_id: string }>('/api/sessions', { method: 'POST' }),

  getSession: (id: string) =>
    request<{ session_id: string; state: string; current_task: string | null; history_count: number }>(
      `/api/sessions/${id}`
    ),

  deleteSession: (id: string) =>
    request(`/api/sessions/${id}`, { method: 'DELETE' }),

  getHistory: (id: string) =>
    request<{ history: Array<{ role: string; content: string; timestamp: number }> }>(
      `/api/sessions/${id}/history`
    ),

  analyzeScreen: (screenshot_b64: string, user_intent: string) =>
    request('/api/vision/analyze', {
      method: 'POST',
      body: JSON.stringify({ screenshot_b64, user_intent }),
    }),

  query: (message: string, screenshot_b64?: string) =>
    request<{ response: string }>('/api/query', {
      method: 'POST',
      body: JSON.stringify({ message, screenshot_b64 }),
    }),

  health: () =>
    request<{ status: string; active_sessions: number; gemini_configured: boolean; browser_ready: boolean; browser_error: string | null }>('/api/health'),
}
