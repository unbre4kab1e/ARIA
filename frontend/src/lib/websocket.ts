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
}

type MessageHandler = (msg: WSMessage) => void

export class ARIAWebSocket {
  private ws: WebSocket | null = null
  private handlers: Set<MessageHandler> = new Set()
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = true
  private connecting = false

  constructor(
    private readonly sessionId: string,
    private readonly baseUrl: string
  ) {}

  connect(): Promise<void> {
    if (this.connecting || this.ws?.readyState === WebSocket.OPEN) return Promise.resolve()
    this.connecting = true
    this.shouldReconnect = true
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${this.baseUrl}/ws/${this.sessionId}`)

      this.ws.onopen = () => {
        this.connecting = false
        this.startPing()
        resolve()
      }
      this.ws.onerror = (e) => {
        this.connecting = false
        reject(e)
      }
      this.ws.onmessage = (e) => {
        try {
          const msg: WSMessage = JSON.parse(e.data)
          this.handlers.forEach((h) => h(msg))
        } catch (err) { console.warn('WS message parse error:', err) }
      }
      this.ws.onclose = () => {
        this.connecting = false
        this.stopPing()
        if (this.shouldReconnect) {
          this.reconnectTimeout = setTimeout(() => {
            // Reconnect silently — handlers are preserved, no need to re-add
            this.reconnectInternal()
          }, 2000)
        }
      }
    })
  }

  /** Internal reconnect — doesn't reject on error, just retries */
  private reconnectInternal() {
    if (!this.shouldReconnect || this.connecting) return
    this.connecting = true

    const ws = new WebSocket(`${this.baseUrl}/ws/${this.sessionId}`)

    ws.onopen = () => {
      this.ws = ws
      this.connecting = false
      this.startPing()
    }
    ws.onerror = () => {
      this.connecting = false
      // Retry again after delay
      if (this.shouldReconnect) {
        this.reconnectTimeout = setTimeout(() => this.reconnectInternal(), 3000)
      }
    }
    ws.onmessage = (e) => {
      try {
        const msg: WSMessage = JSON.parse(e.data)
        this.handlers.forEach((h) => h(msg))
      } catch (err) { console.warn('WS message parse error:', err) }
    }
    ws.onclose = () => {
      this.connecting = false
      this.stopPing()
      if (this.shouldReconnect) {
        this.reconnectTimeout = setTimeout(() => this.reconnectInternal(), 3000)
      }
    }
  }

  disconnect() {
    this.shouldReconnect = false
    this.stopPing()
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    this.ws?.close()
    this.ws = null
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
