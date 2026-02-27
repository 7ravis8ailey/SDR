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

function drawSpectrum(freqs, power, centerFreq) {
    const w = specCanvas.getBoundingClientRect().width;
    const h = specCanvas.getBoundingClientRect().height;
    const ctx = specCtx;

    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, w, h);

    const minP = Math.min(...power);
    const maxP = Math.max(...power);
    const range = maxP - minP || 1;

    // Spectrum line
    ctx.strokeStyle = "#0f0";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < power.length; i++) {
        const x = (i / power.length) * w;
        const y = h - 18 - ((power[i] - minP) / range) * (h - 28);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill under curve
    ctx.lineTo(w, h - 18);
    ctx.lineTo(0, h - 18);
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 255, 0, 0.05)";
    ctx.fill();

    // Center frequency marker
    ctx.strokeStyle = "rgba(255, 0, 0, 0.5)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(w / 2, 0);
    ctx.lineTo(w / 2, h - 18);
    ctx.stroke();
    ctx.setLineDash([]);

    // Labels
    ctx.fillStyle = "#666";
    ctx.font = "11px monospace";
    ctx.fillText(freqs[0].toFixed(2) + " MHz", 4, h - 4);
    ctx.fillText(centerFreq.toFixed(3) + " MHz", w / 2 - 35, 12);
    ctx.textAlign = "right";
    ctx.fillText(freqs[freqs.length - 1].toFixed(2) + " MHz", w - 4, h - 4);
    ctx.textAlign = "left";

    // dB scale
    ctx.fillText(maxP.toFixed(0) + " dB", 4, 22);
    ctx.fillText(minP.toFixed(0) + " dB", 4, h - 22);
}

function heatColor(v) {
    if (v < 0.25) return [0, Math.floor(v * 4 * 255), 255];
    if (v < 0.5) return [0, 255, Math.floor((1 - (v - 0.25) * 4) * 255)];
    if (v < 0.75) return [Math.floor((v - 0.5) * 4 * 255), 255, 0];
    return [255, Math.floor((1 - (v - 0.75) * 4) * 255), 0];
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
        initAudio();
        connect();
    } catch (e) {
        console.error("Start error:", e);
        $("status").textContent = "Error: " + e.message;
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

// --- Click-to-tune on spectrum ---

specCanvas.addEventListener("click", (e) => {
    if (!currentFreqs.length) return;
    const rect = specCanvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const freq =
        currentFreqs[0] +
        x * (currentFreqs[currentFreqs.length - 1] - currentFreqs[0]);
    tuneToFreq(freq);
});

// --- Presets ---

async function loadBands() {
    const resp = await fetch("/api/bands");
    const bands = await resp.json();
    const container = $("presets");
    for (const [name, info] of Object.entries(bands)) {
        const btn = document.createElement("button");
        btn.textContent = name.replace(/_/g, " ");
        btn.title = `${info.description} (${info.frequency_mhz} MHz, ${info.mode.toUpperCase()})`;
        btn.onclick = async () => {
            const resp = await fetch("/api/preset", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
            });
            const data = await resp.json();
            $("freqInput").value = data.frequency_mhz.toFixed(3);
            setMode(data.mode);
        };
        container.appendChild(btn);
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
    if (!signals.length) html = '<div style="color:#666;font-size:12px;padding:4px">No signals found</div>';
    $("scanResults").innerHTML = html;

    btn.disabled = false;
    btn.textContent = "Scan";
}

// --- Digital Monitor ---

function showDigitalOverlay(msg) {
    const w = specCanvas.getBoundingClientRect().width;
    const h = specCanvas.getBoundingClientRect().height;
    const ctx = specCtx;

    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = "#f80";
    ctx.font = "16px monospace";
    ctx.textAlign = "center";
    ctx.fillText(`Monitoring ${msg.freq_mhz.toFixed(3)} MHz`, w / 2, h / 2 - 10);
    ctx.font = "12px monospace";
    ctx.fillStyle = "#888";
    ctx.fillText(`Mode: ${msg.mode.toUpperCase()}`, w / 2, h / 2 + 15);
    ctx.textAlign = "left";

    // Show calls in digitalCalls div
    const callsDiv = $("digitalCalls");
    if (msg.calls && msg.calls.length) {
        callsDiv.innerHTML = msg.calls
            .map((c) => `<div><span style="color:#666">${c.time}</span> ${c.message}</div>`)
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
}

// --- Init ---

window.addEventListener("resize", initCanvases);
initCanvases();
loadBands();
