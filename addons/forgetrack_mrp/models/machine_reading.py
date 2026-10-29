
from odoo import fields, models


class ForgeTrackMachineReading(models.Model):
    _name = "forgetrack.machine.reading"
    _description = "ForgeTrack Machine Reading"
    _order = "reading_time desc, id desc"

    machine_id = fields.Char(
        string="Device ID",
        required=True,
        index=True,
    )

    distance_cm = fields.Float(
        string="Distance (cm)",
        digits=(10, 2),
    )

    reading_time = fields.Datetime(
        string="Reading Time",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
