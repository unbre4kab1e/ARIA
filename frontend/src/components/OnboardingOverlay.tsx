import { useState } from 'react'
import { useARIAStore } from '../store/ariaStore'

const STEPS = [
  {
    icon: (
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" strokeWidth="1.5">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8" y1="23" x2="16" y2="23"/>
      </svg>
    ),
    title: 'Allow Microphone',
    desc: 'ARIA needs mic access to hear your voice commands. Start a session, then approve mic permissions when prompted.',
    accentVar: 'var(--accent-blue)',
  },
  {
    icon: (
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" strokeWidth="1.5">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
      </svg>
    ),
    title: 'Share Your Screen',
    desc: 'Click the screen share button so ARIA can see what you\'re working on and take actions on your behalf.',
    accentVar: 'var(--accent-cyan)',
  },
  {
    icon: (
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" strokeWidth="1.5">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    ),
    title: 'Say Hello to ARIA',
    desc: 'Activate your mic and say something like "ARIA, go to Google and search for the weather in Paris."',
    accentVar: 'var(--accent-green)',
  },
]

export function OnboardingOverlay() {
  const { onboardingDone, completeOnboarding } = useARIAStore()
  const [step, setStep] = useState(0)

  if (onboardingDone) return null

  const c = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(14px)' }}>

      <div className="relative w-full max-w-lg rounded-3xl p-9 text-center"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-bright)',
          boxShadow: '0 30px 80px rgba(0,0,0,0.3)',
        }}>

        {/* Corner marks */}
        <div className="absolute top-0 left-0 w-5 h-5 rounded-tl-3xl"
          style={{ borderTop: `1px solid ${c.accentVar}`, borderLeft: `1px solid ${c.accentVar}`, opacity: 0.5 }} />
        <div className="absolute bottom-0 right-0 w-5 h-5 rounded-br-3xl"
          style={{ borderBottom: `1px solid ${c.accentVar}`, borderRight: `1px solid ${c.accentVar}`, opacity: 0.5 }} />

        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-8">
          {STEPS.map((_, i) => (
            <div key={i} className="rounded-full transition-all duration-300"
              style={{
                width: i === step ? 22 : 6, height: 6,
                background: i <= step ? c.accentVar : 'var(--border-bright)',
              }} />
          ))}
        </div>

        {/* Icon */}
        <div className="w-20 h-20 rounded-2xl mx-auto mb-6 flex items-center justify-center"
          style={{
            background: 'var(--bg-pill)',
            border: '1px solid var(--border)',
          }}>
          {c.icon}
        </div>

        {/* Text */}
        <h2 className="font-orbitron text-lg font-bold mb-3 tracking-wider"
          style={{ color: c.accentVar }}>
          {c.title}
        </h2>
        <p className="font-syne text-sm leading-relaxed mb-9"
          style={{ color: 'var(--text-secondary)' }}>
          {c.desc}
        </p>

        {/* Buttons */}
        <div className="flex items-center justify-center gap-4">
          <button onClick={completeOnboarding}
            className="font-mono text-xs uppercase tracking-widest px-4 py-2 transition-colors"
            style={{ color: 'var(--text-muted)' }}>
            Skip
          </button>
          <button onClick={() => isLast ? completeOnboarding() : setStep(step + 1)}
            className="font-mono text-sm px-6 py-2.5 rounded-xl transition-all tracking-wider uppercase"
            style={{
              background: 'var(--bg-pill)',
              border: `1px solid ${c.accentVar}`,
              color: c.accentVar,
            }}>
            {isLast ? 'Get Started →' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  )
}
