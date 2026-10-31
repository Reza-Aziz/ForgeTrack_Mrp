# ForgeTrack ML Service

Layanan ML terpisah (di luar container Odoo). Membaca data bacaan dari Odoo
via JSON API (API key di `backend/.env`), lalu menyediakan 3 fitur cerdas:

| Fitur | Endpoint | Model | Output |
|-------|----------|-------|--------|
| 1. ETA | `GET /eta?machine_id=&target=` | Random Forest Regressor (+ baseline `sisa/laju`) | `eta_wib`, `is_delayed` |
| 2. Anomali | `GET /anomalies` | EMA thresholding + z-score (bucket 5 menit) | alert `confidence`, `level`, pesan |
| 3. Forecast | `GET /forecast` | Holt-Winters musiman mingguan (+ fallback weekday-mean) | `recommended_target` hari esok |

## Arsitektur

```
MQTT (ESP32/counter)
        │
        ▼
backend/subscriber.py ──► Odoo (forgetrack.machine.reading)
                                │  GET bacaan (30 hari, cache 60 s)
                                ▼
                    backend/ml/service.py  (FastAPI, port 8001)
                    ├── eta.py        RF + baseline
                    ├── anomaly.py    EMA/z-score → push ke forgetrack.ml.event
                    ├── forecast.py   Holt-Winters / fallback
                    └── odoo_data.py  klien data & push event
                                │
                                ▼
                    Dasbor OWL (polling 5 s) ← CORS localhost:8069
```

## Menjalankan

```powershell
cd backend\ml
..\.venv\Scripts\pip install -r requirements.txt
..\.venv\Scripts\uvicorn service:app --host 0.0.0.0 --port 8001
```

Cek: `curl http://localhost:8001/eta?machine_id=machine-01&target=500`

## Logika ringkas

- **ETA** — fitur `[jam_wib, weekday, shift, laju_jam_sebelumnya]` → laju
  (bacaan/jam). Prediksi digabung 50:50 dengan laju real-time 10 menit agar
  lonjakan sesaat tidak membawa ETA salah arah (model retrain maks 1x/jam).
  `is_delayed` = jam selesai > jam tutup shift WIB.
- **Anomali** — laju 5-menit terakhir vs EMA (α=0.3, baseline 1 jam):
  anomali bila turun ≥75% ATAU z ≥2; confidence = 0.6·drop + 0.4·z-score;
  debounce 5 menit per mesin. Alert juga di-POST ke `forgetrack.ml.event`.
- **Forecast** — total harian (WIB), ExponentialSmoothing trend+musiman
  mingguan; data < 14 hari → rata-rata weekday yang sama. Hasilnya dipakai
  sebagai **rekomendasi target** — diisi manual ke dasbor (localStorage).

## Penyimpanan hasil (Odoo)

Model `forgetrack.ml.event` (kolom: `machine_id`, `kind`, `event_time`,
`level`, `confidence`, `message`, `payload` JSON) + ACL group_user.
Migrasi: upgrade modul
`docker exec forgetrack-web-1 odoo -d forgetrack_db -r odoo -w odoo --db_host db -u forgetrack_mrp --stop-after-init`
lalu restart container.

## Keterbatasan & langkah lanjut

- Tanpa sinyal `state: idle` dari MQTT, gap lama (mesin mati) tetap
  ter-flag sebagai anomali — kontrak topic berikutnya: `factory/<id>/state`.
- Forecast harian butuh ±2 minggu data sebelum Holt-Winters lebih unggul
  dari fallback weekday-mean.
- Model tidak dipersist ke disk: retrain in-memory (data kecil); baca
  disk-cache (joblib) jika data membesar.
