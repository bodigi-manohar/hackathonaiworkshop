/* Accuracy tab: model comparison, MAE by hour / weekday, P10-P90 coverage. */
(function () {
  "use strict";
  const G = window.GsCharts;
  const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  window.Tabs = window.Tabs || {};

  window.Tabs.accuracy = {
    title: "Accuracy",
    render(el, data) {
      G.destroyCharts(el);
      const m = data.metrics;
      if (!m) {
        el.innerHTML = `<div class="card"><div class="state"><h3>No metrics yet</h3><p>Run a walk-forward backtest to populate model comparison, hourly error and coverage.</p></div></div>`;
        return;
      }
      const best = [...m.by_model].sort((a, b) => b.skill - a.skill)[0];
      const coverage = m.coverage_p10_p90;

      el.innerHTML = `
        <div class="kpi-grid">
          ${kpi("Walk-forward MAE", best ? best.mae : "—", "kW", best ? `best model: ${best.model}` : "")}
          ${kpi("Skill vs seasonal-naive", best ? best.skill : "—", "", best ? "positive = better than baseline" : "")}
          ${kpi("P10–P90 coverage", `${Math.round(coverage * 100)}%`, "of actuals in band", "target 75–85%")}
          ${kpi("Last-7-day MAE", m.last_7_days_mae ?? "—", "kW", "live replay window")}
        </div>

        <div class="card">
          <div class="card-head"><h2>Model comparison</h2><span class="card-sub">walk-forward backtest · lower MAE is better</span></div>
          <div class="table-scroll" style="max-height:none">
            <table class="data">
              <caption>Models vs baselines on the walk-forward backtest</caption>
              <thead><tr><th>Model</th><th class="num">MAE (kW)</th><th class="num">RMSE (kW)</th><th class="num">nMAE</th><th class="num">Skill vs naive</th></tr></thead>
              <tbody>
                ${[...m.by_model].sort((a, b) => a.mae - b.mae).map((r) =>
                  `<tr class="${r.model === best.model ? "best" : ""}">
                    <td>${r.model}${r.model === best.model ? " <span style='color:var(--primary);font-weight:600'>● best</span>" : ""}</td>
                    <td class="num">${r.mae}</td><td class="num">${r.rmse}</td>
                    <td class="num">${(r.nmae * 100).toFixed(1)}%</td><td class="num">${r.skill > 0 ? "+" : ""}${r.skill.toFixed(2)}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div class="card-head"><h2>MAE by hour of day</h2><span class="card-sub">kW · error is highest on the evening ramp</span></div>
            <div class="chart-wrap short chart-box"><canvas id="accHour" role="img" aria-label="Mean absolute error by hour of day"></canvas></div>
          </div>
          <div class="card">
            <div class="card-head"><h2>MAE by weekday</h2><span class="card-sub">kW · weekends are easier to predict</span></div>
            <div class="chart-wrap short chart-box"><canvas id="accWd" role="img" aria-label="Mean absolute error by weekday"></canvas></div>
          </div>
        </div>`;

      const hours = m.by_hour.map((h) => h.hour);
      const hVals = m.by_hour.map((h) => h.mae);
      const hPeak = hVals.indexOf(Math.max(...hVals));
      const wVals = m.by_weekday.map((w) => w.mae);
      G.regChart(el, G.barChart(el.querySelector("#accHour"), hours.map(String), hVals, "kW", hPeak));
      G.regChart(el, G.barChart(el.querySelector("#accWd"), m.by_weekday.map((w) => WD[w.weekday] ?? `day ${w.weekday}`), wVals, "kW", wVals.indexOf(Math.max(...wVals))));
    },
  };

  function kpi(label, value, unit, sub) {
    return `<div class="card kpi">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}${unit ? `<span class="unit">${unit}</span>` : ""}</div>
      <div class="kpi-sub">${sub}</div>
    </div>`;
  }
})();
