const $ = (id) => document.getElementById(id);
let ws = null;
let audioCtx = null;
let nextPlayTime = 0;
let currentFreqs = [];
let running = false;
let digitalActive = false;
const AUDIO_RATE = 48000;

// --- Spectrum & Waterfall ---

const specCanvas = $("spectrum");
const wfCanvas = $("waterfall");
let specCtx, wfCtx;

// Zoom/pan state
let zoomLevel = 1;    // 1 = full span, 16 = max zoom
let panCenter = 0.5;  // 0-1, center of visible window in FFT
let isDragging = false;
let dragStartX = 0;
let dragStartPan = 0;

function initCanvases() {
    const dpr = window.devicePixelRatio || 1;
    for (const c of [specCanvas, wfCanvas]) {
        const rect = c.getBoundingClientRect();
        c.width = rect.width * dpr;
        c.height = rect.height * dpr;
    }
    specCtx = specCanvas.getContext("2d");
    wfCtx = wfCanvas.getContext("2d");
    specCtx.scale(dpr, dpr);
    wfCtx.scale(dpr, dpr);
}

const SPEC_LEFT = 48;
const SPEC_BOTTOM = 24;
const SPEC_TOP = 8;

function visibleSlice(arr) {
    if (zoomLevel <= 1) return arr;
    const half = (1 / zoomLevel) / 2;
    const start = Math.max(0, Math.floor((panCenter - half) * arr.length));
    const end = Math.min(arr.length, Math.ceil((panCenter + half) * arr.length));
    return arr.slice(start, end);
}

// Bandwidth per mode in kHz (for filter overlay)
const MODE_BANDWIDTHS = { wfm: 200, fm: 200, nfm: 12.5, am: 25 };

