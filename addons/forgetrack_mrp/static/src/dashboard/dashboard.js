/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "forgetrack.machine.reading";
const TARGET_KEY = "forgetrack.dashboard.targets";
const RUNNING_MS = 5 * 60 * 1000; // bacaan terakhir < 5 menit lalu = Running
const ML_URL = "http://localhost:8001"; // layanan ML (backend/ml)

/** Shift 1 = jam 00–07, Shift 2 = 08–15, Shift 3 = 16–23 (WIB, dihitung server) */
const SHIFTS = {
    "1": [0, 1, 2, 3, 4, 5, 6, 7],
    "2": [8, 9, 10, 11, 12, 13, 14, 15],
    "3": [16, 17, 18, 19, 20, 21, 22, 23],
};

/** "2026-10-29T14:30" (datetime-local) → "2026-10-29 14:30:00" (UTC server) */
function toServerDate(val) {
    return val ? new Date(val).toISOString().slice(0, 19).replace("T", " ") : "";
}

/** Date → nilai input datetime-local (zona waktu browser) */
function localInput(d) {
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
        .toISOString().slice(0, 16);
}

/** 12483 → "12.4k" */
function fmtCount(n) {
    return n > 9999 ? (n / 1000).toFixed(1) + "k" : String(n);
}

/** Skala sumbu-Y "rapi": nilai tangga terdekat yang >= nilai tertinggi */
const LADDER = [4, 6, 8, 10, 12, 16, 20, 30, 40, 60, 80, 120, 160, 200, 300, 500, 800, 1200, 2000];
function niceMax(m) {
    return LADDER.find((v) => v >= (m || 1)) ?? Math.ceil(m / 2000) * 2000;
}

/** Jam WIB, format 24 jam (h23 menghindari "24:xx" saat tengah malam) */
const fmtClock = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Jakarta",
    hourCycle: "h23",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
});

function loadTargets() {
    try {
        return JSON.parse(localStorage.getItem(TARGET_KEY)) || {};
    } catch {
        return {};
    }
}

class ItemDashboard extends Component {
    static template = "forgetrack_mrp.Dashboard";

    setup() {
        this.orm = useService("orm");
        // helper dipasang di instance agar bisa dipanggil dari template OWL
        this.fmtCount = fmtCount;
        this.fmtDist = (n) => Math.round(n * 10) / 10;
        this.state = useState({
            cards: [], hourly: [], machineId: "",
            preset: "today",
            from: localInput(new Date(new Date().setHours(0, 0, 0, 0))),
            to: "",
            shift: "all",
            targets: loadTargets(),
            online: true,
            lastSync: "",
            ml: { online: true, eta: null, anomaly: null, forecast: null },
        });
        onWillStart(() => this.load());
        this.timer = setInterval(() => this.load(), 5000);
        onWillUnmount(() => clearInterval(this.timer));
    }

    get domain() {
        if (this.state.preset === "all") return [];
        const domain = [];
        if (this.state.from) {
            domain.push(["reading_time", ">=", toServerDate(this.state.from)]);
        }
        if (this.state.to) {
            domain.push(["reading_time", "<=", toServerDate(this.state.to)]);
        }
        return domain;
    }

    get shiftHours() {
        return this.state.shift === "all" ? null : SHIFTS[this.state.shift];
    }

    get machine() {
        return this.state.cards.find((c) => c.machine_id === this.state.machineId);
    }

    /** "run" | "stop" — murni dari umur bacaan MQTT terakhir (field server last_ts) */
    get status() {
        const ts = this.machine?.last_ts;
        return ts && Date.now() - Date.parse(ts) < RUNNING_MS ? "run" : "stop";
    }

    get progress() {
        const m = this.machine;
        const target = Math.floor(+(this.state.targets[this.state.machineId] || 0));
        if (!m || !target) return { hidden: true, pctLabel: "0", width: 0, cls: "" };
        const pct = (m.count / target) * 100;
        return {
            hidden: false,
            pctLabel: Math.ceil(pct),
            width: Math.min(pct, 100),
            cls: pct >= 100 ? "bg-success" : pct >= 80 ? "bg-warning" : "bg-primary",
        };
    }

    /** target dibagi rata ke jam tampil — penanda di grafik, bukan data palsu */
    get targetPerHour() {
        const target = +(this.state.targets[this.state.machineId] || 0);
        if (!target) return 0;
        return target / (this.shiftHours ? this.shiftHours.length : 24);
    }

    /** deret jam sesuai filter shift */
    get series() {
        const hours = this.shiftHours;
        return this.state.hourly.filter((h) => !hours || hours.includes(h.hour));
    }

