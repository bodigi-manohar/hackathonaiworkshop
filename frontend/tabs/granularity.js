/* Granularity tab: portfolio / zone / house forecast + zone comparison table. */
(function () {
  "use strict";
  const G = window.GsCharts;
  window.Tabs = window.Tabs || {};

  window.Tabs.granularity = {
    title: "Granularity",
    render(el, data) {
      G.destroyCharts(el);
      const f = data.forecast;

      el.innerHTML = `
        <div class="card">
          <div class="card-head">
            <h2>Forecast at ${f ? `${cap(f.level)} level${f.entity_id !== "all" ? ` · ${f.entity_id}` : ""}` : "…"}</h2>
            <span class="card-sub">use the Level / Entity selectors above to switch · P50 dashed, P10–P90 band</span>
          </div>
          ${f ? `<div class="chart-wrap chart-box"><canvas id="granChart" role="img" aria-label="Demand forecast at selected granularity level"></canvas></div>`
              : emptyBox()}
        </div>

        <div class="card">
          <div class="card-head"><h2>Zone comparison</h2><span class="card-sub">peak P50 per zone for this run</span></div>
          <div id="zoneTable"></div>
        </div>`;

      if (f) G.regChart(el, G.forecastChart(el.querySelector("#granChart"), f, {}));

      const zones = (data.entities && data.entities.zone || []).slice(0, 10);
      const box = el.querySelector("#zoneTable");
      box.innerHTML = `<div style="display:flex;justify-content:center;padding:30px"><span class="spin"></span></div>`;
      Promise.all(zones.map((z) => Api.getForecast("zone", z, Gs.runId)))
        .then((fc) => {
          const rows = fc
            .filter(Boolean)
            .map((ff) => {
              const peak = ff.points.reduce((a, b) => (b.p50 > a.p50 ? b : a));
              const kwh = Math.round(ff.points.reduce((a, p) => a + p.p50, 0) * 0.5);
              return { zone: ff.entity_id, peak: peak.p50, time: peak.timestamp, kwh };
            })
            .sort((a, b) => b.peak - a.peak);
          el.querySelector("#zoneTable").innerHTML = `
            <div class="table-scroll">
              <table class="data">
                <caption>Peak P50 per zone, this run (kW)</caption>
                <thead><tr><th>Zone</th><th class="num">Peak P50 (kW)</th><th>Peak time</th><th class="num">Total 24 h (kWh)</th></tr></thead>
                <tbody>${rows.map((r) =>
                  `<tr${r.zone === (f && f.level === "zone" ? f.entity_id : null) ? ' class="best"' : ""}>
                   <td>${r.zone}</td><td class="num">${r.peak}</td>
                   <td class="mono">${G.fmtTime(r.time)}</td><td class="num">${r.kwh}</td></tr>`).join("")}
                </tbody>
              </table>
            </div>`;
        })
        .catch(() => {
          box.innerHTML = `<div class="state"><h3>Could not load zone forecasts</h3><p>Zone data is unavailable right now. Try again once the backend is serving /forecast for zones.</p></div>`;
        });
    },
  };

  function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }
  function emptyBox() {
    return `<div class="state"><h3>No forecast for this level</h3><p>Pick a valid entity for the selected level, or switch back to Portfolio.</p></div>`;
  }
})();