function drawSpectrum(freqs, power, centerFreq) {
    // Apply zoom/pan: slice to visible window
    const visFreqs = visibleSlice(freqs);
    const visPower = visibleSlice(power);

    const w = specCanvas.getBoundingClientRect().width;
    const h = specCanvas.getBoundingClientRect().height;
    const ctx = specCtx;
    const plotW = w - SPEC_LEFT;
    const plotH = h - SPEC_BOTTOM - SPEC_TOP;

    // Clear
    ctx.fillStyle = "#060a0f";
    ctx.fillRect(0, 0, w, h);

    const minP = Math.min(...visPower);
    const maxP = Math.max(...visPower);
    const dbMin = Math.floor(minP / 10) * 10;
    const dbMax = Math.ceil(maxP / 10) * 10;
    const dbRange = dbMax - dbMin || 10;
    const dbStep = dbRange <= 30 ? 5 : 10;

    // Horizontal dB gridlines
    ctx.strokeStyle = "rgba(48, 54, 61, 0.6)";
    ctx.lineWidth = 0.5;
    ctx.fillStyle = "#484f58";
    ctx.font = "10px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "right";
    for (let db = dbMin; db <= dbMax; db += dbStep) {
        const y = SPEC_TOP + plotH - ((db - dbMin) / dbRange) * plotH;
        ctx.beginPath();
        ctx.moveTo(SPEC_LEFT, y);
        ctx.lineTo(w, y);
        ctx.stroke();
        ctx.fillText(db + " dB", SPEC_LEFT - 6, y + 3);
    }

    // Vertical frequency ticks
    const freqStart = visFreqs[0];
    const freqEnd = visFreqs[visFreqs.length - 1];
    const freqSpan = freqEnd - freqStart;

    let tickMhz = 0.5;
    if (freqSpan < 0.05) tickMhz = 0.005;
    else if (freqSpan < 0.1) tickMhz = 0.01;
    else if (freqSpan < 0.5) tickMhz = 0.05;
    else if (freqSpan < 1) tickMhz = 0.1;
    else if (freqSpan < 3) tickMhz = 0.25;
    else if (freqSpan > 10) tickMhz = 1.0;

    ctx.textAlign = "center";
    ctx.fillStyle = "#484f58";
    const firstTick = Math.ceil(freqStart / tickMhz) * tickMhz;
    for (let f = firstTick; f <= freqEnd; f += tickMhz) {
        const x = SPEC_LEFT + ((f - freqStart) / freqSpan) * plotW;
        ctx.beginPath();
        ctx.moveTo(x, SPEC_TOP);
        ctx.lineTo(x, SPEC_TOP + plotH);
        ctx.stroke();
        const decimals = tickMhz < 0.01 ? 4 : tickMhz < 0.1 ? 3 : 2;
        ctx.fillText(f.toFixed(decimals), x, h - 6);
    }

    // Center frequency marker
    if (centerFreq >= freqStart && centerFreq <= freqEnd) {
        const centerX = SPEC_LEFT + ((centerFreq - freqStart) / freqSpan) * plotW;
        ctx.strokeStyle = "rgba(255, 80, 80, 0.5)";
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(centerX, SPEC_TOP);
        ctx.lineTo(centerX, SPEC_TOP + plotH);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    // Bandwidth filter overlay
    const tunedFreq = parseFloat($("freqInput").value);
    const currentMode = document.querySelector(".mode-btn.active")?.dataset.mode || "wfm";
    const bwKhz = MODE_BANDWIDTHS[currentMode] || 25;
    const bwMhz = bwKhz / 1000;
    const filterLeft = SPEC_LEFT + ((tunedFreq - bwMhz / 2 - freqStart) / freqSpan) * plotW;
    const filterRight = SPEC_LEFT + ((tunedFreq + bwMhz / 2 - freqStart) / freqSpan) * plotW;
    const filterW = filterRight - filterLeft;
    if (filterRight > SPEC_LEFT && filterLeft < w) {
        ctx.fillStyle = "rgba(88, 166, 255, 0.12)";
        ctx.fillRect(Math.max(SPEC_LEFT, filterLeft), SPEC_TOP, Math.min(filterW, plotW), plotH);
        ctx.strokeStyle = "rgba(88, 166, 255, 0.4)";
        ctx.lineWidth = 1;
        ctx.strokeRect(Math.max(SPEC_LEFT, filterLeft), SPEC_TOP, Math.min(filterW, plotW), plotH);
    }

    // Spectrum line
    ctx.strokeStyle = "#00d4aa";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < visPower.length; i++) {
        const x = SPEC_LEFT + (i / visPower.length) * plotW;
        const y = SPEC_TOP + plotH - ((visPower[i] - dbMin) / dbRange) * plotH;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Gradient fill under curve
    ctx.lineTo(SPEC_LEFT + plotW, SPEC_TOP + plotH);
    ctx.lineTo(SPEC_LEFT, SPEC_TOP + plotH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, SPEC_TOP, 0, SPEC_TOP + plotH);
    grad.addColorStop(0, "rgba(0, 212, 170, 0.15)");
    grad.addColorStop(1, "rgba(0, 212, 170, 0.01)");
    ctx.fillStyle = grad;
    ctx.fill();

    // Bookmark markers
    drawBookmarks(ctx, visFreqs, freqStart, freqEnd, freqSpan, plotW, plotH, h);

    // Zoom indicator
    if (zoomLevel > 1) {
        ctx.fillStyle = "#8b949e";
        ctx.font = "10px -apple-system, BlinkMacSystemFont, sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(zoomLevel.toFixed(1) + "x", w - 8, SPEC_TOP + 12);
    }

    ctx.textAlign = "left";
}

// Pre-computed 256-entry color LUT for waterfall (black→navy→cyan→green→yellow→red)
const COLOR_LUT = new Uint8Array(256 * 3);
(function buildColorLUT() {
    const stops = [
        [0, 0, 0, 0],
        [0.15, 0, 0, 120],
        [0.3, 0, 180, 255],
        [0.5, 0, 255, 80],
        [0.75, 255, 255, 0],
        [1.0, 255, 0, 0],
    ];
    for (let i = 0; i < 256; i++) {
        const v = i / 255;
        let si = 0;
        while (si < stops.length - 2 && v > stops[si + 1][0]) si++;
        const [p0, r0, g0, b0] = stops[si];
        const [p1, r1, g1, b1] = stops[si + 1];
        const t = (v - p0) / (p1 - p0);
        COLOR_LUT[i * 3] = r0 + (r1 - r0) * t;
        COLOR_LUT[i * 3 + 1] = g0 + (g1 - g0) * t;
        COLOR_LUT[i * 3 + 2] = b0 + (b1 - b0) * t;
    }
})();

// Auto-leveling: exponentially smoothed min/max for waterfall
let wfMin = -50, wfMax = 0;
const WF_ALPHA = 0.05;

// Bands data for bookmark markers (populated by loadBands)
let bandsData = {};

function drawWaterfall(power) {
    const w = wfCanvas.width;
    const h = wfCanvas.height;
    const ctx = wfCtx;

    // Shift down 1 pixel (in canvas coordinates)
    if (h > 1) {
        const img = ctx.getImageData(0, 0, w, h - 1);
        ctx.putImageData(img, 0, 1);
    }

    // Apply zoom/pan: slice power to visible window
    const vis = visibleSlice(power);

    // Auto-level with exponential smoothing
    const frameMin = Math.min(...vis);
    const frameMax = Math.max(...vis);
    wfMin += WF_ALPHA * (frameMin - wfMin);
    wfMax += WF_ALPHA * (frameMax - wfMax);
    const range = wfMax - wfMin || 1;

    const row = ctx.createImageData(w, 1);
    for (let i = 0; i < w; i++) {
        const idx = Math.floor((i / w) * vis.length);
        const norm = Math.max(0, Math.min(1, (vis[idx] - wfMin) / range));
        const ci = (norm * 255) | 0;
        row.data[i * 4] = COLOR_LUT[ci * 3];
        row.data[i * 4 + 1] = COLOR_LUT[ci * 3 + 1];
        row.data[i * 4 + 2] = COLOR_LUT[ci * 3 + 2];
        row.data[i * 4 + 3] = 255;
    }
    ctx.putImageData(row, 0, 0);
}

function drawBookmarks(ctx, visFreqs, freqStart, freqEnd, freqSpan, plotW, plotH, canvasH) {
    if (!Object.keys(bandsData).length) return;
    const tunedFreq = parseFloat($("freqInput").value);
    const y = SPEC_TOP + plotH; // bottom of plot area

    ctx.font = "9px 'SF Mono', 'Cascadia Code', monospace";
    ctx.textAlign = "center";

    for (const [name, info] of Object.entries(bandsData)) {
        const fMhz = info.frequency_mhz;
        if (fMhz < freqStart || fMhz > freqEnd) continue;

        const x = SPEC_LEFT + ((fMhz - freqStart) / freqSpan) * plotW;
        const isTuned = Math.abs(fMhz - tunedFreq) < 0.001;

        // Triangle marker
        ctx.fillStyle = isTuned ? "#58a6ff" : "rgba(0, 212, 170, 0.7)";
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x - 4, y + 8);
        ctx.lineTo(x + 4, y + 8);
        ctx.closePath();
        ctx.fill();

        // Vertical hairline
        ctx.strokeStyle = isTuned ? "rgba(88, 166, 255, 0.3)" : "rgba(0, 212, 170, 0.15)";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(x, SPEC_TOP);
        ctx.lineTo(x, y);
        ctx.stroke();
    }

    ctx.textAlign = "left";
}

