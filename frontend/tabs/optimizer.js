/* Optimizer tab: before/after grid import, battery SoC, cost cards, generator notes. */
(function () {
  "use strict";
  const G = window.GsCharts;
  window.Tabs = window.Tabs || {};

  window.Tabs.optimizer = {
    title: "Optimizer",
    render(el, data) {
      G.destroyCharts(el);
      const p = data.plan;
      if (!p || !p.slots || !p.slots.length) {
        el.innerHTML = stateWrap("No battery plan yet", "The optimizer has not produced a plan for this run. It runs against the P50 forecast, tariff and battery assumptions after each forecast cycle.");
        return;
      }
      const origin = data.forecast ? data.forecast.origin_time : null;
      const peakCut = p.peak_before_kw - p.peak_after_kw;
      const peakPct = p.peak_before_kw ? Math.round((peakCut / p.peak_before_kw) * 100) : 0;

      el.innerHTML = `
        <div class="kpi-grid">
          ${card("Cost before", `A$${p.cost_before.toFixed(2)}`, "24 h grid energy")}
          ${card("Cost after plan", `A$${p.cost_after.toFixed(2)}`, "with battery dispatch")}
          ${card("Estimated saving", `A$${p.saving.toFixed(2)}`, p.saving > 0 ? "per day vs do-nothing" : "advisory plan inactive")}
          ${card("Peak reduction", `${peakCut.toFixed(1)} kW`, `${p.peak_before_kw} -> ${p.peak_after_kw} kW (${peakPct}%)`)}
        </div>

        <div class="card">
          <div class="card-head">
            <h2>Grid import: before vs after</h2>
            <span class="card-sub">tariff windows shaded · bars = battery charge (up) / discharge (down)</span>
            <span class="assumption-note">Tariff &amp; battery values are assumptions · Advisory only</span>
          </div>
          <div class="chart-wrap chart-box"><canvas id="optGrid" role="img" aria-label="Grid import before and after battery plan"></canvas></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head"><h2>Battery state of charge</h2><span class="card-sub">kWh · advisory dispatch</span></div>
            <div class="chart-wrap short chart-box"><canvas id="optSoc" role="img" aria-label="Battery state of charge over 24 hours"></canvas></div>
          </div>
          <div class="card">
            <div class="card-head"><h2>Generator vs grid</h2><span class="card-sub">slots where running the generator is cheaper</span></div>
            ${p.generator_recommendation && p.generator_recommendation.length ? `
              <ul class="gen-list">
                ${p.generator_recommendation.map((g) => `<li><strong class="mono">${G.fmtTime(`${pSlotIso(origin, g.slot)}`)}</strong> · ${g.message}</li>`).join("")}
              </ul>` : `<div class="state" style="padding:28px"><p>No slots where the generator beats grid price under the current assumptions.</p></div>`}
            <p class="card-sub" style="margin-top:10px">Generator cost and tariff are assumptions; nothing is switched on automatically.</p>
          </div>
        </div>`;

      G.regChart(el, G.gridChart(el.querySelector("#optGrid"), p, origin));
      G.regChart(el, G.socChart(el.querySelector("#optSoc"), p, origin));
    },
  };

  function card(label, value, sub) {
    return `<div class="card kpi">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-sub">${sub}</div>
    </div>`;
  }

  function pSlotIso(origin, slot) {
    const base = origin ? new Date(origin) : new Date("2013-02-15T00:00:00+11:00");
    return new Date(base.getTime() + slot * 30 * 60000).toISOString();
  }

  function stateWrap(title, sub) {
    return `<div class="card"><div class="state">
      <h3>${title}</h3><p>${sub}</p>
    </div></div>`;
  }
})();
