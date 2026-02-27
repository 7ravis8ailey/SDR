import os
import sys
import asyncio
import logging

import numpy as np
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from sdr import SDR
from demod import demodulate, DEMODS
from spectrum import compute_spectrum
from scanner import scan_range
from bands import BANDS

log = logging.getLogger("sdr.web")
MOCK = "--mock" in sys.argv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

radio = SDR()
state = {
    "freq": 100.0e6,
    "mode": "wfm",
    "gain": "auto",
    "sample_rate": 2.048e6,
    "audio_rate": 48000,
    "fft_size": 1024,
    "running": False,
}


def mock_samples(n):
    t = np.arange(n) / state["sample_rate"]
    noise = (np.random.randn(n) + 1j * np.random.randn(n)) * 0.02
    sig = 0.5 * np.exp(2j * np.pi * 100e3 * t)
    return (sig + noise).astype(np.complex128)


async def start(request):
    body = await request.json()
    state["freq"] = body.get("freq_mhz", 100.0) * 1e6
    state["mode"] = body.get("mode", "wfm")
    state["gain"] = body.get("gain", "auto")
    if not MOCK:
        if radio.device:
            radio.close()
        gain = state["gain"] if state["gain"] == "auto" else float(state["gain"])
        radio.open(sample_rate=state["sample_rate"], center_freq=state["freq"], gain=gain)
    state["running"] = True
    return JSONResponse({"status": "started", "freq_mhz": state["freq"] / 1e6})


async def stop(request):
    state["running"] = False
    await asyncio.sleep(0.3)
    if not MOCK:
        radio.close()
    return JSONResponse({"status": "stopped"})


async def tune(request):
    body = await request.json()
    freq = body["freq_mhz"] * 1e6
    state["freq"] = freq
    if not MOCK and radio.device:
        radio.center_freq = freq
    return JSONResponse({"freq_mhz": body["freq_mhz"]})


async def set_mode(request):
    body = await request.json()
    state["mode"] = body["mode"]
    return JSONResponse({"mode": body["mode"]})


async def set_gain(request):
    body = await request.json()
    state["gain"] = body["gain"]
    if not MOCK and radio.device:
        radio.gain = body["gain"] if body["gain"] == "auto" else float(body["gain"])
    return JSONResponse({"gain": body["gain"]})


async def get_bands(request):
    result = {}
    for name, (freq, mode, bw, desc) in BANDS.items():
        result[name] = {
            "frequency_mhz": freq / 1e6,
            "mode": mode,
            "bandwidth_khz": bw / 1e3,
            "description": desc,
        }
    return JSONResponse(result)


async def set_preset(request):
    body = await request.json()
    name = body["name"]
    if name not in BANDS:
        return JSONResponse({"error": f"Unknown preset: {name}"}, status_code=400)
    freq, mode, bw, desc = BANDS[name]
    state["freq"] = freq
    state["mode"] = mode
    if not MOCK and radio.device:
        radio.center_freq = freq
    return JSONResponse({"frequency_mhz": freq / 1e6, "mode": mode, "description": desc})


async def run_scan(request):
    body = await request.json()
    was_running = state["running"]
    state["running"] = False
    await asyncio.sleep(0.2)

    if MOCK:
        signals = [{"freq_hz": 162.4e6, "freq_mhz": 162.4, "power_db": -18.5}]
    else:
        if not radio.device:
            radio.open(sample_rate=state["sample_rate"], center_freq=state["freq"], gain="auto")
        signals = await asyncio.to_thread(
            scan_range,
            radio,
            body["start_mhz"] * 1e6,
            body["end_mhz"] * 1e6,
            step=body.get("step_khz", 25) * 1e3,
            threshold_db=body.get("threshold_db", -30),
        )
        if not was_running:
            radio.close()

    return JSONResponse(signals)


async def get_state(request):
    return JSONResponse(
        {
            "freq_mhz": state["freq"] / 1e6,
            "mode": state["mode"],
            "gain": state["gain"],
            "running": state["running"],
            "mock": MOCK,
        }
    )


async def ws_stream(websocket):
    await websocket.accept()
    num_samples = 256 * 1024

    # Wait for state["running"] if client connects before Start is clicked
    for _ in range(600):  # up to 60 seconds
        if state["running"]:
            break
        await asyncio.sleep(0.1)

    if not state["running"]:
        await websocket.close()
        return

    try:
        while state["running"]:
            try:
                if MOCK:
                    iq = mock_samples(num_samples)
                else:
                    iq = await asyncio.to_thread(radio.read_samples, num_samples)
            except Exception as e:
                log.error(f"SDR read error: {e}")
                await asyncio.sleep(0.5)
                continue

            freqs_mhz, power_db = compute_spectrum(
                iq, state["sample_rate"], state["freq"], state["fft_size"]
            )

            audio = await asyncio.to_thread(
                demodulate, iq, state["mode"], state["sample_rate"], state["audio_rate"]
            )

            peak_idx = int(np.argmax(power_db))
            await websocket.send_json(
                {
                    "type": "spectrum",
                    "freqs": freqs_mhz.tolist(),
                    "power": power_db.tolist(),
                    "peak_freq": round(float(freqs_mhz[peak_idx]), 4),
                    "peak_power": round(float(power_db[peak_idx]), 1),
                    "center_freq": state["freq"] / 1e6,
                }
            )

            pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
            await websocket.send_bytes(pcm.tobytes())

            if MOCK:
                await asyncio.sleep(0.128)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"WebSocket error: {e}")


app = Starlette(
    routes=[
        Route("/api/start", start, methods=["POST"]),
        Route("/api/stop", stop, methods=["POST"]),
        Route("/api/tune", tune, methods=["POST"]),
        Route("/api/mode", set_mode, methods=["POST"]),
        Route("/api/gain", set_gain, methods=["POST"]),
        Route("/api/bands", get_bands, methods=["GET"]),
        Route("/api/preset", set_preset, methods=["POST"]),
        Route("/api/scan", run_scan, methods=["POST"]),
        Route("/api/state", get_state, methods=["GET"]),
        WebSocketRoute("/ws", ws_stream),
        Mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "static"), html=True)),
    ],
)

if __name__ == "__main__":
    import uvicorn

    port = 8080
    mode_str = "MOCK" if MOCK else "LIVE"
    print(f"SDR Lab Web UI ({mode_str}) — http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