    /** batas atas sumbu Y: nilai tangga yang menampung tertinggi data & target */
    get gridMax() {
        const values = this.series.map((h) => h.count);
        if (this.targetPerHour) values.push(this.targetPerHour);
        return niceMax(Math.max(...values, 1));
    }

    /** label sumbu Y: 5 tingkat (100/75/50/25/0 % dari gridMax) */
    get yTicks() {
        const g = this.gridMax;
        return [g, g * 0.75, g * 0.5, g * 0.25, 0]
            .map((v) => (v % 1 ? v.toFixed(1) : String(v)));
    }

    /** posisi garis target, satuan viewBox 0–100 */
    get targetY() {
        return 100 - (this.targetPerHour / this.gridMax) * 100;
    }

    /** batang grafik; koordinat memakai satuan viewBox 0–100 */
    get bars() {
        const list = this.series;
        const max = this.gridMax;
        const step = 100 / Math.max(list.length, 1);
        const labelEvery = list.length > 12 ? 2 : 1; // 24 bar → label tiap 2 jam
        return list.map((h, i) => {
            const height = (h.count / max) * 100;
            return {
                hour: h.hour,
                label: String(h.hour).padStart(2, "0"),
                show: h.hour % labelEvery === 0,
                x: i * step + step * 0.2,
                w: step * 0.6,
                y: 100 - height,
                h: height,
                hit: this.targetPerHour && h.count >= this.targetPerHour,
                title: `${String(h.hour).padStart(2, "0")}:00 WIB · ${h.count} bacaan`,
            };
        });
    }

    async load() {
        this._seq = (this._seq || 0) + 1;
        const seq = this._seq;
        // hours hanya dikirim saat shift aktif (kontrak get_summary)
        const args = [this.domain];
        if (this.shiftHours) args.push(this.shiftHours);
        try {
            const [cards, hourly] = await Promise.all([
                this.orm.silent.call(MODEL, "get_summary", args),
                this.orm.silent.call(MODEL, "get_hourly", [this.domain]),
            ]);
            if (seq !== this._seq) return; // respons basi dari filter lama
            // lewati update bila payload tidak berubah → tanpa flicker
            const sig = JSON.stringify([cards, hourly]);
            if (sig !== this._sig) {
                this._sig = sig;
                this.state.cards = cards;
                this.state.hourly = hourly;
                if (!this.state.machineId && cards.length) {
                    this.state.machineId = cards[0].machine_id;
                }
            }
            this.state.lastSync = fmtClock.format(new Date());
            this.state.online = true;
        } catch {
            if (seq !== this._seq) return;
            this.state.online = false; // data terakhir tetap tampil
        }
        this._mlLoad();
    }

    /** Ambil hasil ML (ETA/anomali/forecast); gagal → badge mati, dasbor tetap hidup. */
    async _mlLoad() {
        const mid = this.state.machineId;
        if (!mid) return;
        const target = Math.floor(+(this.state.targets[mid] || 0));
        const urls = [`/anomalies?machine_id=${mid}`, `/forecast?machine_id=${mid}`];
        if (target) urls.push(`/eta?machine_id=${mid}&target=${target}`);
        try {
            const res = await Promise.all(
                urls.map((u) =>
                    fetch(ML_URL + u).then((r) => (r.ok ? r.json() : null))
                        .catch(() => null)),
            );
            const [an, fc, et] = res;
            // mindah hasil layanan ML ke state — event anomali & mesin dipilih
            this.state.ml = {
                online: res.some((v) => v !== null),
                anomaly: an?.events?.[0] || null,
                forecast: fc?.[mid] || null,
                eta: target ? et : null,
            };
        } catch {
            this.state.ml.online = false;
        }
    }

    setPreset(preset) {
        const st = this.state;
        st.preset = preset;
        if (preset === "custom") return;
        if (preset === "all") {
            st.from = "";
            st.to = "";
        } else {
            const now = new Date();
            const from = new Date(now);
            if (preset === "today") from.setHours(0, 0, 0, 0);
            else from.setDate(now.getDate() - Number(preset));
            st.from = localInput(from);
            st.to = preset === "today" ? "" : localInput(new Date(now.getTime() + 864e5));
        }
        this.load();
    }

    onDateChange() {
        this.state.preset = "custom";
        this.load();
    }

    setTarget(ev) {
        const id = this.state.machineId;
        if (!id) return;
        const targets = Object.assign({}, this.state.targets);
        const val = Math.floor(+ev.target.value || 0);
        if (val > 0) targets[id] = val;
        else delete targets[id]; // kosong/0 = tanpa target
        this.state.targets = targets;
        localStorage.setItem(TARGET_KEY, JSON.stringify(targets));
        this._mlLoad(); // target berubah → ETA langsung dihitung ulang
    }
}

registry.category("actions").add("forgetrack.dashboard", ItemDashboard);
