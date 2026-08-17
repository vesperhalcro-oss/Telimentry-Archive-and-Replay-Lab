from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.archive import list_missions, load_mission, save_mission, seed_demo_missions
from backend.match_engine import find_similar_missions
from backend.telemetry import LiveTelemetryStream, MockFlightProfile

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Telemetry Archive & Replay Lab", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

live_stream = LiveTelemetryStream(hz=10)
seed_demo_missions()


class ArchiveRequest(BaseModel):
    name: str = Field(min_length=1)
    rocket: str = Field(default="Tempest-1")


class MatchRequest(BaseModel):
    samples: list[dict[str, Any]]
    exclude_id: str | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "platform": "windows-prototype"}


@app.get("/api/missions")
def missions() -> list[dict[str, Any]]:
    return list_missions()


@app.get("/api/missions/{mission_id}")
def mission_detail(mission_id: str) -> dict[str, Any]:
    try:
        return load_mission(mission_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/live/reset")
def reset_live(seed: int | None = None) -> dict[str, Any]:
    live_stream.reset(seed=seed)
    return {"status": "reset", "seed": seed}


@app.get("/api/live/sample")
def live_sample() -> dict[str, Any]:
    sample = live_stream.current_sample()
    return sample.to_dict()


@app.post("/api/live/bookmark")
def add_bookmark(label: str = "Event") -> dict[str, Any]:
    return live_stream.add_bookmark(label)


@app.post("/api/archive/live")
def archive_live(payload: ArchiveRequest) -> dict[str, Any]:
    elapsed = live_stream.current_sample().t
    profile = live_stream.profile
    samples = [profile.sample_at(t) for t in [i / 10 for i in range(int(elapsed * 10) + 1)]]
    mission = save_mission(payload.name, payload.rocket, samples, seed=profile.seed)
    return mission


@app.post("/api/match/search")
def search_similar(payload: MatchRequest) -> list[dict[str, Any]]:
    if not payload.samples:
        raise HTTPException(status_code=400, detail="samples required")
    return find_similar_missions(payload.samples, exclude_id=payload.exclude_id)


@app.post("/api/demo/seed")
def seed_demo() -> dict[str, Any]:
    ids = seed_demo_missions()
    return {"created": ids, "count": len(ids)}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            sample = live_stream.current_sample()
            await websocket.send_json(
                {
                    "type": "telemetry",
                    "mode": "live",
                    "sample": sample.to_dict(),
                    "bookmarks": live_stream.bookmarks,
                }
            )
            await asyncio.sleep(1 / live_stream.hz)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/replay/{mission_id}")
async def websocket_replay(websocket: WebSocket, mission_id: str, speed: float = 1.0) -> None:
    await websocket.accept()
    try:
        mission = load_mission(mission_id)
    except FileNotFoundError:
        await websocket.close(code=4404)
        return

    samples = mission.get("samples", [])
    if not samples:
        await websocket.close(code=4400)
        return

    speed = max(0.5, min(speed, 10.0))
    idx = 0
    try:
        while idx < len(samples):
            await websocket.send_json(
                {
                    "type": "telemetry",
                    "mode": "replay",
                    "mission_id": mission_id,
                    "sample": samples[idx],
                    "index": idx,
                    "total": len(samples),
                }
            )
            idx += 1
            dt = 0.1 / speed
            if idx < len(samples):
                next_t = samples[idx]["t"] - samples[idx - 1]["t"]
                dt = max(0.02, next_t / speed)
            await asyncio.sleep(dt)
    except WebSocketDisconnect:
        return


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")
