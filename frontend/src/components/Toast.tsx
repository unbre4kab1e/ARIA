import { useARIAStore, type ToastItem } from '../store/ariaStore'

const STYLES: Record<ToastItem['level'], { border: string; iconColor: string; icon: string }> = {
  info:    { border: 'rgba(59,130,246,0.3)',  iconColor: 'var(--accent-blue)',   icon: 'ℹ' },
  success: { border: 'rgba(16,185,129,0.3)',  iconColor: 'var(--accent-green)',  icon: '✓' },
  warning: { border: 'rgba(249,115,22,0.3)',  iconColor: 'var(--accent-orange)', icon: '⚠' },
  error:   { border: 'rgba(239,68,68,0.3)',   iconColor: 'var(--accent-red)',    icon: '✕' },
}

export function ToastContainer() {
  const toasts  = useARIAStore((s) => s.toasts)
  const dismiss = useARIAStore((s) => s.dismissToast)

  return (
    <div className="fixed bottom-24 right-4 z-50 flex flex-col gap-2 items-end pointer-events-none">
      {toasts.map((t) => {
        const s = STYLES[t.level]
        return (
          <div key={t.id} onClick={() => dismiss(t.id)}
            className="animate-fade-up pointer-events-auto flex items-center gap-2.5 px-4 py-2.5 rounded-xl cursor-pointer"
            style={{
              background: 'var(--bg-card)',
              border: `1px solid ${s.border}`,
              backdropFilter: 'blur(14px)',
              maxWidth: 300,
            }}>
            <span className="font-mono text-sm font-bold" style={{ color: s.iconColor }}>{s.icon}</span>
            <span className="font-syne text-sm" style={{ color: 'var(--text-secondary)' }}>{t.message}</span>
          </div>
        )
      })}
    </div>
  )
}
