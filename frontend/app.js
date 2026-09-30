/*
 * app.js
 * ------
 * Vanilla JS controller for the AI Vehicle Detection & Counting dashboard.
 * Talks to the FastAPI backend via the Fetch API and polls /stats for
 * live updates. The processed video is streamed via MJPEG (<img src="/video">),
 * which is the most reliable real-time streaming mechanism for a local
 * Windows laptop (no extra client-side decoding required).
 */

const API_BASE = ""; // same origin, served by FastAPI

const els = {
  videoFeed: document.getElementById("videoFeed"),
  videoPlaceholder: document.getElementById("videoPlaceholder"),
  errorBanner: document.getElementById("errorBanner"),

  statTotal: document.getElementById("statTotal"),
  statCars: document.getElementById("statCars"),
  statMotorcycles: document.getElementById("statMotorcycles"),
  statBuses: document.getElementById("statBuses"),
  statTrucks: document.getElementById("statTrucks"),
  statFps: document.getElementById("statFps"),
  statActive: document.getElementById("statActive"),

  statusPill: document.getElementById("statusPill"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),

  sysDevice: document.getElementById("sysDevice"),
  sysProcessing: document.getElementById("sysProcessing"),

  sourceRadios: document.querySelectorAll('input[name="source"]'),
  videoFile: document.getElementById("videoFile"),

  btnStart: document.getElementById("btnStart"),
  btnStop: document.getElementById("btnStop"),
  btnReset: document.getElementById("btnReset"),
  btnClear: document.getElementById("btnClear"),
  btnExport: document.getElementById("btnExport"),

  direction: document.getElementById("direction"),
  confidence: document.getElementById("confidence"),
  confidenceVal: document.getElementById("confidenceVal"),
  linePosition: document.getElementById("linePosition"),
  lineVal: document.getElementById("lineVal"),

  detectionsBody: document.getElementById("detectionsBody"),
  distChart: document.getElementById("distChart"),
  flowChart: document.getElementById("flowChart"),
};

let pollTimer = null;
let uploadedOk = false;
let isRunning = false;

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------
function showError(msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove("hidden");
}
function clearError() {
  els.errorBanner.classList.add("hidden");
  els.errorBanner.textContent = "";
}

function currentSourceMode() {
  const checked = document.querySelector('input[name="source"]:checked');
  return checked ? checked.value : "webcam";
}

function setUIRunning(running) {
  isRunning = running;
  els.btnStart.disabled = running;
  els.btnStop.disabled = !running;
  els.videoFeed.style.display = running ? "block" : "none";
  els.videoPlaceholder.style.display = running ? "none" : "flex";
  els.sysProcessing.textContent = running ? "Running" : "Stopped";
  els.statusText.textContent = running ? "Processing" : "System Online";
  els.statusDot.classList.toggle("offline", false);
}

// ---------------------------------------------------------------------
// Source selection
// ---------------------------------------------------------------------
els.sourceRadios.forEach((radio) => {
  radio.addEventListener("change", () => {
    const mode = currentSourceMode();
    els.videoFile.disabled = mode !== "upload";
  });
});

els.videoFile.addEventListener("change", async () => {
  const file = els.videoFile.files[0];
  if (!file) return;
  clearError();

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    uploadedOk = true;
  } catch (err) {
    uploadedOk = false;
    showError(err.message);
  }
});

// ---------------------------------------------------------------------
// Controls: sliders
// ---------------------------------------------------------------------
els.confidence.addEventListener("input", () => {
  els.confidenceVal.textContent = parseFloat(els.confidence.value).toFixed(2);
});
els.linePosition.addEventListener("input", () => {
  els.lineVal.textContent = `${els.linePosition.value}%`;
});

async function pushConfig() {
  const params = new URLSearchParams({
    confidence: els.confidence.value,
    line_position: (parseFloat(els.linePosition.value) / 100).toFixed(2),
    direction: els.direction.value,
  });
  try {
    await fetch(`${API_BASE}/configure?${params.toString()}`, { method: "POST" });
  } catch (err) {
    // Non-fatal; configuration will just apply on next /start
  }
}
els.confidence.addEventListener("change", pushConfig);
els.linePosition.addEventListener("change", pushConfig);
els.direction.addEventListener("change", pushConfig);