// --- Audio ---

function initAudio() {
    if (audioCtx) audioCtx.close();
    audioCtx = new AudioContext({ sampleRate: AUDIO_RATE });
    nextPlayTime = audioCtx.currentTime;
}

function playAudio(arrayBuffer) {
    if (!audioCtx || audioCtx.state === "closed") return;

    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
    }

    const buffer = audioCtx.createBuffer(1, float32.length, AUDIO_RATE);
    buffer.getChannelData(0).set(float32);

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);

    const now = audioCtx.currentTime;
    if (nextPlayTime < now) nextPlayTime = now;
    source.start(nextPlayTime);
    nextPlayTime += buffer.duration;
}

// --- WebSocket ---

function connect() {
    if (ws && ws.readyState <= 1) ws.close();
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
        if (typeof event.data === "string") {
            const msg = JSON.parse(event.data);
            if (msg.type === "spectrum") {
                currentFreqs = msg.freqs;
                drawSpectrum(msg.freqs, msg.power, msg.center_freq);
                drawWaterfall(msg.power);
                updatePower(msg.peak_power);
            } else if (msg.type === "digital") {
                showDigitalOverlay(msg);
            }
        } else {
            playAudio(event.data);
        }
    };

    ws.onerror = (e) => {
        console.error("WebSocket error:", e);
    };

    ws.onclose = () => {
        console.log("WebSocket closed, running:", running, "digital:", digitalActive);
        if (running || digitalActive) {
            $("status").textContent = "Reconnecting...";
            $("status").dataset.state = "reconnecting";
            setTimeout(connect, 1500);
        }
    };
}

