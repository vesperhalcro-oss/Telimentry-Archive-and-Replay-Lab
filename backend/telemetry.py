from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TelemetrySample:
    t: float
    altitude_m: float
    battery_v: float
    pitch_deg: float
    roll_deg: float
    yaw_deg: float
    lat: float
    lon: float
    speed_mps: float
    anomaly: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MockFlightProfile:
    """Generates a plausible rocket flight curve for live or archived missions."""

    def __init__(self, seed: int | None = None, duration_s: float = 120.0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.duration_s = duration_s
        self.launch_lat = 28.6139 + self.rng.uniform(-0.05, 0.05)
        self.launch_lon = 77.2090 + self.rng.uniform(-0.05, 0.05)
        self.parachute_delay = self.rng.uniform(55, 75)
        self.peak_altitude = self.rng.uniform(900, 1400)
        self.anomaly_at = self.parachute_delay + self.rng.uniform(3, 8) if self.rng.random() < 0.35 else None

    def sample_at(self, elapsed_s: float) -> TelemetrySample:
        t = max(0.0, min(elapsed_s, self.duration_s))
        phase = t / self.duration_s

        if t < 2:
            altitude = 5 * t
            speed = 8 + 20 * t
        elif t < self.parachute_delay:
            ascent = (t - 2) / max(self.parachute_delay - 2, 1)
            altitude = 10 + self.peak_altitude * math.sin(ascent * math.pi / 2)
            speed = 40 + 80 * (1 - ascent)
        else:
            descent = (t - self.parachute_delay) / max(self.duration_s - self.parachute_delay, 1)
            altitude = max(0.0, self.peak_altitude * (1 - descent**1.4))
            speed = max(2.0, 18 * (1 - descent))

        battery = max(3.3, 4.2 - phase * 0.7 - self.rng.uniform(0, 0.02))
        wobble = math.sin(t * 2.3) * 4
        pitch = wobble + self.rng.uniform(-1.5, 1.5)
        roll = math.cos(t * 1.7) * 3 + self.rng.uniform(-1, 1)
        yaw = (t * 8 + self.rng.uniform(-2, 2)) % 360

        lat = self.launch_lat + math.sin(t / 30) * 0.002 + t * 0.00001
        lon = self.launch_lon + math.cos(t / 25) * 0.002 + t * 0.00001

        anomaly = bool(self.anomaly_at and abs(t - self.anomaly_at) < 0.5)
        if anomaly:
            altitude *= 0.92
            pitch += self.rng.uniform(8, 15)

        return TelemetrySample(
            t=round(t, 3),
            altitude_m=round(altitude, 2),
            battery_v=round(battery, 3),
            pitch_deg=round(pitch, 2),
            roll_deg=round(roll, 2),
            yaw_deg=round(yaw, 2),
            lat=round(lat, 6),
            lon=round(lon, 6),
            speed_mps=round(speed, 2),
            anomaly=anomaly,
        )

    def generate_series(self, hz: float = 10.0) -> list[TelemetrySample]:
        step = 1.0 / hz
        samples: list[TelemetrySample] = []
        t = 0.0
        while t <= self.duration_s:
            samples.append(self.sample_at(t))
            t += step
        return samples


class LiveTelemetryStream:
    def __init__(self, hz: float = 10.0):
        self.hz = hz
        self.profile = MockFlightProfile(seed=int(time.time()))
        self.started_at = time.time()
        self.bookmarks: list[dict[str, Any]] = []

    def reset(self, seed: int | None = None) -> None:
        self.profile = MockFlightProfile(seed=seed or int(time.time()))
        self.started_at = time.time()
        self.bookmarks.clear()

    def current_sample(self) -> TelemetrySample:
        elapsed = time.time() - self.started_at
        return self.profile.sample_at(elapsed)

    def add_bookmark(self, label: str) -> dict[str, Any]:
        sample = self.current_sample()
        bookmark = {"label": label, "t": sample.t, "sample": sample.to_dict()}
        self.bookmarks.append(bookmark)
        return bookmark
