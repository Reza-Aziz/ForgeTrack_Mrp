
import json
import paho.mqtt.client as mqtt

from odoo_client import send_to_odoo

import os
from dotenv import load_dotenv

load_dotenv()

BROKER = os.getenv("MQTT_BROKER", "172.17.226.151")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "factory/machine-01/telemetry")


def on_connect(client, userdata, flags, reason_code, properties):
    print("Terhubung ke Mosquitto:", reason_code)

    if reason_code.is_failure:
        print("Koneksi MQTT gagal.")
        return

    client.subscribe(TOPIC)
    print("Mendengarkan topic:", TOPIC)


def on_message(client, userdata, message):
    payload = message.payload.decode("utf-8")

    print("\n--- DATA SENSOR DITERIMA ---")
    print("Topic:", message.topic)
    print("Payload:", payload)

    try:
        data = json.loads(payload)
        print("Data JSON:", data)

        device_id = data.get("device_id")
        distance_cm = data.get("distance_cm")

        if not device_id or distance_cm is None:
            print("[ERROR] device_id atau distance_cm tidak tersedia.")
            return

        send_to_odoo(device_id, distance_cm)

    except json.JSONDecodeError:
        print("[ERROR] Pesan bukan JSON yang valid.")

    except (ValueError, TypeError, RuntimeError) as error:
        print("[ERROR] Gagal mengirim data ke Odoo:", error)

    except Exception as error:
        print("[ERROR] Pengiriman gagal:", error)


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

client.on_connect = on_connect
client.on_message = on_message


def run():
    """Hubungkan & dengarkan MQTT (blokir). Dipanggil dari main.py atau __main__."""
    print(f"Menghubungkan ke Mosquitto {BROKER}:{PORT}...")
    client.connect(BROKER, PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    run()
