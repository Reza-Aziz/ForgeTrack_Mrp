"""Fitur 1 — Prediksi Waktu Selesai (ETA) & keterlambatan.

Model: Random Forest Regressor dari scikit-learn.
  X = [jam_wib, hari_dalam_minggu, shift, laju_per_menit_jam_sebelumnya]
  y = laju_per_menit pada jam berikutnya (items/menit = jumlah bacaan/jam aktual)

Fallback: rate = laju saat ini (regresi sederhana sisa_target / rate).
"""

import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from odoo_data import WIB, fetch_readings, parse_utc

SHIFT_OF_HOUR = lambda h: "1" if h < 8 else ("2" if h < 16 else "3")
SHIFT_CLOSE_H = {"1": 8, "2": 16, "3": 24}  # jam WIB saat shift ditutup
MIN_TRAIN = 20  # titik historis minimal sebelum regresi dipakai

_lock = threading.Lock()
_models = {}  # machine_id -> {"model", "trained_at", "points"}


def _wib(s):
    return parse_utc(s).replace(tzinfo=timezone.utc).astimezone(WIB)


def _train_locked(rows, machine_id):
    """Latih ulang RF untuk satu mesin; dipanggil dalam lock, maks 1x/jam."""
    now = time.time()
    state = _models.get(machine_id)
    if state and now - state["trained_at"] < 3600:
        return state

    # statistik pelatihan: (dow, hour_wib) -> total bacaan; laju jam sebelumnya sbg fitur
    bucket = defaultdict(int)
    for r in rows:
        dt = _wib(r["reading_time"])
        bucket[(dt.weekday(), dt.hour)] += 1
    by_dow = defaultdict(list)
    for dow, h in bucket:
        by_dow[dow].append((h, bucket[(dow, h)]))

    samples, labels = [], []
    for dow, hours in by_dow.items():
        hours.sort()
        for i, (h, c) in enumerate(hours):
            prev = hours[i - 1][1] if i else 0
            samples.append([h, dow, SHIFT_OF_HOUR(h), prev])
            labels.append(c)

    if len(samples) < MIN_TRAIN:
        _models[machine_id] = {"model": None, "trained_at": now, "points": len(samples)}
        return _models[machine_id]

    model = RandomForestRegressor(n_estimators=60, random_state=42)
    model.fit(np.asarray(samples, dtype=float), np.asarray(labels, dtype=float))
    _models[machine_id] = {"model": model, "trained_at": now, "points": len(samples)}
    return _models[machine_id]


def predict_eta(machine_id, target, rows=None, now_wib=None):
    """Estimasi jam selesai target & flag terlambat. rows/now_wib untuk tes."""
    now_wib = now_wib or datetime.now(timezone.utc).astimezone(WIB)
    rows = rows if rows is not None else [
        r for r in fetch_readings() if r["machine_id"] == machine_id
    ]

    produced = sum(1 for r in rows if _wib(r["reading_time"]).date() == now_wib.date())
    remaining = target - produced
    if remaining <= 0:
        return {
            "machine_id": machine_id, "target": target,
            "produced_today": produced, "remaining": 0,
            "eta_wib": None, "is_delayed": False, "source": "target tercapai",
        }

    # laju saat ini: bacaan 10 menit terakhir → items/menit
    cutoff = now_wib - timedelta(minutes=10)
    current_rate = sum(1 for r in rows if _wib(r["reading_time"]) > cutoff) / 10.0

    with _lock:
        state = _train_locked(rows, machine_id)
    if state["model"] is not None:
        X = np.array([[
            now_wib.hour, now_wib.weekday(), SHIFT_OF_HOUR(now_wib.hour), current_rate * 60
        ]], dtype=float)
        rate_per_min = max(float(state["model"].predict(X)[0]) / 60.0, 1e-6)
        # gabung laju real-time & model 50:50 → lonjakan sesaat tidak membawa ETA salah arah
        if current_rate > 0:
            rate_per_min = 0.5 * current_rate + 0.5 * rate_per_min
        source = f"random_forest ({state['points']} titik historis)"
    else:
        rate_per_min = current_rate
        source = "baseline (sisa target / laju saat ini)"

    shift = SHIFT_OF_HOUR(now_wib.hour)
    if rate_per_min <= 0:
        return {
            "machine_id": machine_id, "target": target,
            "produced_today": produced, "remaining": remaining,
            "rate_per_min": 0, "eta_wib": None, "shift": shift,
            "is_delayed": None,  # tak bisa dihitung bila mesin mati/diam
            "source": source + " — laju 0 bacaan/menit, ETA tidak tersedia",
        }

    minutes = remaining / rate_per_min
    finish_time = now_wib + timedelta(minutes=minutes)
    shift = SHIFT_OF_HOUR(now_wib.hour)
    close_time = now_wib.replace(hour=SHIFT_CLOSE_H[shift] % 24, minute=0, second=0)
    if shift == "3":  # Shift 3 tutup tengah malam → bergeser 1 hari
        close_time += timedelta(days=1)
    return {
        "machine_id": machine_id,
        "target": target,
        "produced_today": produced,
        "remaining": remaining,
        "rate_per_min": round(rate_per_min, 2),
        "minutes_to_finish": round(minutes),
        "eta_wib": finish_time.strftime("%d %b %Y %H:%M WIB"),
        "shift": shift,
        "shift_close": close_time.strftime("%H:%M WIB"),
        "is_delayed": finish_time > close_time,
        "source": source,
    }
