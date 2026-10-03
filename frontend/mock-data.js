/* GridSight mock data layer.
 * Used when MOCK mode is on and the sample JSON files cannot be fetched
 * (e.g. page opened via file:// instead of a local server).
 * Numbers are generated with the SAME formula as scripts/generate_samples.ps1,
 * so they match contracts/sample/*.json exactly.
 */
(function () {
  "use strict";

  const r1 = (x) => Math.round(x * 10) / 10;
  const r2 = (x) => Math.round(x * 100) / 100;
  const ts = (d, s) => `2013-02-${String(d).padStart(2, "0")}T${String(Math.floor(s / 2)).padStart(2, "0")}:${s % 2 ? "30" : "00"}:00+11:00`;

  function p50(s) {
    const h = s / 2;
    return r1(124
      + 10 * Math.exp(-((h - 8.5) ** 2) / 8)
      + 14 * Math.exp(-((h - 13.5) ** 2) / 10)
      + 55 * Math.exp(-((h - 18.5) ** 2) / 6)
      + 1.5 * Math.sin(s * 1.9 + 1.0));
  }
  function p50h(s) {
    const h = s / 2;
    return r1(122
      + 8 * Math.exp(-((h - 8.5) ** 2) / 8)
      + 10 * Math.exp(-((h - 13.5) ** 2) / 10)
      + 42 * Math.exp(-((h - 19) ** 2) / 6)
      + 1.6 * Math.sin(s * 1.7 + 0.5));
  }
  function bandW(s) {
    const h = s / 2;
    return 8 + 30 * Math.exp(-((h - 18.5) ** 2) / 6);
  }

  const points = [];
  const history = [];
  for (let s = 0; s < 48; s++) {
    const mid = p50(s), w = bandW(s);
    points.push({ slot: s, timestamp: ts(15, s), p10: r1(mid - 0.475 * w), p50: mid, p90: r1(mid + 0.525 * w) });
    history.push({ timestamp: ts(14, s), actual: p50h(s) });
  }

  const forecast = {
    run_id: "2013-02-15T00-00",
    origin_time: "2013-02-15T00:00:00+11:00",
    level: "portfolio", entity_id: "all", unit: "kW", slot_minutes: 30,
    model_version: "ensemble-v1", weather_source: "open-meteo",
    points, history,
  };

  const peakSlot = points.reduce((a, b) => (b.p50 > a.p50 ? b : a));
  const peakVal = peakSlot.p50;
  const bandWPeak = r1(peakSlot.p90 - peakSlot.p10);
  const ramp = r1(peakVal - points[34].p50);

  const alerts = [
    { id: "a1", type: "peak", severity: "warn", level: "portfolio", entity_id: "all",
      window_start: "2013-02-15T18:00:00+11:00", window_end: "2013-02-15T20:00:00+11:00",
      value: peakVal, threshold: 170.0, message: "Evening peak above threshold" },
    { id: "a2", type: "ramp", severity: "warn", level: "portfolio", entity_id: "all",
      window_start: "2013-02-15T17:00:00+11:00", window_end: "2013-02-15T18:30:00+11:00",
      value: ramp, threshold: 12.0, message: `Evening ramp +${ramp} kW over 3 slots as solar drops` },
    { id: "a3", type: "heatwave", severity: "warn", level: "portfolio", entity_id: "all",
      window_start: "2013-02-15T12:00:00+11:00", window_end: "2013-02-15T16:00:00+11:00",
      value: 36.0, threshold: 32.0, message: "Apparent temperature 36 C exceeds heatwave threshold" },
    { id: "a4", type: "low_confidence", severity: "info", level: "portfolio", entity_id: "all",
      window_start: "2013-02-15T17:30:00+11:00", window_end: "2013-02-15T20:30:00+11:00",
      value: bandWPeak, threshold: 30.0, message: `P10-P90 band ${bandWPeak} kW wide at the evening peak` },
  ];

  // Tariff (assumption): off-peak 22:00-07:00, peak 14:00-20:00, else shoulder.
  const price = (s) => {
    const h = Math.floor(s / 2);
    return (h >= 22 || h < 7) ? 0.12 : (h >= 14 && h < 20) ? 0.42 : 0.24;
  };

  // Battery plan (assumption): 100 kWh, 20 kW, 90% efficient, SoC 10-90% of cap, start 60.
  const cap = 100, pmax = 20, eff = 0.9, socMin = 10;
  let soc = 60;
  const slots = [];
  let sumB = 0, sumA = 0;
  for (let s = 0; s < 48; s++) {
    let charge = 0, discharge = 0;
    if (s >= 44) charge = pmax;                                  // 22:00+ off-peak
    else if (s <= 6 && soc < cap) charge = pmax;                 // 00:00-03:30
    if (s >= 34 && s <= 39 && soc > socMin) discharge = pmax;     // 17:00-19:30 peak
    if (soc + charge * 0.5 * eff > cap) charge = Math.round(((cap - soc) / (0.5 * eff)) * 10) / 10;
    if (soc - discharge * 0.5 < socMin) discharge = Math.round((soc - socMin) / 0.5 * 10) / 10;
    const gb = p50(s);
    const ga = r1(gb - discharge + charge);
    slots.push({ slot: s, price: price(s), grid_before_kw: gb, grid_after_kw: ga,
      battery_charge_kw: r1(charge), battery_discharge_kw: r1(discharge), soc_kwh: r1(soc) });
    sumB += gb * price(s) * 0.5; sumA += ga * price(s) * 0.5;
    soc = Math.max(socMin, Math.min(cap, soc + charge * 0.5 * eff - discharge * 0.5));
  }
  const costBefore = r2(sumB), costAfter = r2(sumA), saving = r2(sumB - sumA);
  const peakBefore = r1(Math.max(...slots.map((x) => x.grid_before_kw)));
  const peakAfter = r1(Math.max(...slots.map((x) => x.grid_after_kw)));

  const plan = {
    mode: "advisory", assumptions: "Illustrative tariff and battery values",
    slots,
    cost_before: costBefore, cost_after: costAfter, saving,
    peak_before_kw: peakBefore, peak_after_kw: peakAfter,
    generator_recommendation: [
      { slot: 28, message: "Generator (A$0.30/kWh assumption) cheaper than peak grid price A$0.42 - start for peak window" },
      { slot: 36, message: "Generator still cheaper than grid for this slot" },
      { slot: 39, message: "Last slot where generator beats grid price; stop at 20:00" },
    ],
  };

  const byHour = [];
  for (let h = 0; h < 24; h++) {
    byHour.push({ hour: h, mae: r1(8.0 + 4 * Math.exp(-((h - 18.5) ** 2) / 4) + 0.5 * Math.sin(h)) });
  }
  const metrics = {
    scope: "walk_forward_backtest",
    by_model: [
      { model: "seasonal_naive", mae: 12.4, rmse: 16.0, nmae: 0.098, skill: 0.0 },
      { model: "weekly_naive", mae: 11.9, rmse: 15.2, nmae: 0.094, skill: 0.04 },
      { model: "ridge", mae: 11.2, rmse: 14.5, nmae: 0.089, skill: 0.10 },
      { model: "lightgbm", mae: 10.6, rmse: 13.9, nmae: 0.084, skill: 0.14 },
      { model: "ensemble", mae: 9.8, rmse: 13.1, nmae: 0.077, skill: 0.21 },
    ],
    by_hour: byHour,
    by_weekday: [9.5, 9.2, 9.0, 9.4, 10.8, 8.8, 8.2].map((mae, weekday) => ({ weekday, mae })),
    coverage_p10_p90: 0.79,
    last_7_days_mae: 10.2,
  };

  const totalKwh = r1(points.reduce((a, p) => a + p.p50, 0) * 0.5);
  const explainContext = {
    run_id: "2013-02-15T00-00",
    peak: { time: peakSlot.timestamp, p50_kw: peakVal, p90_kw: peakSlot.p90 },
    total_kwh_next_24h: totalKwh,
    drivers: ["Hot afternoon (max 36 C)", "Weekday evening", "Low solar after 17:00"],
    band_width_note: "P10-P90 band is widest at the evening peak",
    accuracy_last_7_days: { mae_kw: 10.2, skill_vs_naive: 0.21 },
    alerts_summary: ["1 peak alert (warn)", "1 ramp alert (warn)", "1 heatwave alert (warn)", "1 low-confidence alert (info)"],
    plan_summary: { saving, peak_reduction_kw: r1(peakBefore - peakAfter) },
  };

  const entities = { portfolio: ["all"], zone: ["2000", "2010", "2020", "2030"], house: ["1", "2", "3"] };

  const runs = [
    { run_id: "2013-02-15T00-00", origin_time: "2013-02-15T00:00:00+11:00", created_at: "2013-02-15T00:00:42+11:00" },
    { run_id: "2013-02-14T00-00", origin_time: "2013-02-14T00:00:00+11:00", created_at: "2013-02-14T00:00:38+11:00" },
  ];

  // Zone / house forecasts are derived deterministically from the portfolio curve.
  const factors = { "2000": 0.34, "2010": 0.28, "2020": 0.22, "2030": 0.16, "1": 0.09, "2": 0.07, "3": 0.05 };

  function deriveForecast(level, entityId, runId) {
    if (runId && runId !== "2013-02-15T00-00") return null; // older mock runs have no data -> empty state
    if (level === "portfolio" && entityId === "all") return structuredClone(forecast);
    const f = factors[entityId] ?? 0.2;
    const scale = (x) => (level === "house" ? r1(x * f) : r1(x * f));
    return structuredClone({
      ...forecast,
      level, entity_id: entityId,
      points: points.map((p) => ({ ...p, p10: scale(p.p10), p50: scale(p.p50), p90: scale(p.p90) })),
      history: history.map((h) => ({ ...h, actual: scale(h.actual) })),
    });
  }

  // Deterministic "template" answers - the mock never has an LLM.
  function mockChat(question, data) {
    const q = question.toLowerCase();
    const c = data.context || explainContext;
    const t = (iso) => new Date(iso).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Australia/Sydney" });
    let answer;
    if (q.includes("peak") || q.includes("high")) {
      answer = `The evening peak is forecast at ${c.peak.p50_kw} kW (P50) around ${t(c.peak.time)}, up to ${c.peak.p90_kw} kW at P90. Drivers in this run: ${c.drivers.join("; ")}. The band is widest at the evening peak, so treat the exact timing with some uncertainty.`;
    } else if (q.includes("risk")) {
      answer = `The biggest risk tomorrow is the evening peak: P90 reaches ${c.peak.p90_kw} kW at ${t(c.peak.time)}, and the P10-P90 band is widest there. There is ${c.alerts_summary[0]} and ${c.alerts_summary[2]}, so expect AC load to push the peak higher if it gets hotter.`;
    } else if (q.includes("save") || q.includes("battery") || q.includes("plan")) {
      answer = `The battery plan (advisory, assumption-based) charges during off-peak slots and discharges from 17:00-19:30. Estimated saving is A$${c.plan_summary.saving.toFixed(2)} per day and the grid peak drops by ${c.plan_summary.peak_reduction_kw} kW (${data.plan ? data.plan.peak_before_kw : "?"} -> ${data.plan ? data.plan.peak_after_kw : "?"} kW). Tariff and battery values are assumptions.`;
    } else if (q.includes("accurat") || q.includes("yesterday") || q.includes("error")) {
      answer = `Over the last 7 days the MAE was ${c.accuracy_last_7_days.mae_kw} kW, a skill score of ${c.accuracy_last_7_days.skill_vs_naive} vs seasonal-naive (positive means better). P10-P90 coverage in the backtest is ${(data.metrics ? data.metrics.coverage_p10_p90 : 0.79) * 100}%, close to the 80% target.`;
    } else {
      answer = `I can only explain pre-computed results. Run ${c.run_id}: peak ${c.peak.p50_kw} kW at ${t(c.peak.time)}, ${c.total_kwh_next_24h} kWh expected over 24 h, battery plan saving A$${c.plan_summary.saving.toFixed(2)}, ${c.alerts_summary.length} active alerts. Ask about the peak, risks, the battery plan or accuracy for more detail.`;
    }
    return { answer, used_llm: false };
  }

  window.MockData = {
    deriveForecast,
    alerts, metrics, plan, entities, runs,
    get explainContext() { return explainContext; },
    mockChat,
  };
})();
