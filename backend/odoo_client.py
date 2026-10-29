
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069").rstrip("/")
ODOO_DB = os.getenv("ODOO_DB", "forgetrack_db")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")


def send_to_odoo(device_id, distance_cm):
    if not ODOO_API_KEY:
        raise RuntimeError("ODOO_API_KEY belum diatur di .env")

    url = f"{ODOO_URL}/json/2/forgetrack.machine.reading/create"

    headers = {
        "Authorization": f"bearer {ODOO_API_KEY}",
        "X-Odoo-Database": ODOO_DB,
        "Content-Type": "application/json",
    }

    payload = {
        "vals_list": [{
            "machine_id": str(device_id),
            "distance_cm": float(distance_cm),
            "reading_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }]
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=10,
    )
    response.raise_for_status()

    print("[ODOO] Data berhasil dikirim:", response.text)
