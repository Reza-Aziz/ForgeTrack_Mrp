
from odoo import api, fields, models


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

    @api.model
    def get_summary(self, domain):
        """Agregasi bacaan per mesin untuk dashboard, dipanggil dari JS."""
        groups = self._read_group(
            domain,
            groupby=["machine_id"],
            aggregates=["__count", "distance_cm:avg", "distance_cm:min",
                        "distance_cm:max", "reading_time:max"],
        )
        summary = []
        for machine_id, count, avg_d, min_d, max_d, last in groups:
            if last:
                last = fields.Datetime.context_timestamp(self, last).strftime("%d %b %Y %H:%M")
            summary.append({
                "machine_id": machine_id,
                "count": count,
                "avg_distance": avg_d and round(avg_d, 1),
                "min_distance": min_d,
                "max_distance": max_d,
                "last_reading": last or "",
            })
        return summary