function updatePower(db) {
    const pct = Math.max(0, Math.min(100, ((db + 50) / 50) * 100));
    $("powerFill").style.width = pct + "%";
    $("powerText").textContent = db.toFixed(1) + " dB";
}

// --- Controls ---

async function toggleRadio() {
    if (running) {
        await stopRadio();
    } else {
        await startRadio();
    }
}

async function startRadio() {
    const freq = parseFloat($("freqInput").value);
    const mode = document.querySelector(".mode-btn.active").dataset.mode;
    const gain =
        $("gainSelect").value === "auto" ? "auto" : $("gainSlider").value;

    $("startBtn").disabled = true;
    $("status").textContent = "Starting...";
    $("status").dataset.state = "reconnecting";

    try {
        const resp = await fetch("/api/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ freq_mhz: freq, mode, gain }),
        });
        if (!resp.ok) throw new Error(`Start failed: ${resp.status}`);

        running = true;
        $("startBtn").textContent = "Stop";
        $("startBtn").classList.add("active");
        $("status").textContent = "Running";
        $("status").dataset.state = "running";
        initAudio();
        connect();
    } catch (e) {
        console.error("Start error:", e);
        $("status").textContent = "Error: " + e.message;
        $("status").dataset.state = "stopped";
    } finally {
        $("startBtn").disabled = false;
    }
}

async function stopRadio() {
    running = false;
    if (ws) ws.close();
    ws = null;
    if (audioCtx) {
        audioCtx.close();
        audioCtx = null;
    }
    await fetch("/api/stop", { method: "POST" });
    $("startBtn").textContent = "Start";
    $("startBtn").classList.remove("active");
    $("status").textContent = "Stopped";
    $("status").dataset.state = "stopped";
}

async function tuneToFreq(mhz) {
    $("freqInput").value = mhz.toFixed(3);
    if (window.updateFreqWidget) updateFreqWidget(mhz);
    await fetch("/api/tune", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ freq_mhz: mhz }),
    });
}

async function nudgeFreq(deltaMhz) {
    const current = parseFloat($("freqInput").value);
    await tuneToFreq(current + deltaMhz);
}

async function setMode(mode) {
    document
        .querySelectorAll(".mode-btn")
        .forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
    await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
    });
}

async function setGain(value) {
    $("gainValue").textContent = value + " dB";
    await fetch("/api/gain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gain: value }),
    });
}

function gainChanged() {
    const sel = $("gainSelect").value;
    const slider = $("gainSlider");
    if (sel === "auto") {
        slider.disabled = true;
        $("gainValue").textContent = "auto";
        fetch("/api/gain", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gain: "auto" }),
        });
    } else {
        slider.disabled = false;
        setGain(slider.value);
    }
}

// --- Click-to-tune, zoom, pan on spectrum and waterfall ---

function pixelToFreq(e, canvas) {
    if (!currentFreqs.length) return null;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    if (clickX < SPEC_LEFT) return null;
    const x = (clickX - SPEC_LEFT) / (rect.width - SPEC_LEFT);
    const vis = visibleSlice(currentFreqs);
    return vis[0] + x * (vis[vis.length - 1] - vis[0]);
}

