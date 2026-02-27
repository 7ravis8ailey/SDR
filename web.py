import os
import sys
import asyncio
import logging
import time
import wave

import numpy as np
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from sdr import SDR, acquire_device, release_device, device_owner
from demod import demodulate, DEMODS
from spectrum import compute_spectrum
from scanner import scan_range
from bands import BANDS
from digital import DigitalVoiceDecoder

log = logging.getLogger("sdr.web")
MOCK = "--mock" in sys.argv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")

radio = SDR()
decoder = DigitalVoiceDecoder()
state = {
    "freq": 100.0e6,
    "mode": "wfm",
    "gain": "auto",
    "sample_rate": 2.048e6,
    "audio_rate": 48000,
    "fft_size": 1024,
    "running": False,
    "digital_active": False,
}


def mock_samples(n):
    t = np.arange(n) / state["sample_rate"]
    noise = (np.random.randn(n) + 1j * np.random.randn(n)) * 0.02
    sig = 0.5 * np.exp(2j * np.pi * 100e3 * t)
    return (sig + noise).astype(np.complex128)


# --- Spectrum/Audio streaming endpoints ---


async def start(request):
    body = await request.json()
    if not MOCK and not acquire_device("webui"):
        owner = device_owner()
        return JSONResponse(
            {"error": f"Device in use by {owner}. Stop it first."}, status_code=409
        )
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
        release_device("webui")
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
            "digital_active": state["digital_active"],
            "mock": MOCK,
        }
    )


# --- Digital decoder endpoints ---


async def digital_start(request):
    body = await request.json()
    freq_hz = body["freq_mhz"] * 1e6
    mode = body.get("mode", "nfm")
    gain = body.get("gain", state["gain"])
    squelch = body.get("squelch", 0)

    # Stop webui streaming if active
    if state["running"]:
        state["running"] = False
        await asyncio.sleep(0.3)
        if not MOCK:
            radio.close()
            release_device("webui")

    if not MOCK:
        if not acquire_device("digital"):
            owner = device_owner()
            return JSONResponse(
                {"error": f"Device in use by {owner}."}, status_code=409
            )

    try:
        if not MOCK:
            await asyncio.to_thread(decoder.start, freq_hz, mode, gain, squelch)
        state["digital_active"] = True
        state["freq"] = freq_hz
        return JSONResponse({
            "status": "started",
            "freq_mhz": freq_hz / 1e6,
            "mode": mode,
        })
    except Exception as e:
        if not MOCK:
            release_device("digital")
        return JSONResponse({"error": str(e)}, status_code=500)


async def digital_stop(request):
    if decoder.active:
        await asyncio.to_thread(decoder.stop)
    state["digital_active"] = False
    if not MOCK:
        release_device("digital")
    return JSONResponse({"status": "stopped"})


async def digital_status(request):
    if MOCK:
        return JSONResponse({
            "active": state["digital_active"],
            "frequency_hz": state["freq"] if state["digital_active"] else None,
            "frequency_mhz": state["freq"] / 1e6 if state["digital_active"] else None,
            "mode": "nfm",
            "has_dsd": False,
            "has_rtl_fm": False,
            "pid": None,
        })
    return JSONResponse(decoder.get_status())


async def digital_calls(request):
    return JSONResponse(decoder.get_calls())


# --- Recording endpoints ---


async def record(request):
    body = await request.json()
    duration = body.get("duration_seconds", 10.0)
    mode = body.get("mode", state["mode"])

    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    freq_str = f"{state['freq'] / 1e6:.3f}MHz"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{freq_str}_{mode}.wav"
    filepath = os.path.join(RECORDINGS_DIR, filename)

    if MOCK:
        num_samples = int(state["sample_rate"] * duration)
        iq = mock_samples(num_samples)
    else:
        if not radio.device:
            return JSONResponse({"error": "Device not open. Start streaming first."}, status_code=400)
        num_samples = int(state["sample_rate"] * duration)
        iq = await asyncio.to_thread(radio.read_samples, num_samples)

    audio = await asyncio.to_thread(
        demodulate, iq, mode, state["sample_rate"], state["audio_rate"]
    )
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)

    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(state["audio_rate"])
        wf.writeframes(pcm.tobytes())

    return JSONResponse({
        "filename": filename,
        "duration_seconds": round(len(audio) / state["audio_rate"], 2),
        "frequency_mhz": state["freq"] / 1e6,
        "mode": mode,
        "size_bytes": os.path.getsize(filepath),
    })


async def list_recordings(request):
    if not os.path.exists(RECORDINGS_DIR):
        return JSONResponse([])
    files = []
    for f in sorted(os.listdir(RECORDINGS_DIR), reverse=True):
        if f.endswith(".wav"):
            path = os.path.join(RECORDINGS_DIR, f)
            files.append({
                "filename": f,
                "size_bytes": os.path.getsize(path),
            })
    return JSONResponse(files)


# --- WebSocket ---


async def ws_stream(websocket):
    await websocket.accept()
    num_samples = 256 * 1024

    # Wait for either state["running"] or state["digital_active"]
    for _ in range(600):  # up to 60 seconds
        if state["running"] or state["digital_active"]:
            break
        await asyncio.sleep(0.1)

    if not state["running"] and not state["digital_active"]:
        await websocket.close()
        return

    try:
        if state["digital_active"]:
            await _ws_digital_stream(websocket)
        else:
            await _ws_spectrum_stream(websocket, num_samples)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"WebSocket error: {e}")


async def _ws_spectrum_stream(websocket, num_samples):
    """Stream spectrum + demodulated audio from pyrtlsdr."""
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


async def _ws_digital_stream(websocket):
    """Stream decoded audio from digital decoder subprocess."""
    while state["digital_active"]:
        # Send status message (no spectrum in digital mode)
        await websocket.send_json({
            "type": "digital",
            "freq_mhz": state["freq"] / 1e6,
            "mode": decoder.mode or "nfm",
            "calls": decoder.get_calls()[-5:],
        })

        # Read decoded audio and forward to browser
        audio_bytes = await asyncio.to_thread(decoder.read_audio, 9600)
        if audio_bytes:
            await websocket.send_bytes(audio_bytes)

        await asyncio.sleep(0.1)


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
        Route("/api/digital/start", digital_start, methods=["POST"]),
        Route("/api/digital/stop", digital_stop, methods=["POST"]),
        Route("/api/digital/status", digital_status, methods=["GET"]),
        Route("/api/digital/calls", digital_calls, methods=["GET"]),
        Route("/api/record", record, methods=["POST"]),
        Route("/api/recordings", list_recordings, methods=["GET"]),
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
