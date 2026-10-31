from datetime import timedelta, timezone

from odoo import api, fields, models

# Semua tampilan jam memakai WIB (UTC+7, tanpa DST) — konsisten dengan MQTT publisher.
WIB = timezone(timedelta(hours=7))
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _wib(dt):
    """Naive-UTC datetime -> datetime WIB."""
    return dt.replace(tzinfo=timezone.utc).astimezone(WIB)


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

        hours: list int 0..23 (jam WIB, dihitung server) untuk filter, atau None (tanpa filter).
        """
        if hours is None:
            return self._summary_from_groups(self._read_group(
                domain,
                groupby=["machine_id"],
                aggregates=["__count", "distance_cm:avg", "distance_cm:min",
                            "distance_cm:max", "reading_time:max"],
            ))
        # Data kecil: search + loop python murni, filter per jam WIB.
        allowed = set(hours)
        buckets = {}
        for rec in self.search(domain):
            local_hour = _wib(rec.reading_time).hour
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
        # last_ts = waktu bacaan TERBARU GLOBAL (tanpa filter) — dipakai JS untuk
        # status Running/Berhenti, supaya tidak ikut terpenalti filter rentang user.
        glob_last = {row[0]: row[1] for row in self._read_group(
            [], groupby=["machine_id"], aggregates=["reading_time:max"],
        )}
        summary = []
        for machine_id, count, avg_d, min_d, max_d, last in groups:
            formatted = ""
            if last:
                t = _wib(last)
                formatted = "%02d %s %d %02d:%02d WIB" % (
                    t.day, BULAN[t.month - 1], t.year, t.hour, t.minute,
                )
            ts = glob_last.get(machine_id)
            summary.append({
                "machine_id": machine_id,
                "count": count,
                "avg_distance": avg_d and round(avg_d, 1),
                "min_distance": min_d,
                "max_distance": max_d,
                "last_reading": formatted,
                # ISO-Z, diagram bisa Date.parse() langsung
                "last_ts": fields.Datetime.to_string(ts).replace(" ", "T") + "Z" if ts else "",
            })
        return summary

    @api.model
    def get_hourly(self, domain):
        """24 bucket jam WIB {"hour": 0..23, "count": n} dalam domain."""
        hours = [0] * 24
        for rec in self.search(domain):
            hours[_wib(rec.reading_time).hour] += 1
        return [{"hour": h, "count": c} for h, c in enumerate(hours)]
