/* Overview tab: KPI cards + main forecast chart (history, P50, P10-P90 band). */
(function () {
  "use strict";
  const G = window.GsCharts;

  const icon = (path) => `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="${path}"/></svg>`;

  window.Tabs = window.Tabs || {};
  window.Tabs.overview = {
    title: "Overview",
    render(el, data) {
      G.destroyCharts(el);
      const f = data.forecast;
      const peak = f.points.reduce((a, b) => (b.p50 > a.p50 ? b : a));
      const totalKwh = Math.round(f.points.reduce((a, p) => a + p.p50, 0) * 0.5);
      const mae = data.metrics ? data.metrics.last_7_days_mae : null;
      const nAlerts = data.alerts ? data.alerts.length : 0;

      el.innerHTML = `
        <div class="kpi-grid">
          ${kpi("Next-24 h peak", peak.p50, "kW", G.fmtTime(peak.timestamp), icon("M4 18a8 8 0 0 1 16 0M12 18V9"))}
          ${kpi("Total next 24 h", totalKwh, "kWh", "sum of P50 slots", icon("M3 12h4l3-7 4 14 3-7h4"))}
          ${kpi("Last-7-day MAE", mae ?? "—", "kW", mae != null ? "walk-forward, live" : "metrics unavailable", icon("M12 3v18m8-9H4"))}
          ${kpi("Active alerts", nAlerts, "", `${nAlerts ? "need attention" : "all clear"}`, icon("M12 4a6 6 0 0 0-6 6v3.5L4 17h16l-2-3.5V10a6 6 0 0 0-6-6z"))}
        </div>

        <div class="card">
          <div class="card-head">
            <h2>Next-24 h demand forecast</h2>
            <span class="card-sub">${f.level === "portfolio" ? "Portfolio" : `${f.level} ${f.entity_id}`} · P50 dashed · P10–P90 band · Australia/Sydney</span>
            <div class="card-actions">
              <button class="btn" type="button" data-act="table">Data table</button>
              <button class="btn primary" type="button" data-act="csv">Download CSV</button>
            </div>
          </div>
          <div class="chart-wrap tall chart-box"><canvas id="ovChart" role="img" aria-label="24 hour demand forecast with uncertainty band"></canvas></div>
          <div id="ovTable" hidden style="margin-top:14px"></div>
        </div>`;

      const threshold = data.alerts?.find((a) => a.type === "peak")?.threshold ?? null;
      G.regChart(el, G.forecastChart(el.querySelector("#ovChart"), f, { threshold }));

      // hero KPI: demand sparkline (history + P50 forecast)
      const hero = el.querySelector(".kpi-grid .kpi");
      if (hero) hero.insertAdjacentHTML("beforeend", '<canvas class="kpi-spark" id="ovSpark" aria-hidden="true"></canvas>');
      const sp = el.querySelector("#ovSpark");
      if (sp) G.sparkline(sp, f.history.map((h) => h.actual).concat(f.points.map((p) => p.p50)), f.history.length);

      el.querySelector('[data-act="csv"]').addEventListener("click", () => {
        const blob = new Blob([Api.forecastCsv(f)], { type: "text/csv" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `gridsight_${f.run_id}_${f.level}_${f.entity_id}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
      });
      el.querySelector('[data-act="table"]').addEventListener("click", (e) => {
        const box = el.querySelector("#ovTable");
        if (box.hidden) box.innerHTML = forecastTable(f);
        box.hidden = !box.hidden;
        e.target.textContent = box.hidden ? "Data table" : "Hide table";
      });
    },
  };

  function kpi(label, value, unit, sub, ic) {
    return `<div class="card kpi">
      <div class="kpi-icon">${ic}</div>
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}<span class="unit">${unit || ""}</span></div>
      <div class="kpi-sub">${sub}</div>
    </div>`;
  }

  function forecastTable(f) {
    const rows = f.points.map((p) =>
      `<tr><td class="num">${G.fmtTime(p.timestamp)}</td><td class="num">${p.slot}</td><td class="num">${p.p10}</td><td class="num">${p.p50}</td><td class="num">${p.p90}</td></tr>`).join("");
    return `<div class="table-scroll" style="max-height:300px"><table class="data" caption="Next 24 h, 48 half-hour slots (kW)">
      <thead><tr><th>Time (AEST/AEDT)</th><th class="num">Slot</th><th class="num">P10</th><th class="num">P50</th><th class="num">P90</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }
})();
