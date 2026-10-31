
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
    def get_summary(self, domain, hours=None):
        """Agregasi bacaan per mesin untuk dashboard, dipanggil dari JS.

        hours: list int 0..23 (jam lokal user) untuk filter, atau None (tanpa filter).
        """
        if hours is None:
            return self._summary_from_groups(self._read_group(
                domain,
                groupby=["machine_id"],
                aggregates=["__count", "distance_cm:avg", "distance_cm:min",
                            "distance_cm:max", "reading_time:max"],
            ))
        # Data kecil: search + loop python murni, filter per jam lokal user.
        allowed = set(hours)
        buckets = {}
        for rec in self.search(domain):
            local_hour = fields.Datetime.context_timestamp(self, rec.reading_time).hour
            if local_hour in allowed:
                buckets.setdefault(rec.machine_id, []).append(rec)
        groups = []
        for machine_id, recs in buckets.items():
            dists = [r.distance_cm for r in recs if r.distance_cm]
            groups.append((
                machine_id,
                len(recs),
                sum(dists) / len(dists) if dists else False,
                min(dists) if dists else False,
                max(dists) if dists else False,
                recs[0].reading_time,  # _order desc, id desc -> recs[0] terbaru
            ))
        return self._summary_from_groups(groups)

    @api.model
    def _summary_from_groups(self, groups):
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

    @api.model
    def get_hourly(self, domain):
        """24 bucket jam lokal {"hour": 0..23, "count": n} dalam domain."""
        hours = [0] * 24
        for rec in self.search(domain):
            hours[fields.Datetime.context_timestamp(self, rec.reading_time).hour] += 1
        return [{"hour": h, "count": c} for h, c in enumerate(hours)]
