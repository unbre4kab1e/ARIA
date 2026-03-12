import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        orbitron: ['Orbitron', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        syne: ['Syne', 'sans-serif'],
      },
      colors: {
        void: '#0a0a0f',
        surface: '#0f0f1a',
        panel: '#13131f',
        border: '#1e1e30',
        'border-bright': '#2a2a45',
        neon: {
          blue: '#3b82f6',
          cyan: '#06b6d4',
          green: '#10b981',
          orange: '#f97316',
          red: '#ef4444',
          purple: '#8b5cf6',
        },
      },
      animation: {
        'orb-idle':    'orb-idle 4s ease-in-out infinite',
        'orb-listen':  'orb-listen 1.5s ease-in-out infinite',
        'orb-think':   'orb-think 1s linear infinite',
        'orb-act':     'orb-act 0.5s ease-in-out infinite',
        'pulse-ring':  'pulse-ring 2s ease-out infinite',
        'scan-line':   'scan-line 3s linear infinite',
        'waveform':    'waveform 0.5s ease-in-out infinite alternate',
        'fade-up':     'fade-up 0.4s ease-out forwards',
        'glow-flicker':'glow-flicker 3s ease-in-out infinite',
      },
      keyframes: {
        'orb-idle': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.5' },
          '50%':      { transform: 'scale(1.05)', opacity: '0.7' },
        },
        'orb-listen': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%':      { transform: 'scale(1.15)' },
        },
        'orb-think': {
          '0%':   { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'orb-act': {
          '0%, 100%': { transform: 'scale(1.1)', opacity: '0.9' },
          '50%':      { transform: 'scale(1.25)', opacity: '1' },
        },
        'pulse-ring': {
          '0%':   { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(2)',   opacity: '0' },
        },
        'scan-line': {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        'waveform': {
          '0%':   { height: '4px' },
          '100%': { height: '20px' },
        },
        'fade-up': {
          '0%':   { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        'glow-flicker': {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