function clickToTune(e, canvas) {
    if (isDragging) return; // don't tune on drag release
    const freq = pixelToFreq(e, canvas);
    if (freq !== null) tuneToFreq(freq);
}

// Zoom: mouse wheel
function handleZoom(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -1 : 1;
    const newZoom = Math.max(1, Math.min(16, zoomLevel * (1 + delta * 0.2)));

    // Zoom toward mouse position
    if (currentFreqs.length && newZoom > 1) {
        const rect = e.target.getBoundingClientRect();
        const mouseX = (e.clientX - rect.left - SPEC_LEFT) / (rect.width - SPEC_LEFT);
        const mouseRel = panCenter - (1 / zoomLevel) / 2 + mouseX * (1 / zoomLevel);
        panCenter = mouseRel;
    }

    zoomLevel = newZoom;
    if (zoomLevel <= 1) { panCenter = 0.5; zoomLevel = 1; }

    // Clamp pan so we don't go out of bounds
    const half = (1 / zoomLevel) / 2;
    panCenter = Math.max(half, Math.min(1 - half, panCenter));
}

// Pan: click-drag
let dragMoved = false;
function handleMouseDown(e) {
    if (e.button !== 0) return;
    const rect = e.target.getBoundingClientRect();
    if (e.clientX - rect.left < SPEC_LEFT) return;
    isDragging = true;
    dragMoved = false;
    dragStartX = e.clientX;
    dragStartPan = panCenter;
    e.target.style.cursor = "grabbing";
}

function handleMouseMove(e) {
    if (!isDragging || !currentFreqs.length) return;
    const rect = e.target.getBoundingClientRect();
    const dx = e.clientX - dragStartX;
    const pixelSpan = rect.width - SPEC_LEFT;
    const panDelta = -(dx / pixelSpan) * (1 / zoomLevel);
    panCenter = dragStartPan + panDelta;

    const half = (1 / zoomLevel) / 2;
    panCenter = Math.max(half, Math.min(1 - half, panCenter));

    if (Math.abs(dx) > 3) dragMoved = true;
}

function handleMouseUp(e) {
    if (!isDragging) return;
    e.target.style.cursor = "crosshair";
    isDragging = false;
    if (!dragMoved) clickToTune(e, e.target);
}

for (const canvas of [specCanvas, wfCanvas]) {
    canvas.addEventListener("wheel", handleZoom, { passive: false });
    canvas.addEventListener("mousedown", handleMouseDown);
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseup", handleMouseUp);
    canvas.addEventListener("mouseleave", (e) => {
        if (isDragging) { isDragging = false; canvas.style.cursor = "crosshair"; }
    });
}

// --- Phone Book ---

let phonebookData = [];
let phonebookFilter = "all";

const PHONEBOOK_GROUPS = {
    "Public Safety": ["carter_", "ems_", "sycamore_", "elizabethton_"],
    "State/Federal": ["tn_"],
    "Ham Repeaters": ["wr4cc_", "k4lns_", "km4hdm_", "ae2ey_", "w4ysf_", "ke4ccb_", "kc4ayx_"],
    "Weather": ["noaa_"],
    "Marine": ["marine_"],
    "Other": ["aprs_"],
};

const PROTOCOL_COLORS = {
    analog_nfm: "#3fb950",
    analog_am: "#3fb950",
    analog_wfm: "#3fb950",
    dmr: "#d29922",
    p25: "#58a6ff",
    nxdn: "#bc8cff",
    dstar: "#f778ba",
    ysf: "#f778ba",
    aprs: "#79c0ff",
    adsb: "#79c0ff",
    ism: "#79c0ff",
};

function protocolLabel(protocol) {
    const labels = {
        analog_nfm: "NFM", analog_am: "AM", analog_wfm: "WFM",
        dmr: "DMR", p25: "P25", nxdn: "NXDN", dstar: "D-STAR",
        ysf: "YSF", aprs: "APRS", adsb: "ADS-B", ism: "ISM",
    };
    return labels[protocol] || protocol;
}

