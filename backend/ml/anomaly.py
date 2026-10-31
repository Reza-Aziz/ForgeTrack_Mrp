"""Fitur 2 — Deteksi anomali kecepatan & kemacetan (jamming/bottleneck).

Pendekatan: EMA thresholding + z-score pada bucket 5 menit (tanpa dependensi):

  1. Bacaan 3 jam terakhir dibucket per 5 menit -> laju items/menit.
  2. Baseline = EMA(alpha=0.3) atas 12 bucket sebelum bucket terakhir.
  3. Anomali jika bucket terakhir turun >= 75% dari baseline
     (misc at ~ z >= 2 dengan deviasi historis), ATAU gaung (gap).
  4. Confidence = kombinasi drop% & z, dinormalisasi 0..1.

Catatan desain: deteksi "jamming" vs "mesin dimatikan" membedakannya dengan
instruksi idle (belum ada di MQTT topic — di masa depan, publisher kirim
`state: idle`). Selama itu belum ada, gap panjang tetap di-flag, eja nama level.
"""

import time
from datetime import datetime, timedelta, timezone

from odoo_data import WIB, fetch_readings, parse_utc, post_event

BUCKET_MIN = 5          # jendela bucket
BASELINE_BUCKETS = 12   # baseline dari 12 bucket = 1 jam
WINDOW = timedelta(hours=3)
ALPHA = 0.3             # EMA smoothing
DROP_BREAK = 0.75       # anomal bila laju < 75% dari baseline
Z_BREAK = 2.0
DEBOUNCE = 300          # detik: satu mesin tidak diflood alert berulang

_last_alerted = {}  # machine_id -> ts alert terakhir


def _wib(s):
    return parse_utc(s).replace(tzinfo=timezone.utc).astimezone(WIB)


def detect_anomaly(machine_id, now_wib=None):
    """Return list event anomali (0 atau 1 event) untuk satu mesin."""
    now_wib = now_wib or datetime.now(timezone.utc).astimezone(WIB)
    cutoff = now_wib - WINDOW
    rows = [_wib(r["reading_time"]) for r in fetch_readings()
            if r["machine_id"] == machine_id]
    rows = sorted(t for t in rows if cutoff <= t <= now_wib)

    if not rows:
        return []

    # bucket 5 menit -> items/menit (0.agar bucket tanpa data tetap = 0)
    bucket_count = {}
    for t in rows:
        key = int((t - cutoff).total_seconds() // (BUCKET_MIN * 60))
        bucket_count[key] = bucket_count.get(key, 0) + 1
    n_buckets = min(int((now_wib - cutoff).total_seconds() // (BUCKET_MIN * 60)) + 1, 36)
    rates = [bucket_count.get(i, 0) / BUCKET_MIN for i in range(n_buckets)]

    cur = rates[-1]
    hist = rates[-1 - BASELINE_BUCKETS:-1] or [cur]
    # EMA urut kronologis
    ema = hist[0]
    for v in hist[1:]:
        ema = ALPHA * v + (1 - ALPHA) * ema
    mean = sum(hist) / len(hist)
    std = (sum((v - mean) ** 2 for v in hist) / len(hist)) ** 0.5

    baseline_rate = max(ema, 1e-6)
    drop = 1 - cur / baseline_rate
    z = (baseline_rate - cur) / (std or 1e-6)

    if drop < DROP_BREAK and z < Z_BREAK:
        return []  # normal

    # debounce: dashboard polling 5-10 dtk bernilai jutaan event → 1x/menit cukup
    if time.time() - _last_alerted.get(machine_id, 0) < DEBOUNCE:
        return []

    confidence = min(1.0, round(0.6 * (drop / 1.0) + 0.4 * min(z / 3, 1.0), 2))
    level = "critical" if confidence >= 0.7 else "warning"
    pct = round(drop * 100)
    event = {
        "machine_id": machine_id,
        "detected_wib": now_wib.strftime("%d %b %Y %H:%M WIB"),
        "rate_now_per_min": round(cur, 2),
        "rate_baseline_per_min": round(baseline_rate, 2),
        "drop_pct": pct,
        "z_score": round(z, 2),
        "confidence": confidence,
        "level": level,
        "message": (
            f"Kemacetan diduga: laju turun {pct}% (z={z:.1f}) dari baseline EMA — "
            f"periksa konveyor / kebersihan sensor {machine_id}."
        ),
    }
    _last_alerted[machine_id] = time.time()
    event["_pushed"] = True
    post_event(machine_id, "anomaly", level, event["message"], event)  # log persist
    return [event]
