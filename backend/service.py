"""ForgeTrack ML — FastAPI service (fitur 1–3).

Bukan proses terpisah lagi: dipanggil dari main.py bersama subscriber MQTT.
Jalan mandiri (opsional): uvicorn service:app --port 8001
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ml import anomaly, eta, forecast
from ml.odoo_data import fetch_readings

ORIGIN_DASH = "http://localhost:8069"  # dasbor Odoo

app = FastAPI(title="ForgeTrack ML", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ORIGIN_DASH],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _machines():
    ids = sorted({r["machine_id"] for r in fetch_readings()})
    if not ids:
        raise HTTPException(404, "Belum ada data bacaan di Odoo.")
    return ids


def _pick(machine_id):
    ids = _machines()
    if machine_id and machine_id not in ids:
        raise HTTPException(404, f"Mesin '{machine_id}' tidak ditemukan. Ada: {ids}")
    return machine_id or ",".join(ids)


@app.get("/health")
def health():
    return {"status": "ok", "machines": _machines()}


@app.get("/eta")
def get_eta(machine_id: str = "", target: int = 0):
    """Fitur 1: waktu selesai target & flag terlambat.

    Contoh: /eta?machine_id=machine-01&target=500
    """
    if target <= 0:
        raise HTTPException(400, "Parameter ?target= (pcs) wajib dan harus > 0")
    rows = fetch_readings()
    if machine_id:
        _pick(machine_id)
        return eta.predict_eta(machine_id, target, rows=rows)
    return {mid: eta.predict_eta(mid, target, rows=rows) for mid in _machines()}


@app.get("/anomalies")
def get_anomalies(machine_id: str = ""):
    """Fitur 2: event anomali/jamming; tiap event juga di-push ke Odoo."""
    ids = [machine_id] if machine_id else _machines()
    events = []
    for mid in ids:
        events += anomaly.detect_anomaly(mid)
    return {"count": len(events), "events": events}


@app.get("/forecast")
def get_forecast(machine_id: str = ""):
    """Fitur 3: rekomendasi target produksi hari esok."""
    ids = [machine_id] if machine_id else _machines()
    known = _machines()
    for mid in ids:
        if mid not in known:
            raise HTTPException(404, f"Mesin '{mid}' tidak ditemukan.")
    rows = fetch_readings()
    return {mid: forecast.forecast(mid, rows=rows) for mid in ids}