async function loadPhonebook() {
    // Load phonebook entries
    const resp = await fetch("/api/phonebook");
    phonebookData = await resp.json();

    // Also load bands for spectrum bookmark markers
    const bandsResp = await fetch("/api/bands");
    bandsData = await bandsResp.json();

    renderPhonebook();

    // Wire up search
    $("phonebookSearch").addEventListener("input", renderPhonebook);
}

function filterPhonebook(filter) {
    phonebookFilter = filter;
    document.querySelectorAll(".filter-btn").forEach((b) =>
        b.classList.toggle("active", b.dataset.filter === filter)
    );
    renderPhonebook();
}

function renderPhonebook() {
    const container = $("phonebook");
    container.innerHTML = "";
    const query = ($("phonebookSearch")?.value || "").toLowerCase();

    // Filter entries
    let entries = phonebookData.filter((e) => {
        if (query && !e.name.toLowerCase().includes(query)
            && !e.description.toLowerCase().includes(query)
            && !String(e.frequency_mhz).includes(query)) {
            return false;
        }
        if (phonebookFilter === "analog" && !e.protocol.startsWith("analog")) return false;
        if (phonebookFilter === "digital" && e.protocol.startsWith("analog")) return false;
        return true;
    });

    // Group entries
    const grouped = {};
    const matched = new Set();

    for (const [groupName, prefixes] of Object.entries(PHONEBOOK_GROUPS)) {
        const group = entries.filter((e) =>
            prefixes.some((p) => e.name.startsWith(p))
        );
        if (group.length) {
            grouped[groupName] = group;
            group.forEach((e) => matched.add(e.name));
        }
    }

    // Catch unmatched
    const unmatched = entries.filter((e) => !matched.has(e.name));
    if (unmatched.length) {
        grouped["Other"] = [...(grouped["Other"] || []), ...unmatched];
    }

    if (!Object.keys(grouped).length) {
        container.innerHTML = '<div class="phonebook-empty">No matching frequencies</div>';
        return;
    }

    for (const [groupName, group] of Object.entries(grouped)) {
        const section = document.createElement("div");
        section.className = "phonebook-group";

        const label = document.createElement("span");
        label.className = "phonebook-group-label";
        label.textContent = groupName;
        section.appendChild(label);

        for (const entry of group) {
            const row = document.createElement("div");
            row.className = "phonebook-entry";
            row.onclick = () => smartTune(entry.frequency_mhz);

            const freq = document.createElement("span");
            freq.className = "phonebook-freq";
            freq.textContent = entry.frequency_mhz.toFixed(4);

            const desc = document.createElement("span");
            desc.className = "phonebook-desc";
            desc.textContent = entry.description;

            const badge = document.createElement("span");
            badge.className = "protocol-badge";
            badge.textContent = protocolLabel(entry.protocol);
            badge.style.background = (PROTOCOL_COLORS[entry.protocol] || "#8b949e") + "22";
            badge.style.color = PROTOCOL_COLORS[entry.protocol] || "#8b949e";

            const meta = document.createElement("span");
            meta.className = "phonebook-meta";
            meta.appendChild(badge);
            if (entry.tone) {
                const tone = document.createElement("span");
                tone.className = "tone-label";
                tone.textContent = entry.tone;
                meta.appendChild(tone);
            }

            row.appendChild(freq);
            row.appendChild(desc);
            row.appendChild(meta);
            section.appendChild(row);
        }

        container.appendChild(section);
    }
}

