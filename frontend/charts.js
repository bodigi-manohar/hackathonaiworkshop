/* GridSight chart helpers (Chart.js 4, UMD from cdnjs).
 * "Aurora Grid" conventions: actuals = solid electric cyan (neon glow),
 * forecast P50 = dashed warm amber, P10–P90 = ~15% amber fill.
 * Cyan/amber pair is colour-blind safe; series also differ by dash style.
 * All colours flow from the CSS tokens in styles.css.
 */
(function () {
  "use strict";

  const TZ = "Australia/Sydney";
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  function palette() {
    return {
      actual: css("--chart-actual"),
      forecast: css("--chart-forecast"),
      band: css("--chart-band"),
      grid: css("--chart-grid"),
      muted: css("--muted"),
      text: css("--ink"),
      success: css("--chart-success"),
      before: css("--chart-before"),
      warn: css("--warn"),
      critical: css("--critical"),
    };
  }

  function baseOptions(unit) {
    const c = palette();
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      animation: { duration: 800, easing: "easeOutQuart" },
      plugins: {
        legend: {
          labels: { color: c.muted, usePointStyle: true, pointStyle: "line", boxWidth: 26, font: { family: css("--font-sans"), size: 12, weight: "700" } },
        },
        tooltip: {
          backgroundColor: "rgba(11,14,44,0.94)",
          titleColor: "#eef0ff",
          bodyColor: "#eef0ff",
          borderColor: "rgba(146,164,255,0.35)",
          borderWidth: 1,
          titleFont: { family: css("--font-sans"), size: 12, weight: "700" },
          bodyFont: { family: css("--font-mono"), size: 12 },
          padding: 12, cornerRadius: 12, displayColors: true, boxPadding: 4, caretSize: 6,
          shadowColor: "rgba(2,4,24,0.55)", shadowBlur: 24, shadowOffsetY: 8,
          callbacks: { label: (ctx) => ctx.dataset.label == null ? "" : ` ${ctx.dataset.label}: ${ctx.parsed.y == null ? "-" : `${ctx.parsed.y} ${unit}`}` },
        },
      },
      scales: {
        x: { grid: { color: c.grid }, ticks: { color: c.muted, font: { family: css("--font-mono"), size: 10.5 }, maxTicksLimit: 12, maxRotation: 0 } },
        y: { grid: { color: c.grid }, title: { display: true, text: unit, color: c.muted, font: { family: css("--font-sans"), size: 11, weight: "700" } }, ticks: { color: c.muted, font: { family: css("--font-mono"), size: 11 } } },
      },
    };
  }

  // Neon glow behind specific datasets (by index via options.plugins.gsGlow).
  const lineGlow = {
    id: "gsGlow",
    beforeDatasetDraw(chart, args) {
      const g = chart.options.plugins.gsGlow && chart.options.plugins.gsGlow[args.index];
      if (!g) return;
      const ctx = chart.ctx;
      ctx.save();
      ctx.shadowColor = g.color;
      ctx.shadowBlur = g.blur || 8;
    },
    afterDatasetDraw(chart, args) {
      if (chart.options.plugins.gsGlow && chart.options.plugins.gsGlow[args.index]) chart.ctx.restore();
    },
  };

  // Vertical line at the forecast origin ("now") + label.
  const nowLine = {
    id: "gsNowLine",
    afterDraw(chart) {
      const idx = chart.options.plugins.gsNowLine?.index;
      if (idx == null) return;
      const { ctx, chartArea: a, scales } = chart;
      const x = scales.x.getPixelForValue(idx);
      ctx.save();
      const glow = css("--primary-glow") || "rgba(34,211,238,0.5)";
      ctx.strokeStyle = glow;
      ctx.shadowColor = glow; ctx.shadowBlur = 8;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.setLineDash([]);
      ctx.font = `700 10px ${css("--font-sans")}`;
      ctx.fillStyle = css("--primary") || "#22d3ee";
      ctx.shadowColor = glow; ctx.shadowBlur = 10;
      ctx.textAlign = "left";
      ctx.fillText("NOW", x + 5, a.top + 10);
      ctx.restore();
    },
  };

  // Horizontal threshold line with a right-aligned label.
  const thresholdLine = {
    id: "gsThreshold",
    afterDatasetsDraw(chart) {
      const t = chart.options.plugins.gsThreshold;
      if (!t) return;
      const { ctx, chartArea: a, scales } = chart;
      const y = scales.y.getPixelForValue(t.value);
      ctx.save();
      ctx.strokeStyle = t.color; ctx.setLineDash([6, 4]); ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = `700 10px ${css("--font-sans")}`;
      ctx.fillStyle = t.color; ctx.textAlign = "right";
      ctx.fillText(t.label, a.right - 4, y - 5);
      ctx.restore();
    },
  };

  // Peak marker: ring + label above the peak point.
  const peakMarker = {
    id: "gsPeak",
    afterDatasetsDraw(chart) {
      const m = chart.options.plugins.gsPeak;
      if (!m) return;
      const { ctx, scales } = chart;
      const x = scales.x.getPixelForValue(m.index);
      const y = scales.y.getPixelForValue(m.value);
      ctx.save();
      ctx.strokeStyle = m.color; ctx.lineWidth = 2;
      ctx.shadowColor = m.color; ctx.shadowBlur = 8;
      ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.font = `700 11px ${css("--font-mono")}`;
      ctx.fillStyle = m.color; ctx.textAlign = "center";
      ctx.shadowColor = m.color; ctx.shadowBlur = 8;
      ctx.fillText(m.label, x, y - 12);
      ctx.restore();
    },
  };

  // Tariff window shading behind the optimizer chart.
  const tariffBands = {
    id: "gsTariffBands",
    beforeDatasetsDraw(chart) {
      const bands = chart.options.plugins.gsTariffBands;
      if (!bands) return;
      const { ctx, chartArea: a, scales } = chart;
      ctx.save();
      for (const b of bands) {
        const x0 = scales.x.getPixelForValue(Math.max(0, b.from - 0.5));
        const x1 = scales.x.getPixelForValue(Math.min(bands.length ? 47 : 0, b.to + 0.5));
        ctx.fillStyle = b.color;
        ctx.fillRect(x0, a.top, x1 - x0, a.bottom - a.top);
      }
      ctx.restore();
    },
  };

  /** Main forecast chart: history (solid) + p50 (dashed) + p10-p90 band. */
  function forecastChart(canvas, forecast, opts = {}) {
    const c = palette();
    const labels = [...forecast.history.map((h) => h.timestamp), ...forecast.points.map((p) => p.timestamp)];
    const labelsHH = labels.map((t) => fmtTime(t));
    const pad = new Array(forecast.history.length).fill(null); // forecast starts at the NOW index

    const peak = forecast.points.reduce((a, b) => (b.p50 > a.p50 ? b : a));
    const data = {
      labels: labelsHH,
      datasets: [
        { label: "Actuals (prev 24 h)", data: forecast.history.map((h) => h.actual), borderColor: c.actual, borderWidth: 2.25, pointRadius: 0, tension: 0.25, order: 3 },
        { label: "P90", data: [...pad, ...forecast.points.map((p) => p.p90)], borderColor: "transparent", borderWidth: 0, pointRadius: 0, order: 1, fill: false },
        { label: "P10–P90 band", data: [...pad, ...forecast.points.map((p) => p.p10)], borderColor: "transparent", borderWidth: 0, pointRadius: 0, backgroundColor: c.band, fill: "-1", order: 2 },
        { label: "Forecast P50", data: [...pad, ...forecast.points.map((p) => p.p50)], borderColor: c.forecast, borderWidth: 2.25, borderDash: [6, 4], pointRadius: 0, tension: 0.25, order: 4 },
      ],
    };
    const o = baseOptions(forecast.unit || "kW");
    o.plugins.gsGlow = { 0: { color: "rgba(34,211,238,0.55)", blur: 10 }, 3: { color: "rgba(251,191,36,0.5)", blur: 8 } };
    o.plugins.gsNowLine = { index: forecast.history.length };
    o.plugins.gsPeak = { index: forecast.history.length + peak.slot, value: peak.p50, color: c.forecast, label: `Peak ${peak.p50} kW` };
    if (opts.threshold != null) {
      o.plugins.gsThreshold = { value: opts.threshold, label: `Threshold ${opts.threshold} kW`, color: c.critical };
    }
    return new Chart(canvas, {
      type: "line",
      data, options: o,
      plugins: [lineGlow, nowLine, thresholdLine, peakMarker],
    });
  }

  /** Optimizer: grid import before/after + charge/discharge bars + tariff shading. */
  function gridChart(canvas, plan, originIso) {
    const c = palette();
    const labels = slotLabels(plan.slots.length, originIso);
    const o = baseOptions("kW");
    o.plugins.gsTariffBands = tariffBandsOf(plan);
    const data = {
      labels,
      datasets: [
        { label: "Grid import (before)", data: plan.slots.map((s) => s.grid_before_kw), borderColor: c.before, borderWidth: 1.75, pointRadius: 0, tension: 0.25, order: 4 },
        { label: "Grid import (after plan)", data: plan.slots.map((s) => s.grid_after_kw), borderColor: c.success, borderWidth: 2.25, pointRadius: 0, tension: 0.25, order: 3 },
        { label: "Battery charging", data: plan.slots.map((s) => s.battery_charge_kw), type: "bar", backgroundColor: "rgba(34,211,238,0.5)", stack: "bat", order: 1 },
        { label: "Battery discharging", data: plan.slots.map((s) => -s.battery_discharge_kw), type: "bar", backgroundColor: "rgba(251,191,36,0.55)", stack: "bat", order: 2 },
      ],
    };
    return new Chart(canvas, { type: "line", data, options: o, plugins: [tariffBands] });
  }

  /** Battery state of charge. */
  function socChart(canvas, plan, originIso) {
    const c = palette();
    const o = baseOptions("kWh");
    const cap = Math.ceil(Math.max(20, ...plan.slots.map((s) => s.soc_kwh)) / 20) * 20;
    o.scales.y.max = cap; o.scales.y.min = 0;
    o.plugins.gsTariffBands = tariffBandsOf(plan);
    const data = {
      labels: slotLabels(plan.slots.length, originIso),
      datasets: [
        {
          label: "Battery SoC", data: plan.slots.map((s) => s.soc_kwh),
          borderColor: c.actual, borderWidth: 2.25, pointRadius: 0, tension: 0.25,
          fill: true, backgroundColor: "rgba(34,211,238,0.10)",
        },
      ],
    };
    return new Chart(canvas, { type: "line", data, options: o, plugins: [tariffBands] });
  }

  function tariffBandsOf(plan) {
    const prices = [...new Set(plan.slots.map((s) => s.price))].sort((a, b) => a - b);
    const names = prices.length >= 3 ? ["off-peak", "shoulder", "peak"] : ["off-peak", "peak"];
    const colors = ["rgba(34,211,238,0.06)", "rgba(146,164,255,0.05)", "rgba(251,191,36,0.10)"];
    return prices.map((p, i) => {
      const idx = plan.slots.map((s) => s.price).indexOf(p);
      const last = plan.slots.map((s) => s.price).lastIndexOf(p);
      return { from: idx, to: last, color: colors[i] ?? colors[1], label: `${names[i]} A$${p.toFixed(2)}` };
    });
  }

  /** Simple bar chart (MAE by hour / weekday). */
  function barChart(canvas, labels, values, unit, highlightIdx) {
    const c = palette();
    const o = baseOptions(unit);
    o.plugins.legend.display = false;
    o.plugins.tooltip.callbacks.label = (ctx) => ` ${ctx.parsed.y} ${unit}`;
    const data = {
      labels,
      datasets: [{
        data: values,
        backgroundColor: values.map((_, i) => i === highlightIdx ? c.forecast : "rgba(34,211,238,0.55)"),
        borderRadius: 4, barPercentage: 0.72,
      }],
    };
    return new Chart(canvas, { type: "bar", data, options: o });
  }

  /** Mini sparkline for KPI hero cards: cyan area+line, NOW divider, amber end dot. */
  function sparkline(canvas, values, splitAt) {
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(2.5, window.devicePixelRatio || 1);
    const w = canvas.clientWidth || 260, h = canvas.clientHeight || 40;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.scale(dpr, dpr);
    const min = Math.min(...values), max = Math.max(...values);
    const range = max - min || 1;
    const px = (i) => 2 + (i / (values.length - 1)) * (w - 4);
    const py = (v) => h - 4 - ((v - min) / range) * (h - 12);

    // area fill
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(34,211,238,0.28)");
    grad.addColorStop(1, "rgba(34,211,238,0)");
    ctx.beginPath();
    values.forEach((v, i) => (i ? ctx.lineTo(px(i), py(v)) : ctx.moveTo(px(i), py(v))));
    ctx.lineTo(px(values.length - 1), h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();

    // line
    ctx.beginPath();
    values.forEach((v, i) => (i ? ctx.lineTo(px(i), py(v)) : ctx.moveTo(px(i), py(v))));
    ctx.strokeStyle = css("--chart-actual") || "#22d3ee";
    ctx.lineWidth = 1.75; ctx.lineJoin = "round"; ctx.stroke();

    // "now" divider between history and forecast
    if (splitAt > 0 && splitAt < values.length) {
      const x = px(splitAt);
      ctx.strokeStyle = "rgba(238,240,255,0.35)";
      ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, 2); ctx.lineTo(x, h - 2); ctx.stroke();
      ctx.setLineDash([]);
    }

    // forecast end-point dot (amber, glowing)
    const lx = px(values.length - 1), ly = py(values[values.length - 1]);
    ctx.fillStyle = css("--chart-forecast") || "#fbbf24";
    ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 7;
    ctx.beginPath(); ctx.arc(lx, ly, 2.6, 0, Math.PI * 2); ctx.fill();
    ctx.shadowBlur = 0;
  }

  // ---------- shared utils ----------
  function fmtTime(iso) {
    return new Date(iso).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ });
  }
  function fmtDateTime(iso) {
    return new Date(iso).toLocaleString("en-AU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ });
  }
  function slotLabels(n, originIso) {
    // tz-agnostic: shifts the origin instant and formats in Australia/Sydney
    const base = originIso ? new Date(originIso) : new Date("2013-02-15T00:00:00+11:00");
    return Array.from({ length: n }, (_, i) =>
      new Date(base.getTime() + i * 30 * 60000).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ }));
  }

  /** Destroy all charts registered under an element. */
  function destroyCharts(el) {
    (el._gsCharts || []).forEach((ch) => { try { ch.destroy(); } catch { /* noop */ } });
    el._gsCharts = [];
  }
  function regChart(el, ch) { el._gsCharts = el._gsCharts || []; el._gsCharts.push(ch); }

  window.GsCharts = { forecastChart, gridChart, socChart, barChart, sparkline, destroyCharts, regChart, fmtTime, fmtDateTime, palette };
})();
