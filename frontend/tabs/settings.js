/* Settings tab: read-only thresholds, tariff, battery spec (clearly marked assumptions),
 * data source (mock/live), model + weather provenance. */
(function () {
  "use strict";
  const G = window.GsCharts;
  window.Tabs = window.Tabs || {};

  window.Tabs.settings = {
    title: "Settings",
    render(el, data) {
      const f = data.forecast;
      const p = data.plan;
      const mock = Api.mock;

      // derive contiguous tariff windows from the plan prices
      const origin = f ? f.origin_time : "2013-02-15T00:00:00+11:00";
      const runs = [];
      if (p && p.slots) {
        let cur = null;
        p.slots.forEach((s, i) => {
          if (!cur || cur.price !== s.price) { if (cur) runs.push(cur); cur = { price: s.price, from: i, to: i }; }
          else cur.to = i;
        });
        if (cur) runs.push(cur);
      }
      const prices = [...new Set(runs.map((r) => r.price))].sort((a, b) => a - b);
      const name = (p2) => prices.length >= 3 ? (p2 === prices[0] ? "Off-peak" : p2 === prices[prices.length - 1] ? "Peak" : "Shoulder") : (p2 === prices[0] ? "Off-peak" : "Peak");
      const col = (p2) => p2 === prices[prices.length - 1] && prices.length >= 2 ? "var(--warn)" : p2 === prices[0] ? "var(--chart-actual)" : "var(--muted)";
      const t2 = (slot) => new Date(new Date(origin).getTime() + slot * 30 * 60000)
        .toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Australia/Sydney" });
      const tariff = runs.length
        ? runs.map((r) => `<div class="tariff-row"><span class="dot" style="background:${col(r.price)}"></span>
            <span>${name(r.price)}</span><span class="mono">A$${r.price.toFixed(2)}/kWh</span>
            <span class="mono" style="color:var(--muted)">${t2(r.from)}–${t2(r.to + 1)}</span></div>`).join("")
        : "";

      el.innerHTML = `
        <div class="card">
          <div class="card-head"><h2>Data source</h2></div>
          <dl class="dl">
            <dt>Mode</dt>
            <dd>${mock ? "Mock — reading contracts/sample + embedded data" : "Live — calling FastAPI"}</dd>
            <dt>API base</dt>
            <dd>${mock ? `${Api.apiBase} (not contacted in mock)` : Api.apiBase}</dd>
            <dt>Forecast level / entity</dt>
            <dd>${f ? `${f.level} / ${f.entity_id}` : "—"}</dd>
          </dl>
          <label class="toggle" style="margin-top:14px">
            <input type="checkbox" id="mockToggle" ${mock ? "checked" : ""}>
            <span class="track"></span>
            <span>Use mock data (turn off to use the live API)</span>
          </label>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head"><h2>Provenance</h2><span class="assumption-note">read-only</span></div>
            <dl class="dl">
              <dt>Run ID</dt><dd>${f ? f.run_id : "—"}</dd>
              <dt>Origin time</dt><dd>${f ? G.fmtDateTime(f.origin_time) : "—"}</dd>
              <dt>Model</dt><dd>${f ? f.model_version : "—"}</dd>
              <dt>Weather source</dt><dd>${f ? f.weather_source : "—"}</dd>
              <dt>Slot</dt><dd>${f ? `${f.slot_minutes} min` : "—"}</dd>
              <dt>Timezone</dt><dd>Australia/Sydney</dd>
            </dl>
          </div>

          <div class="card">
            <div class="card-head"><h2>Control state</h2><span class="assumption-note">advisory only</span></div>
            <dl class="dl">
              <dt>Control enabled</dt><dd>no (advisory)</dd>
              <dt>Dry run</dt><dd>yes</dd>
              <dt>Override</dt><dd>POST /control/override available</dd>
            </dl>
            <p class="card-sub" style="margin:12px 0 0">Nothing is executed automatically. Enable bounded automation via config only, with guardrails and a logged manual override.</p>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h2>Alert thresholds</h2><span class="card-sub">from config — assumptions</span></div>
          <dl class="dl">
            <dt>Peak (P50 above X kW)</dt><dd>170 kW</dd>
            <dt>Ramp (ΔY kW within Z slots)</dt><dd>12 kW / 3 slots</dd>
            <dt>Heatwave (apparent temp above)</dt><dd>32 °C</dd>
            <dt>Low confidence (band wider than)</dt><dd>30 kW</dd>
            <dt>Drift (rolling 7-day MAE ÷ train MAE)</dt><dd>1.3×</dd>
          </dl>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head"><h2>Tariff (assumption)</h2></div>
            <div class="tariff-list">${tariff || '<span class="card-sub">No tariff in plan yet.</span>'}</div>
          </div>
          <div class="card">
            <div class="card-head"><h2>Battery (assumption)</h2></div>
            <dl class="dl">
              <dt>Capacity</dt><dd>100 kWh</dd>
              <dt>Max charge / discharge</dt><dd>20 kW</dd>
              <dt>Round-trip efficiency</dt><dd>90%</dd>
              <dt>SoC limits</dt><dd>10 – 100 kWh</dd>
              <dt>Initial SoC</dt><dd>60 kWh</dd>
            </dl>
          </div>
        </div>`;

      el.querySelector("#mockToggle").addEventListener("change", (e) => {
        Api.mock = e.target.checked;
        if (window.Gs) Gs.refresh({ rerender: true });
      });
    },
  };

})();