async function smartTune(freqMhz) {
    const gain = $("gainSelect").value === "auto" ? "auto" : $("gainSlider").value;

    // Update UI immediately
    $("freqInput").value = freqMhz.toFixed(3);
    if (window.updateFreqWidget) updateFreqWidget(freqMhz);
    $("status").textContent = "Tuning...";
    $("status").dataset.state = "reconnecting";

    try {
        const resp = await fetch("/api/smart-tune", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ freq_mhz: freqMhz, gain }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Failed: ${resp.status}`);

        // Determine what was started
        if (data.decoder === "analog" && (data.mode === "wfm" || data.mode === "am")) {
            running = true;
            digitalActive = false;
            $("startBtn").textContent = "Stop";
            $("startBtn").classList.add("active");
            $("status").textContent = "Running";
            $("status").dataset.state = "running";
        } else {
            running = false;
            digitalActive = true;
            $("digitalBtn").textContent = "Stop";
            $("digitalBtn").classList.add("active");
            $("digitalStatus").textContent = `Monitoring ${freqMhz.toFixed(3)} MHz (${protocolLabel(data.protocol)})`;
            $("status").textContent = "Digital Monitor";
            $("status").dataset.state = "digital";
        }

        // Update mode buttons
        const modeMap = { wfm: "wfm", am: "am", nfm: "nfm" };
        const uiMode = modeMap[data.mode] || "nfm";
        document.querySelectorAll(".mode-btn").forEach((b) =>
            b.classList.toggle("active", b.dataset.mode === uiMode)
        );

        initAudio();
        connect();
    } catch (e) {
        console.error("Smart tune error:", e);
        $("status").textContent = "Error: " + e.message;
        $("status").dataset.state = "stopped";
    }
}

// --- Scanner ---

async function runScan() {
    const btn = $("scanBtn");
    btn.disabled = true;
    btn.textContent = "Scanning...";

    const resp = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            start_mhz: parseFloat($("scanStart").value),
            end_mhz: parseFloat($("scanEnd").value),
        }),
    });
    const signals = await resp.json();

    let html = "<table><tr><th>Freq (MHz)</th><th>Power (dB)</th></tr>";
    for (const s of signals) {
        html += `<tr onclick="tuneToFreq(${s.freq_mhz})">`;
        html += `<td>${s.freq_mhz.toFixed(3)}</td><td>${s.power_db}</td></tr>`;
    }
    html += "</table>";
    if (!signals.length) html = '<div style="color:#484f58;font-size:12px;padding:8px">No signals found</div>';
    $("scanResults").innerHTML = html;

    btn.disabled = false;
    btn.textContent = "Scan";
}

// --- Recording ---

async function recordAudio() {
    const btn = $("recordBtn");
    const duration = parseFloat($("recordDuration").value);
    const mode = document.querySelector(".mode-btn.active").dataset.mode;

    btn.disabled = true;
    btn.classList.add("recording");
    btn.textContent = `Recording ${duration}s...`;
    $("recordStatus").textContent = "";

    try {
        const resp = await fetch("/api/record", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ duration_seconds: duration, mode }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Failed: ${resp.status}`);
        $("recordStatus").textContent = `Saved: ${data.filename} (${data.duration_seconds}s)`;
    } catch (e) {
        $("recordStatus").textContent = "Error: " + e.message;
    } finally {
        btn.disabled = false;
        btn.classList.remove("recording");
        btn.textContent = "Record";
    }
}

// --- Digital Monitor ---

function showDigitalOverlay(msg) {
    const w = specCanvas.getBoundingClientRect().width;
    const h = specCanvas.getBoundingClientRect().height;
    const ctx = specCtx;

    ctx.fillStyle = "#060a0f";
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = "#d29922";
    ctx.font = "18px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`Monitoring ${msg.freq_mhz.toFixed(3)} MHz`, w / 2, h / 2 - 10);
    ctx.font = "13px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.fillStyle = "#8b949e";
    ctx.fillText(`Mode: ${msg.mode.toUpperCase()}`, w / 2, h / 2 + 15);
    ctx.textAlign = "left";

    const callsDiv = $("digitalCalls");
    if (msg.calls && msg.calls.length) {
        callsDiv.innerHTML = msg.calls
            .map((c) => `<div><span style="color:#484f58">${c.time}</span> ${c.message}</div>`)
            .join("");
    }
}

async function toggleDigital() {
    if (digitalActive) {
        await stopDigital();
    } else {
        await startDigital();
    }
}

