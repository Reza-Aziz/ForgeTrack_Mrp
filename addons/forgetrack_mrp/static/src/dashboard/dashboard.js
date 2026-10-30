/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

/** "2026-10-29T14:30" (datetime-local) → "2026-10-29 14:30:00" (UTC server) */
function toServerDate(val) {
    return val ? new Date(val).toISOString().slice(0, 19).replace("T", " ") : "";
}

/** Date → nilai untuk input datetime-local, dalam zona waktu browser */
function localInput(d) {
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
        .toISOString().slice(0, 16);
}

class ItemDashboard extends Component {
    static template = "forgetrack_mrp.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            cards: [],
            from: localInput(new Date(new Date().setHours(0, 0, 0, 0))),
            to: "",
        });
        onWillStart(() => this.load());
    }

    get domain() {
        const domain = [];
        if (this.state.from) {
            domain.push(["reading_time", ">=", toServerDate(this.state.from)]);
        }
        if (this.state.to) {
            domain.push(["reading_time", "<=", toServerDate(this.state.to)]);
        }
        return domain;
    }

    async load() {
        this.state.cards = await this.orm.silent.call(
            "forgetrack.machine.reading", "get_summary", [this.domain]);
    }

    setPreset(days) {
        const now = new Date();
        const from = new Date(now);
        if (days === 0) {
            from.setHours(0, 0, 0, 0);
            this.state.to = "";
        } else {
            from.setDate(now.getDate() - days);
            const to = new Date(now);
            to.setDate(to.getDate() + 1);
            this.state.to = localInput(to);
        }
        this.state.from = localInput(from);
        this.load();
    }
}

actionRegistry.add("forgetrack.dashboard", ItemDashboard);
