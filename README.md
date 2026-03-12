# ARIA — Adaptive Reality Intelligence Assistant

> *Your AI co-pilot that sees your screen, hears your voice, and acts on your world — in real time.*

ARIA is a next-generation multimodal AI agent built for the Google AI Hackathon.
It combines **Gemini Live API** (real-time voice), **Gemini Vision** (screen understanding), and **Google ADK** (autonomous tool execution) into a single seamless experience.

---

## Demo

**Voice → Screen Control in 3 seconds:**
1. "ARIA, go to Google and search for flights to Tokyo"
2. ARIA narrates: *"Navigating to Google..."* → clicks search bar → types query → presses Enter
3. "Actually, show me the cheapest option" — ARIA **interrupts its own action** and pivots

---

## Categories Covered

| Category | How ARIA qualifies |
|---|---|
| **Live Agent** | Real-time voice via Gemini Live API, natural interruptions, spoken responses |
| **UI Navigator** | Sees the browser via screenshots, clicks/types/scrolls autonomously via Playwright |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     ARIA Frontend (React)                        │
│   WebRTC Mic → PCM chunks      getDisplayMedia → PNG frames      │
│                         ↕ WebSocket                              │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI + Cloud Run)                    │
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────┐                     │
│  │  Gemini Live    │    │  ADK Agent       │                     │
│  │  (voice/audio)  │    │  (task planning) │                     │
│  └─────────────────┘    └────────┬─────────┘                     │
│                                  │ tool calls                    │
│  ┌───────────────┐  ┌────────────▼──────────┐  ┌─────────────┐  │
│  │ Gemini Vision │  │ Playwright Controller  │  │   Session   │  │
│  │ (screenshot   │  │ navigate/click/type    │  │   Manager   │  │
│  │  analysis)    │  │ scroll/screenshot      │  │             │  │
│  └───────────────┘  └───────────────────────┘  └─────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| **AI — Voice** | Gemini 2.0 Flash Live API |
| **AI — Vision** | Gemini 2.0 Flash (multimodal) |
| **Agent Framework** | Google ADK (Agent Development Kit) |
| **Backend** | Python 3.12, FastAPI, WebSockets |
| **Browser Control** | Playwright (Chromium) |
| **Frontend** | React 18, TypeScript, TailwindCSS, WebRTC |
| **Cloud** | Google Cloud Run, Secret Manager, Artifact Registry |
| **CI/CD** | Google Cloud Build |

---

## Project Structure

```
challenge/
├── backend/
│   ├── main.py                  FastAPI app entry point
│   ├── config.py                Environment config
│   ├── Dockerfile               Cloud Run ready
│   ├── requirements.txt
│   ├── agents/
│   │   ├── aria_agent.py        ADK Agent with all tools
│   │   ├── runner.py            Per-session ADK InMemoryRunner
│   │   └── tools/
│   │       ├── browser_tools.py Playwright: navigate/click/type/scroll
│   │       ├── vision_tools.py  Gemini Vision ADK tools
│   │       └── system_tools.py  Time, notifications, history
│   ├── api/
│   │   ├── routes.py            REST endpoints
│   │   └── websocket.py         Full-duplex WS session handler
│   └── services/
│       ├── gemini_live.py       Gemini Live API service
│       ├── vision.py            Gemini Vision one-shot service
│       └── session.py           Session state machine + TTL
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              3-panel layout
│   │   ├── components/
│   │   │   ├── ARIAOrb.tsx      Animated state orb
│   │   │   ├── TranscriptFeed.tsx  Live chat + action log
│   │   │   ├── ScreenPreview.tsx   Screenshot panel
│   │   │   ├── ControlBar.tsx      Mic/Screen/Interrupt/Text
│   │   │   ├── StatusPanel.tsx     Session metrics
│   │   │   ├── SettingsModal.tsx   Config overlay
│   │   │   ├── OnboardingOverlay.tsx  3-step wizard
│   │   │   └── Toast.tsx           Notifications
│   │   ├── hooks/
│   │   │   ├── useARIASession.ts   Session + WS lifecycle
│   │   │   ├── useMicrophone.ts    WebRTC mic → PCM
│   │   │   ├── useScreenCapture.ts getDisplayMedia → PNG
│   │   │   └── useAudioOutput.ts   PCM audio playback
│   │   ├── store/ariaStore.ts   Zustand global state
│   │   └── lib/
│   │       ├── api.ts           REST client
│   │       ├── websocket.ts     Typed WS client
│   │       └── audio.ts         PCM helpers
│   └── Dockerfile               Nginx multi-stage build
│
├── docker-compose.yml           Local dev (one command)
├── cloudbuild.yaml              GCP CI/CD pipeline
└── setup-gcp.sh                 One-time GCP provisioning
```

