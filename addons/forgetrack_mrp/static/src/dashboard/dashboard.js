/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "forgetrack.machine.reading";
const TARGET_KEY = "forgetrack.dashboard.targets";
const RUNNING_MS = 5 * 60 * 1000; // Running = bacaan terakhir < 5 menit lalu

/** Shift 1 = jam 00–07, Shift 2 = 08–15, Shift 3 = 16–23 (jam lokal, dihitung server) */
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

/** "29 Okt 2026 14:30" (format server, zona user) → Date lokal | null */
const MONTHS = {
    Jan: 0, Feb: 1, Mar: 2, Apr: 3, Mei: 4, May: 4, Jun: 5, Jul: 6,
    Agu: 7, Ags: 7, Aug: 7, Sep: 8, Okt: 9, Oct: 9, Nov: 10, Des: 11, Dec: 11,
};
function parseLastReading(str) {
    const m = /^(\d{1,2}) ([A-Za-z]{3}) (\d{4}) (\d{1,2}):(\d{2})$/.exec((str || "").trim());
    const month = m ? MONTHS[m[2]] : undefined;
    return month === undefined ? null : new Date(+m[3], month, +m[1], +m[4], +m[5]);
}

/** 12483 → "12.4k" */
function fmtCount(n) {
    return n > 9999 ? (n / 1000).toFixed(1) + "k" : String(n);
}

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
            mock: "", // "" = otomatis, "run"/"stop" = paksa status (prototipe)
            targets: loadTargets(),
            online: true,
            lastSync: "",
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

    /** "run" | "stop"; mock menimpa aturan otomatis sampai dikembalikan ke Otomatis */
    get status() {
        if (this.state.mock) return this.state.mock;
        const last = parseLastReading(this.machine?.last_reading);
        return last && Date.now() - last.getTime() < RUNNING_MS ? "run" : "stop";
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

    /** batang grafik; koordinat memakai satuan viewBox 0–100 */
    get bars() {
        const hours = this.shiftHours;
        const list = this.state.hourly.filter((h) => !hours || hours.includes(h.hour));
        const max = Math.max(...list.map((h) => h.count), 1);
        const step = 100 / Math.max(list.length, 1);
        return list.map((h, i) => {
            const height = (h.count / max) * 100;
            return {
                hour: h.hour,
                label: String(h.hour).padStart(2, "0"),
                x: i * step + step * 0.2,
                w: step * 0.6,
                y: 100 - height,
                h: height,
                above: this.targetPerHour && h.count >= this.targetPerHour,
                title: `${String(h.hour).padStart(2, "0")}:00 — ${h.count} bacaan`,
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
            this.state.lastSync = new Date().toTimeString().slice(0, 8);
            this.state.online = true;
        } catch {
            if (seq !== this._seq) return;
            this.state.online = false; // data terakhir tetap tampil
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
    }
}

registry.category("actions").add("forgetrack.dashboard", ItemDashboard);
