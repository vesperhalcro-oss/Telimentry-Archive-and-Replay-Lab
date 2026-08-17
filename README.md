# Telemetry Archive & Replay Lab

Rough Windows prototype for the Smart India Hackathon 2026 concept deck: live telemetry monitoring, mission archiving, replay scrubbing, FastDTW-style match search, and dual playback comparison.

## What works in this prototype

- **Live mode** — mock rocket telemetry over WebSocket (altitude, battery, attitude, GPS)
- **Replay mode** — load archived missions, variable speed (0.5x–10x), timeline scrubber
- **Archive** — save the current live flight to JSON under `data/archives/`
- **Match search** — DTW-based similarity scoring against archived missions
- **Dual playback** — side-by-side altitude charts for primary vs matched mission
- **Demo data** — four seeded missions on first startup

## Requirements

- Windows 10/11
- Python 3.11+ (tested with 3.14)

## Quick start (Windows)

```powershell
cd C:\Users\razgu\telemetry-replay-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\scripts\run.ps1
```

Open http://127.0.0.1:8000 in your browser.

## API highlights

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/missions` | List archived missions |
| `POST /api/live/reset` | Reset mock live flight |
| `POST /api/archive/live` | Archive current live session |
| `POST /api/match/search` | Find similar missions |
| `WS /ws/live` | Stream live telemetry |
| `WS /ws/replay/{id}` | Replay archived mission |

## Project layout

```
telemetry-replay-lab/
├── backend/          FastAPI app, mock telemetry, archive, DTW matcher
├── frontend/         Static dashboard (Chart.js)
├── data/archives/    Saved mission JSON files
└── scripts/run.ps1   Windows launcher
```

## Next steps (full product)

- Replace mock generator with PySerial / LoRa gateway ingest
- Persist time-series in InfluxDB instead of JSON files
- Tauri desktop shell + React Native mobile companion
- Three.js trajectory view and Leaflet map overlay

Team Tempest — prototype scaffold for pitch/demo iteration.
