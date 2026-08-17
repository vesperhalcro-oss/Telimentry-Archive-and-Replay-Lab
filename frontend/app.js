const state = {
  mode: "live",
  ws: null,
  replayWs: null,
  missions: [],
  currentMission: null,
  currentSamples: [],
  matchedMission: null,
  matchedSamples: [],
  charts: {},
};

const maxPoints = 240;

function $(id) {
  return document.getElementById(id);
}

function chartOptions(label, color) {
  return {
    type: "line",
    data: {
      labels: [],
      datasets: [{ label, data: [], borderColor: color, tension: 0.25, pointRadius: 0 }],
    },
    options: {
      responsive: true,
      animation: false,
      scales: {
        x: { ticks: { color: "#9fb0d0" }, grid: { color: "#24304a" } },
        y: { ticks: { color: "#9fb0d0" }, grid: { color: "#24304a" } },
      },
      plugins: { legend: { labels: { color: "#e8eefc" } } },
    },
  };
}

function initCharts() {
  state.charts.altitude = new Chart($("altitude-chart"), chartOptions("Altitude (m)", "#4cc9f0"));
  state.charts.battery = new Chart($("battery-chart"), chartOptions("Battery (V)", "#6bff95"));
  state.charts.dualLeft = new Chart($("dual-left-chart"), chartOptions("Primary altitude", "#4cc9f0"));
  state.charts.dualRight = new Chart($("dual-right-chart"), chartOptions("Matched altitude", "#f72585"));
}

function pushChart(chart, t, value) {
  chart.data.labels.push(t.toFixed(1));
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > maxPoints) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update("none");
}

function setMetrics(sample, statusText) {
  $("m-time").textContent = `${sample.t.toFixed(1)} s`;
  $("m-alt").textContent = `${sample.altitude_m.toFixed(1)} m`;
  $("m-batt").textContent = `${sample.battery_v.toFixed(2)} V`;
  $("m-speed").textContent = `${sample.speed_mps.toFixed(1)} m/s`;
  $("m-pitch").textContent = `${sample.pitch_deg.toFixed(1)}°`;
  $("m-roll").textContent = `${sample.roll_deg.toFixed(1)}°`;
  $("m-yaw").textContent = `${sample.yaw_deg.toFixed(1)}°`;
  const status = $("m-status");
  status.textContent = statusText;
  status.className = sample.anomaly ? "anomaly" : "ok";
}

function handleSample(sample, statusText) {
  setMetrics(sample, statusText);
  pushChart(state.charts.altitude, sample.t, sample.altitude_m);
  pushChart(state.charts.battery, sample.t, sample.battery_v);
  state.currentSamples.push(sample);
  if (state.currentSamples.length > 2000) state.currentSamples.shift();
}

function disconnectWs() {
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  if (state.replayWs) {
    state.replayWs.close();
    state.replayWs = null;
  }
}

function connectLive() {
  disconnectWs();
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${protocol}://${location.host}/ws/live`);
  state.ws.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    handleSample(payload.sample, payload.sample.anomaly ? "ANOMALY" : "LIVE");
  };
}

async function loadMissions() {
  const res = await fetch("/api/missions");
  state.missions = await res.json();
  const select = $("mission-select");
  select.innerHTML = "";
  for (const mission of state.missions) {
    const option = document.createElement("option");
    option.value = mission.id;
    option.textContent = `${mission.name} (${mission.rocket})`;
    select.appendChild(option);
  }
}

async function startReplay() {
  disconnectWs();
  const missionId = $("mission-select").value;
  const speed = $("replay-speed").value;
  const detail = await (await fetch(`/api/missions/${missionId}`)).json();
  state.currentMission = detail;
  state.currentSamples = detail.samples.slice();

  $("scrubber").max = Math.max(0, detail.samples.length - 1);
  $("scrubber").value = 0;

  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.replayWs = new WebSocket(`${protocol}://${location.host}/ws/replay/${missionId}?speed=${speed}`);
  state.replayWs.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    $("scrubber").value = payload.index;
    handleSample(payload.sample, `REPLAY ${payload.index + 1}/${payload.total}`);
  };
}

