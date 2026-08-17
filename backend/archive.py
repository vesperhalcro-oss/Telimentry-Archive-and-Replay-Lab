from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.telemetry import MockFlightProfile, TelemetrySample

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "archives"


def _mission_path(mission_id: str) -> Path:
    return DATA_DIR / f"{mission_id}.json"


def list_missions() -> list[dict[str, Any]]:
    missions: list[dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        missions.append(
            {
                "id": payload["id"],
                "name": payload["name"],
                "rocket": payload.get("rocket", "Unknown"),
                "date": payload.get("date"),
                "sample_count": len(payload.get("samples", [])),
                "duration_s": payload.get("duration_s", 0),
                "has_anomaly": payload.get("has_anomaly", False),
            }
        )
    return missions


def save_mission(name: str, rocket: str, samples: list[TelemetrySample], seed: int | None = None) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    mission_id = datetime.now(timezone.utc).strftime("mission-%Y%m%d-%H%M%S-%f")
    payload = {
        "id": mission_id,
        "name": name,
        "rocket": rocket,
        "date": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "duration_s": samples[-1].t if samples else 0,
        "has_anomaly": any(s.anomaly for s in samples),
        "samples": [s.to_dict() for s in samples],
    }
    with _mission_path(mission_id).open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return payload


def load_mission(mission_id: str) -> dict[str, Any]:
    path = _mission_path(mission_id)
    if not path.exists():
        raise FileNotFoundError(f"Mission not found: {mission_id}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def seed_demo_missions() -> list[str]:
    """Create a few archived missions for replay and match search demos."""
    if list_missions():
        return [m["id"] for m in list_missions()]

    created: list[str] = []
    presets = [
        ("Campus Launch Alpha", "Tempest-1", 101),
        ("Night Test Bravo", "Tempest-1", 202),
        ("Parachute Delay Drill", "Tempest-2", 303),
        ("Recovery Validation", "Tempest-2", 404),
    ]
    for name, rocket, seed in presets:
        profile = MockFlightProfile(seed=seed, duration_s=120)
        samples = profile.generate_series(hz=10)
        mission = save_mission(name, rocket, samples, seed=seed)
        created.append(mission["id"])
    return created
