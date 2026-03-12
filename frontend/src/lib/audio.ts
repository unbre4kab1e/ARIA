export function float32ToInt16(buf: Float32Array): ArrayBuffer {
  const out = new Int16Array(buf.length)
  for (let i = 0; i < buf.length; i++) {
    const s = Math.max(-1, Math.min(1, buf[i]))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out.buffer
}

export function bufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

export function base64ToBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

export async function playPcmAudio(base64: string, sampleRate = 24000): Promise<void> {
  const ctx = new AudioContext({ sampleRate })
  const int16 = new Int16Array(base64ToBuffer(base64))
  const float32 = new Float32Array(int16.length)
  for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768
  const audioBuffer = ctx.createBuffer(1, float32.length, sampleRate)
  audioBuffer.copyToChannel(float32, 0)
  const source = ctx.createBufferSource()
  source.buffer = audioBuffer
  source.connect(ctx.destination)
  source.start()
  return new Promise((resolve) => { source.onended = () => { ctx.close(); resolve() } })
}
