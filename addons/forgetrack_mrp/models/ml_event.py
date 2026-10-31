"""Simpan hasil prediksi & log anomali dari layanan ML (backend/ml/)."""

from odoo import fields, models


class ForgeTrackMLEvent(models.Model):
    _name = "forgetrack.ml.event"
    _description = "ForgeTrack ML Event (prediksi & alert)"
    _order = "event_time desc, id desc"
    _rec_name = "message"

    machine_id = fields.Char(
        string="Device ID",
        required=True,
        index=True,
    )

    kind = fields.Selection(
        selection=[
            ("anomaly", "Anomali Kecepatan"),
            ("eta", "Estimasi Selesai"),
            ("forecast", "Forecast"),
        ],
        string="Jenis Event",
        required=True,
        index=True,
    )

    event_time = fields.Datetime(
        string="Waktu Event",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    level = fields.Selection(
        selection=[
            ("info", "Info"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        string="Level",
        default="info",
    )

    confidence = fields.Float(
        string="Confidence (0-1)",
        digits=(3, 2),
    )

    message = fields.Char(
        string="Pesan",
    )

    payload = fields.Json(
        string="Payload",
        help="Detail lengkap respons model untuk audit/debug.",
    )