async function startDigital() {
    const freq = parseFloat($("digitalFreq").value);
    const mode = $("digitalMode").value;
    const gain = $("gainSelect").value === "auto" ? "auto" : $("gainSlider").value;

    $("digitalBtn").disabled = true;
    $("digitalStatus").textContent = "Starting monitor...";

    try {
        // Stop spectrum streaming if active
        if (running) {
            await stopRadio();
        }

        const resp = await fetch("/api/digital/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ freq_mhz: freq, mode, gain }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Failed: ${resp.status}`);

        digitalActive = true;
        $("digitalBtn").textContent = "Stop";
        $("digitalBtn").classList.add("active");
        $("digitalStatus").textContent = `Monitoring ${freq.toFixed(3)} MHz (${mode.toUpperCase()})`;
        $("status").textContent = "Digital Monitor";
        $("status").dataset.state = "digital";
        $("freqInput").value = freq.toFixed(3);
        if (window.updateFreqWidget) updateFreqWidget(freq);
        initAudio();
        connect();
    } catch (e) {
        console.error("Digital start error:", e);
        $("digitalStatus").textContent = "Error: " + e.message;
    } finally {
        $("digitalBtn").disabled = false;
    }
}

async function stopDigital() {
    digitalActive = false;
    if (ws) ws.close();
    ws = null;
    if (audioCtx) {
        audioCtx.close();
        audioCtx = null;
    }
    await fetch("/api/digital/stop", { method: "POST" });
    $("digitalBtn").textContent = "Monitor";
    $("digitalBtn").classList.remove("active");
    $("digitalStatus").textContent = "";
    $("digitalCalls").innerHTML = "";
    $("status").textContent = "Stopped";
    $("status").dataset.state = "stopped";
}

// --- Per-Digit Frequency Widget (SDR++ style) ---

function initFreqWidget() {
    const container = document.querySelector(".freq-display");
    if (!container) return;

    const input = $("freqInput");
    input.style.display = "none";
    container.querySelectorAll(".freq-nudge").forEach((b) => b.remove());
    const existingUnit = container.querySelector(".freq-unit");
    if (existingUnit) existingUnit.remove();

    const widget = document.createElement("div");
    widget.className = "freq-widget";

    // Place values in Hz: [100M, 10M, 1M, 100k, 10k, 1k, 100, 10, 1]
    const placeValues = [100e6, 10e6, 1e6, 100e3, 10e3, 1e3, 100, 10, 1];
    const digits = [];

    for (let i = 0; i < 9; i++) {
        if (i === 3 || i === 6) {
            const dot = document.createElement("span");
            dot.className = "freq-dot";
            dot.textContent = ".";
            widget.appendChild(dot);
        }
        const span = document.createElement("span");
        span.className = "freq-digit";
        span.textContent = "0";

        span.addEventListener("wheel", (e) => {
            e.preventDefault();
            const dir = e.deltaY < 0 ? 1 : -1;
            const hz = parseFloat(input.value) * 1e6;
            const newMhz = Math.max(24, Math.min(1766, (hz + dir * placeValues[i]) / 1e6));
            tuneToFreq(newMhz);
        }, { passive: false });

        span.addEventListener("click", (e) => {
            const rect = span.getBoundingClientRect();
            const dir = e.clientY < rect.top + rect.height / 2 ? 1 : -1;
            const hz = parseFloat(input.value) * 1e6;
            const newMhz = Math.max(24, Math.min(1766, (hz + dir * placeValues[i]) / 1e6));
            tuneToFreq(newMhz);
        });

        digits.push(span);
        widget.appendChild(span);
    }

    const unit = document.createElement("span");
    unit.className = "freq-unit freq-unit-label";
    unit.textContent = "MHz";
    widget.appendChild(unit);

    container.insertBefore(widget, container.firstChild);

    window.updateFreqWidget = function (mhz) {
        const hz = Math.round(mhz * 1e6);
        const str = String(hz).padStart(9, "0").slice(-9);
        for (let i = 0; i < 9; i++) {
            digits[i].textContent = str[i];
            const leadingZero = i < 3 && !str.slice(0, i + 1).match(/[1-9]/);
            digits[i].classList.toggle("dim", leadingZero);
        }
        input.value = mhz.toFixed(3);
    };

    updateFreqWidget(parseFloat(input.value));
}

// --- Init ---

window.addEventListener("resize", initCanvases);
initCanvases();
loadPhonebook();
initFreqWidget();
