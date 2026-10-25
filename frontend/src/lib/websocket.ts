export type WSMessageType =
  | 'audio' | 'screenshot' | 'text' | 'interrupt' | 'ping'
  | 'state' | 'action' | 'notification' | 'error' | 'pong' | 'browser_frame'

export type ARIAState = 'idle' | 'listening' | 'thinking' | 'acting' | 'interrupted'

export interface WSMessage {
  type: WSMessageType
  data?: string
  content?: string
  final?: boolean
  state?: ARIAState
  action?: string
  detail?: string
  message?: string
  level?: 'info' | 'success' | 'warning' | 'error'
  role?: 'user' | 'aria'
  x?: number
  y?: number
  url?: string
  title?: string
}

/** 'open' / 'reconnecting' are transient; 'closed' means the server refused the session for good. */
export type WSStatus =
  | { kind: 'open' }
  | { kind: 'reconnecting' }
  | { kind: 'closed'; reason: 'unauthorized' | 'session_not_found' }

type MessageHandler = (msg: WSMessage) => void
type StatusHandler = (status: WSStatus) => void

// Close codes sent by the backend for errors that a retry can't fix
const CLOSE_UNAUTHORIZED = 4401
const CLOSE_SESSION_NOT_FOUND = 4404

export class ARIAWebSocket {
  private ws: WebSocket | null = null
  private handlers: Set<MessageHandler> = new Set()
  private statusHandlers: Set<StatusHandler> = new Set()
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = true

  constructor(
    private readonly sessionId: string,
    private readonly baseUrl: string,
    private readonly token = '',
  ) {}

  private get url() {
    const query = this.token ? `?token=${encodeURIComponent(this.token)}` : ''
    return `${this.baseUrl}/ws/${this.sessionId}${query}`
  }

  /** Resolves on the first successful open; later drops reconnect automatically. */
  connect(): Promise<void> {
    this.shouldReconnect = true
    return new Promise((resolve, reject) => this.open(resolve, reject))
  }

  private open(onFirstOpen?: () => void, onFirstError?: (e: unknown) => void) {
    const ws = new WebSocket(this.url)
    this.ws = ws
    let opened = false

    ws.onopen = () => {
      opened = true
      this.startPing()
      this.emitStatus({ kind: 'open' })
      onFirstOpen?.()
    }
    ws.onmessage = (e) => {
      try {
        const msg: WSMessage = JSON.parse(e.data)
        this.handlers.forEach((h) => h(msg))
      } catch (err) { console.warn('WS message parse error:', err) }
    }
    ws.onclose = (e) => {
      this.stopPing()
      if (this.ws !== ws) return // replaced by a newer socket
      if (e.code === CLOSE_UNAUTHORIZED || e.code === CLOSE_SESSION_NOT_FOUND) {
        this.shouldReconnect = false
        this.emitStatus({
          kind: 'closed',
          reason: e.code === CLOSE_UNAUTHORIZED ? 'unauthorized' : 'session_not_found',
        })
        return
      }
      if (!opened && onFirstError) {
        onFirstError(new Error('WebSocket connection failed'))
        return
      }
      if (this.shouldReconnect) {
        this.emitStatus({ kind: 'reconnecting' })
        this.reconnectTimeout = setTimeout(() => this.open(), 2000)
      }
    }
  }

  disconnect() {
    this.shouldReconnect = false
    this.stopPing()
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    const ws = this.ws
    this.ws = null
    ws?.close()
  }

  send(msg: WSMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  sendAudio(base64Pcm: string)    { this.send({ type: 'audio',     data: base64Pcm }) }
  sendScreenshot(base64Png: string){ this.send({ type: 'screenshot', data: base64Png }) }
  sendText(content: string)        { this.send({ type: 'text',       content }) }
  sendInterrupt()                  { this.send({ type: 'interrupt' }) }

  onMessage(handler: MessageHandler) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  onStatus(handler: StatusHandler) {
    this.statusHandlers.add(handler)
    return () => this.statusHandlers.delete(handler)
  }

  private emitStatus(status: WSStatus) {
    this.statusHandlers.forEach((h) => h(status))
  }

  private startPing() {
    this.stopPing()
    this.pingInterval = setInterval(() => this.send({ type: 'ping' }), 20_000)
  }
  private stopPing() {
    if (this.pingInterval) clearInterval(this.pingInterval)
    this.pingInterval = null
  }

  get connected() { return this.ws?.readyState === WebSocket.OPEN }
}