// ---------------------------------------------------------------------
// Start / Stop / Reset / Clear / Export
// ---------------------------------------------------------------------
els.btnStart.addEventListener("click", async () => {
  clearError();
  const mode = currentSourceMode();

  if (mode === "upload" && !uploadedOk) {
    showError("Please upload a video file first.");
    return;
  }

  const params = new URLSearchParams({
    mode,
    confidence: els.confidence.value,
    line_position: (parseFloat(els.linePosition.value) / 100).toFixed(2),
    direction: els.direction.value,
  });

  try {
    const res = await fetch(`${API_BASE}/start?${params.toString()}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start");

    els.sysDevice.textContent = (data.device || "cpu").toUpperCase();
    els.videoFeed.src = `${API_BASE}/video?ts=${Date.now()}`;
    setUIRunning(true);
    startPolling();
  } catch (err) {
    showError(err.message);
  }
});

els.btnStop.addEventListener("click", async () => {
  try {
    await fetch(`${API_BASE}/stop`, { method: "POST" });
  } finally {
    setUIRunning(false);
    els.videoFeed.removeAttribute("src");
    stopPolling();
  }
});

els.btnReset.addEventListener("click", async () => {
  await fetch(`${API_BASE}/reset`, { method: "POST" });
  refreshStats();
});

els.btnClear.addEventListener("click", () => {
  els.detectionsBody.innerHTML = "";
});

els.btnExport.addEventListener("click", () => {
  window.location.href = `${API_BASE}/export`;
});

// ---------------------------------------------------------------------
// Polling stats
// ---------------------------------------------------------------------
function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(refreshStats, 500);
}
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  refreshStats();
}

async function refreshStats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    const data = await res.json();
    updateDashboard(data);
  } catch (err) {
    // Backend might be briefly unavailable; ignore transient failures
  }
}

function updateDashboard(data) {
  els.statTotal.textContent = data.total ?? 0;
  els.statCars.textContent = data.cars ?? 0;
  els.statMotorcycles.textContent = data.motorcycles ?? 0;
  els.statBuses.textContent = data.buses ?? 0;
  els.statTrucks.textContent = data.trucks ?? 0;
  els.statFps.textContent = `${(data.fps ?? 0).toFixed ? data.fps.toFixed(1) : data.fps} FPS`;
  els.statActive.textContent = data.active_tracks ?? 0;

  if (data.device) els.sysDevice.textContent = data.device.toUpperCase();

  if (data.error) {
    showError(data.error);
  }

  if (data.status === "stopped" && isRunning) {
    // Backend stopped on its own (e.g. end of video, webcam error)
    setUIRunning(false);
    stopPolling();
  }

  renderTable(data.recent_detections || []);
  renderDistributionChart(data);
  renderFlowChart(data.flow_series || []);
}

// ---------------------------------------------------------------------
// Recent detections table
// ---------------------------------------------------------------------
function renderTable(entries) {
  const rows = entries.slice().reverse().map((e) => {
    const cls = `badge-${e.vehicle_type}`;
    return `<tr>
      <td>${e.time}</td>
      <td>${e.track_id}</td>
      <td class="${cls}">${capitalize(e.vehicle_type)}</td>
      <td>${e.confidence}%</td>
      <td>${e.direction}</td>
    </tr>`;
  });
  els.detectionsBody.innerHTML = rows.join("");
}
function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ---------------------------------------------------------------------
// Charts (plain canvas, no external library needed)
// ---------------------------------------------------------------------
function renderDistributionChart(data) {
  const ctx = els.distChart.getContext("2d");
  const w = els.distChart.width, h = els.distChart.height;
  ctx.clearRect(0, 0, w, h);

  const items = [
    { label: "Cars", value: data.cars ?? 0, color: "#ffb648" },
    { label: "Motorcycles", value: data.motorcycles ?? 0, color: "#4ce0d2" },
    { label: "Buses", value: data.buses ?? 0, color: "#56d97a" },
    { label: "Trucks", value: data.trucks ?? 0, color: "#ff6b6b" },
  ];
  const maxVal = Math.max(1, ...items.map((i) => i.value));
  const barHeight = 26;
  const gap = 16;
  const startY = 20;
  const chartWidth = w - 110;

  ctx.font = "12px 'Space Grotesk', sans-serif";
  items.forEach((item, idx) => {
    const y = startY + idx * (barHeight + gap);
    const barW = (item.value / maxVal) * chartWidth;

    ctx.fillStyle = "#9aa8c4";
    ctx.fillText(item.label, 0, y + barHeight / 2 + 4);

    ctx.fillStyle = "#182742";
    ctx.fillRect(90, y, chartWidth, barHeight);

    ctx.fillStyle = item.color;
    ctx.fillRect(90, y, Math.max(2, barW), barHeight);

    ctx.fillStyle = "#e9edf5";
    ctx.fillText(String(item.value), 90 + chartWidth + 8, y + barHeight / 2 + 4);
  });
}

function renderFlowChart(series) {
  const ctx = els.flowChart.getContext("2d");
  const w = els.flowChart.width, h = els.flowChart.height;
  ctx.clearRect(0, 0, w, h);

  if (!series || series.length === 0) {
    ctx.fillStyle = "#5c6a8a";
    ctx.font = "12px 'Space Grotesk', sans-serif";
    ctx.fillText("Waiting for data...", 10, h / 2);
    return;
  }

  const padding = 28;
  const maxCount = Math.max(1, ...series.map((p) => p.count));
  const stepX = (w - padding * 2) / Math.max(1, series.length - 1);

  // Axes
  ctx.strokeStyle = "#23324f";
  ctx.beginPath();
  ctx.moveTo(padding, h - padding);
  ctx.lineTo(w - padding, h - padding);
  ctx.stroke();

  // Line
  ctx.strokeStyle = "#4ce0d2";
  ctx.lineWidth = 2;
  ctx.beginPath();
  series.forEach((point, idx) => {
    const x = padding + idx * stepX;
    const y = h - padding - (point.count / maxCount) * (h - padding * 2);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Points
  ctx.fillStyle = "#4ce0d2";
  series.forEach((point, idx) => {
    const x = padding + idx * stepX;
    const y = h - padding - (point.count / maxCount) * (h - padding * 2);
    ctx.beginPath();
    ctx.arc(x, y, 2.5, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.fillStyle = "#9aa8c4";
  ctx.font = "11px 'Space Grotesk', sans-serif";
  ctx.fillText(`max: ${maxCount}`, padding, 14);
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
(function init() {
  setUIRunning(false);
  refreshStats();
  // Light idle polling even when stopped, so cards reflect last-known state
  setInterval(() => {
    if (!isRunning) refreshStats();
  }, 3000);
})();