function scrubTo(index) {
  if (!state.currentMission) return;
  const sample = state.currentMission.samples[index];
  if (!sample) return;
  setMetrics(sample, `SCRUB ${Number(index) + 1}/${state.currentMission.samples.length}`);
}

async function runMatchSearch() {
  if (state.currentSamples.length < 10) {
    alert("Need more telemetry samples first.");
    return;
  }
  const res = await fetch("/api/match/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ samples: state.currentSamples.slice(-400) }),
  });
  const results = await res.json();
  const list = $("match-results");
  list.innerHTML = "";
  for (const item of results) {
    const li = document.createElement("li");
    li.textContent = item.summary;
    li.dataset.missionId = item.mission_id;
    li.style.cursor = "pointer";
    li.onclick = () => selectMatchedMission(item);
    list.appendChild(li);
  }
}

async function selectMatchedMission(item) {
  const detail = await (await fetch(`/api/missions/${item.mission_id}`)).json();
  state.matchedMission = detail;
  state.matchedSamples = detail.samples;
  $("dual-right-title").textContent = detail.name;
}

async function showDualPlayback() {
  $("dual-panel").classList.remove("hidden");
  $("dual-left-title").textContent = state.mode === "live" ? "Live / Primary" : state.currentMission?.name || "Primary";

  const leftSeries = state.currentSamples.map((s) => s.altitude_m);
  const rightSeries = (state.matchedSamples.length ? state.matchedSamples : state.currentSamples).map((s) => s.altitude_m);

  fillStaticChart(state.charts.dualLeft, leftSeries, "#4cc9f0");
  fillStaticChart(state.charts.dualRight, rightSeries, "#f72585");
}

function fillStaticChart(chart, series, color) {
  chart.data.labels = series.map((_, i) => i);
  chart.data.datasets[0].data = series;
  chart.data.datasets[0].borderColor = color;
  chart.update("none");
}

function setMode(mode) {
  state.mode = mode;
  $("mode-live").classList.toggle("active", mode === "live");
  $("mode-replay").classList.toggle("active", mode === "replay");
  $("live-controls").classList.toggle("hidden", mode !== "live");
  $("replay-controls").classList.toggle("hidden", mode !== "replay");
  disconnectWs();
  if (mode === "live") connectLive();
}

function bindUi() {
  $("mode-live").onclick = () => setMode("live");
  $("mode-replay").onclick = () => setMode("replay");
  $("reset-live").onclick = async () => {
    await fetch("/api/live/reset", { method: "POST" });
    state.currentSamples = [];
    state.charts.altitude.data.labels = [];
    state.charts.altitude.data.datasets[0].data = [];
    state.charts.battery.data.labels = [];
    state.charts.battery.data.datasets[0].data = [];
    state.charts.altitude.update();
    state.charts.battery.update();
    connectLive();
  };
  $("bookmark").onclick = async () => {
    await fetch("/api/live/bookmark?label=Manual", { method: "POST" });
  };
  $("archive-live").onclick = async () => {
    const name = prompt("Mission name", "Campus Launch");
    if (!name) return;
    const res = await fetch("/api/archive/live", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, rocket: "Tempest-1" }),
    });
    const mission = await res.json();
    alert(`Archived ${mission.id}`);
    await loadMissions();
  };
  $("replay-speed").oninput = (e) => {
    $("speed-label").textContent = `${Number(e.target.value).toFixed(1)}x`;
  };
  $("start-replay").onclick = startReplay;
  $("stop-replay").onclick = disconnectWs;
  $("scrubber").oninput = (e) => scrubTo(e.target.value);
  $("match-search").onclick = runMatchSearch;
  $("dual-playback").onclick = showDualPlayback;
  $("dual-scrubber").oninput = (e) => {
    const pct = Number(e.target.value) / 100;
    const leftIdx = Math.floor((state.currentSamples.length - 1) * pct);
    const rightIdx = Math.floor((state.matchedSamples.length - 1) * pct);
    if (state.currentSamples[leftIdx]) setMetrics(state.currentSamples[leftIdx], "DUAL PRIMARY");
  };
}

async function boot() {
  initCharts();
  bindUi();
  await loadMissions();
  setMode("live");
}

boot();
