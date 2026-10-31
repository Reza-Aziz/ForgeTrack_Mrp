"""Klien data: ambil bacaan dari Odoo + kirim log event ML.

Dipakai bersama semua fitur ML. Cache sederhana 60 detik agar polling
dasbor tidak membebani Odoo.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# .env ada di backend/ (satu folder di atas)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069").rstrip("/")
ODOO_DB = os.getenv("ODOO_DB", "forgetrack_db")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")

WIB = timezone(timedelta(hours=7))  # WIB, tanpa DST
CACHE_TTL = 60  # detik
CACHE_DAYS = 30  # jendela data historis

_cache = {"t": 0.0, "readings": []}


def _headers():
    if not ODOO_API_KEY:
        raise RuntimeError("ODOO_API_KEY belum diatur di .env")
    return {
        "Authorization": f"bearer {ODOO_API_KEY}",
        "X-Odoo-Database": ODOO_DB,
        "Content-Type": "application/json",
    }


def fetch_readings():
    """Semua bacaan CACHE_DAYS terakhir, terbaru dulu. Datetime naive-UTC.

    Dicache 60 s — cukup untuk polling dasbor 5 s.
    """
    if time.time() - _cache["t"] < CACHE_TTL:
        return _cache["readings"]

    since = (datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    url = f"{ODOO_URL}/json/2/forgetrack.machine.reading/search_read"
    resp = requests.post(url, headers=_headers(), timeout=15, json={
        "domain": [["reading_time", ">=", since]],
        "fields": ["machine_id", "distance_cm", "reading_time"],
        "limit": 50000,
    })
    resp.raise_for_status()
    readings = resp.json()
    if isinstance(readings, dict):  # /json/2 kadang membungkus hasil
        readings = readings.get("result", readings.get("data", []))
    _cache.update({"t": time.time(), "readings": readings})
    return readings


def parse_utc(s):
    """'YYYY-MM-DD HH:MM:SS' (UTC server) -> datetime naive-UTC."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def wib_hour(s):
    """Jam WIB (0..23) dari string reading_time."""
    return parse_utc(s).replace(tzinfo=timezone.utc).astimezone(WIB).hour


def post_event(machine_id, kind, level, message, payload):
    """Push event/alert ML ke Odoo (model forgetrack.ml.event).

    Dipanggil dari anomaly detector; gagal jaringan tidak boleh mematikan API.
    """
    url = f"{ODOO_URL}/json/2/forgetrack.ml.event/create"
    try:
        resp = requests.post(url, headers=_headers(), json={
            "vals_list": [{
                "machine_id": machine_id,
                "kind": kind,
                "level": level,
                "message": message,
                "payload": payload,  # fields.Json
            }],
        }, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print("[ML] push event gagal:", e)
