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

function drawSpectrum(freqs, power, centerFreq) {
    const w = specCanvas.getBoundingClientRect().width;
    const h = specCanvas.getBoundingClientRect().height;
    const ctx = specCtx;
    const plotW = w - SPEC_LEFT;
    const plotH = h - SPEC_BOTTOM - SPEC_TOP;

    // Clear
    ctx.fillStyle = "#060a0f";
    ctx.fillRect(0, 0, w, h);

    const minP = Math.min(...power);
    const maxP = Math.max(...power);
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
    const freqStart = freqs[0];
    const freqEnd = freqs[freqs.length - 1];
    const freqSpan = freqEnd - freqStart;
    let tickMhz = 0.5;
    if (freqSpan < 1) tickMhz = 0.1;
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
        ctx.fillText(f.toFixed(2), x, h - 6);
    }

    // Center frequency marker
    const centerX = SPEC_LEFT + ((centerFreq - freqStart) / freqSpan) * plotW;
    ctx.strokeStyle = "rgba(255, 80, 80, 0.5)";
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(centerX, SPEC_TOP);
    ctx.lineTo(centerX, SPEC_TOP + plotH);
    ctx.stroke();
    ctx.setLineDash([]);

    // Spectrum line
    ctx.strokeStyle = "#00d4aa";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < power.length; i++) {
        const x = SPEC_LEFT + (i / power.length) * plotW;
        const y = SPEC_TOP + plotH - ((power[i] - dbMin) / dbRange) * plotH;
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

    // Center freq label
    ctx.fillStyle = "#8b949e";
    ctx.font = "11px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(centerFreq.toFixed(3) + " MHz", centerX, SPEC_TOP + 14);
    ctx.textAlign = "left";
}

function heatColor(v) {
    if (v < 0.15) return [0, 0, Math.floor(v / 0.15 * 120)];
    if (v < 0.3) return [0, Math.floor((v - 0.15) / 0.15 * 180), 120 + Math.floor((v - 0.15) / 0.15 * 135)];
    if (v < 0.5) return [0, 180 + Math.floor((v - 0.3) / 0.2 * 75), Math.floor((1 - (v - 0.3) / 0.2) * 255)];
    if (v < 0.75) return [Math.floor((v - 0.5) / 0.25 * 255), 255, 0];
    return [255, Math.floor((1 - (v - 0.75) / 0.25) * 255), 0];
}

function drawWaterfall(power) {
    const w = wfCanvas.width;
    const h = wfCanvas.height;
    const ctx = wfCtx;
    const dpr = window.devicePixelRatio || 1;

    // Shift down 1 pixel (in canvas coordinates)
    if (h > 1) {
        const img = ctx.getImageData(0, 0, w, h - 1);
        ctx.putImageData(img, 0, 1);
    }

    const minP = Math.min(...power);
    const maxP = Math.max(...power);
    const range = maxP - minP || 1;

    const row = ctx.createImageData(w, 1);
    for (let i = 0; i < w; i++) {
        const idx = Math.floor((i / w) * power.length);
        const norm = (power[idx] - minP) / range;
        const [r, g, b] = heatColor(norm);
        row.data[i * 4] = r;
        row.data[i * 4 + 1] = g;
        row.data[i * 4 + 2] = b;
        row.data[i * 4 + 3] = 255;
    }
    ctx.putImageData(row, 0, 0);
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

// --- Click-to-tune on spectrum and waterfall ---

function clickToTune(e, canvas) {
    if (!currentFreqs.length) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    if (clickX < SPEC_LEFT) return;
    const x = (clickX - SPEC_LEFT) / (rect.width - SPEC_LEFT);
    const freq = currentFreqs[0] + x * (currentFreqs[currentFreqs.length - 1] - currentFreqs[0]);
    tuneToFreq(freq);
}

specCanvas.addEventListener("click", (e) => clickToTune(e, specCanvas));
wfCanvas.addEventListener("click", (e) => clickToTune(e, wfCanvas));

// --- Presets ---

const PRESET_GROUPS = {
    "FM Radio": ["fm_"],
    "Aviation": ["aviation_", "atis"],
    "NOAA Weather": ["noaa_"],
    "Marine": ["marine_"],
    "Public Safety": ["public_safety_"],
    "ADS-B": ["adsb"],
    "Carter County": ["carter_", "ems_", "sycamore_", "elizabethton_", "happy_valley_", "unaka_", "walmart_"],
};

async function loadBands() {
    const resp = await fetch("/api/bands");
    const bands = await resp.json();
    const container = $("presets");
    container.innerHTML = "";

    const matched = new Set();

    for (const [groupName, prefixes] of Object.entries(PRESET_GROUPS)) {
        const entries = Object.entries(bands).filter(([name]) =>
            prefixes.some((p) => name.startsWith(p) || name === p)
        );
        if (!entries.length) continue;
        entries.forEach(([name]) => matched.add(name));

        const group = document.createElement("div");
        group.className = "preset-group";

        const label = document.createElement("span");
        label.className = "preset-group-label";
        label.textContent = groupName;
        group.appendChild(label);

        const btns = document.createElement("div");
        btns.className = "preset-group-buttons";

        for (const [name, info] of entries) {
            const btn = document.createElement("button");
            btn.className = "preset-btn";
            btn.textContent = name.replace(/_/g, " ");
            btn.title = `${info.description} (${info.frequency_mhz} MHz, ${info.mode.toUpperCase()})`;
            btn.onclick = async () => {
                const r = await fetch("/api/preset", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name }),
                });
                const data = await r.json();
                $("freqInput").value = data.frequency_mhz.toFixed(3);
                setMode(data.mode);
                document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
            };
            btns.appendChild(btn);
        }
        group.appendChild(btns);
        container.appendChild(group);
    }

    // Catch-all for unmatched presets
    const unmatched = Object.entries(bands).filter(([name]) => !matched.has(name));
    if (unmatched.length) {
        const group = document.createElement("div");
        group.className = "preset-group";
        const label = document.createElement("span");
        label.className = "preset-group-label";
        label.textContent = "Other";
        group.appendChild(label);
        const btns = document.createElement("div");
        btns.className = "preset-group-buttons";
        for (const [name, info] of unmatched) {
            const btn = document.createElement("button");
            btn.className = "preset-btn";
            btn.textContent = name.replace(/_/g, " ");
            btn.title = `${info.description} (${info.frequency_mhz} MHz, ${info.mode.toUpperCase()})`;
            btn.onclick = async () => {
                const r = await fetch("/api/preset", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name }),
                });
                const data = await r.json();
                $("freqInput").value = data.frequency_mhz.toFixed(3);
                setMode(data.mode);
                document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
            };
            btns.appendChild(btn);
        }
        group.appendChild(btns);
        container.appendChild(group);
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

// --- Init ---

window.addEventListener("resize", initCanvases);
initCanvases();
loadBands();