---

## Quick Start — Local Development

### Prerequisites
- Python 3.12+
- Node.js 20+
- A [Gemini API key](https://aistudio.google.com/app/apikey)

### 1. Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY

# Run
python main.py
# → http://localhost:8000
```

### 2. Frontend

```bash
cd frontend

npm install
npm run dev
# → http://localhost:5173
```

### 3. Docker (full stack)

```bash
# Fill in backend/.env first
docker compose up --build
# → Frontend: http://localhost:3000
# → Backend:  http://localhost:8000
```

---

## Cloud Deployment (Google Cloud Run)

### 1. Provision GCP resources

```bash
bash setup-gcp.sh YOUR_PROJECT_ID
```

### 2. Add your API key to Secret Manager

```bash
echo -n "YOUR_GEMINI_API_KEY" | \
  gcloud secrets versions add aria-google-api-key --data-file=-
```

### 3. Deploy via Cloud Build

```bash
gcloud builds submit --config=cloudbuild.yaml --project=YOUR_PROJECT_ID
```

This builds both Docker images, pushes to Artifact Registry, and deploys to Cloud Run.

---

## Key Features

### Real-time Voice + Vision
- Mic audio streamed as 16kHz PCM to Gemini Live API
- Screenshots captured every 2s and sent alongside voice for context
- ARIA responds with both text transcript and synthesized voice

### Interruption Handling
At any point, saying "stop", "wait", or "actually..." — or pressing the interrupt button — immediately halts ARIA's current action chain and awaits new instructions.

### Multi-step Autonomous Tasks
ARIA can chain complex workflows:
```
"Book me a round trip to Paris in April under €500"
→ navigate(google.com/flights)
→ type("Paris round trip April")
→ scroll(down)
→ click(cheapest option)
→ "Found a flight for €420 on April 12th. Shall I continue?"
```

### Screen-aware Q&A
Point at anything on screen and ask "what does this button do?" — ARIA uses Gemini Vision to describe it.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini API key | required |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | required for Cloud |
| `GOOGLE_CLOUD_REGION` | GCP region | `us-central1` |
| `PORT` | Backend port | `8000` |
| `DEBUG` | Enable debug logs | `false` |
| `BROWSER_HEADLESS` | Run Playwright headless | `true` |
| `SCREENSHOT_INTERVAL_MS` | Vision polling interval | `2000` |
| `SESSION_TTL_SECONDS` | Session idle timeout | `3600` |
| `MAX_SESSIONS` | Concurrent session limit | `10` |

---

## Google Cloud Services Used

- **Gemini Live API** — real-time bidirectional audio + multimodal
- **Gemini 2.0 Flash** — vision / screenshot analysis
- **Google ADK** — agent orchestration, tool calling
- **Cloud Run** — serverless container hosting (backend + frontend)
- **Artifact Registry** — Docker image storage
- **Secret Manager** — API key secure storage
- **Cloud Build** — CI/CD pipeline

---

*Built for the Google AI Hackathon — Live Agents × UI Navigator categories.*
