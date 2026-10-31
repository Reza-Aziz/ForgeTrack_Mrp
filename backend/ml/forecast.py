"""Fitur 3 — Forecast kebutuhan produksi (demand forecasting per hari).

Model utama: Holt-Winters (ExponentialSmoothing, musiman mingguan period=7,
statsmodels). Fallback saat data < 14 hari: rata-rata hari yang sama
(weekday) dari riwayat yang ada — masih lebih informatif daripada menebak.
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from statsmodels.tsa.holtwinters import ExponentialSmoothing

from odoo_data import WIB, fetch_readings, parse_utc

MIN_DAYS_HW = 14  # butuh >= 2 minggu utk musiman mingguan


def _wib(s):
    return parse_utc(s).replace(tzinfo=timezone.utc).astimezone(WIB)


NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def forecast(machine_id, rows=None, tomorrow_wib=None):
    """Proyeksi total produksi HARI ESOK untuk mesin."""
    tomorrow_wib = tomorrow_wib or (
        datetime.now(timezone.utc).astimezone(WIB) + timedelta(days=1)
    )
    rows = rows if rows is not None else [
        r for r in fetch_readings() if r["machine_id"] == machine_id
    ]

    # deret harian (hari WIB -> count), diisi 0 utk hari kosong
    per_day = defaultdict(int)
    for r in rows:
        per_day[_wib(r["reading_time"]).date()] += 1
    if not per_day:
        return {"machine_id": machine_id, "recommended_target": None,
                "method": "no_data", "note": "Belum ada data historis."}

    first, last = min(per_day), max(per_day)
    start_dow = first.weekday()
    series = []
    d = first
    while d <= last:
        series.append(per_day.get(d, 0))
        d += timedelta(days=1)
    n = len(series)
    dow = tomorrow_wib.weekday()

    if n >= MIN_DAYS_HW:
        try:
            fit = ExponentialSmoothing(
                series, trend="add", seasonal="add", seasonal_periods=7,
            ).fit()
            pred = max(math.ceil(float(fit.forecast(1)[0])), 1)
        except Exception:
            pred = _weekday_mean(series, start_dow, dow)
        method = "holt_winters (musiman mingguan)"
    else:
        pred = _weekday_mean(series, start_dow, dow)
        method = f"baseline rata-rata {NAMA_HARI[dow]} (hari data: {min(n, 7)})"

    return {
        "machine_id": machine_id,
        "forecast_date": tomorrow_wib.strftime("%d %b %Y"),
        "weekday": NAMA_HARI[dow],
        "recommended_target": pred,
        "history_days": n,
        "method": method,
        "recent_values": series[-7:],
    }


def _weekday_mean(series, start_dow, target_dow):
    """Rata-rata produksi utk weekday target (weekday start = index 0 seri)."""
    shift = (target_dow - start_dow) % 7
    vals = [series[k] for k in range(shift, len(series), 7)]
    return max(math.ceil(sum(vals) / max(len(vals), 1)), 1) if vals else 1
