/* Alerts tab: severity-sorted list with icon+text badges (never colour alone). */
(function () {
  "use strict";
  const G = window.GsCharts;
  window.Tabs = window.Tabs || {};

  const SEV = {
    critical: { icon: "M12 3a9 9 0 1 0 .01 0zM12 7.5v5.5m0 3.5v.5", label: "Critical" },
    warn:     { icon: "M12 3 2.5 20h19L12 3zm0 6v5m0 3v.5", label: "Warn" },
    info:     { icon: "M12 3a9 9 0 1 0 .01 0zM12 11v5m0-8v.5", label: "Info" },
  };
  const ORDER = { critical: 0, warn: 1, info: 2 };
  const TYPE_LABEL = { peak: "Peak", ramp: "Ramp", low_confidence: "Low confidence", model_drift: "Model drift", heatwave: "Heatwave" };

  window.Tabs.alerts = {
    title: "Alerts",
    render(el, data) {
      const alerts = [...(data.alerts || [])].sort(
        (a, b) => (ORDER[a.severity] - ORDER[b.severity]) || a.window_start.localeCompare(b.window_start));

      el.innerHTML = `
        <div class="card">
          <div class="card-head">
            <h2>Active alerts</h2>
            <span class="card-sub">${alerts.length} alert${alerts.length === 1 ? "" : "s"} · sorted by severity, then time · Australia/Sydney</span>
          </div>
          ${alerts.length ? `
          <div class="alert-rows" role="list">
            ${alerts.map(row).join("")}
          </div>` : emptyState()}
        </div>`;
    },
  };

  const UNIT = { peak: "kW", ramp: "kW", low_confidence: "kW", model_drift: "ratio", heatwave: "°C apparent" };

  function row(a) {
    const s = SEV[a.severity] || SEV.info;
    const u = UNIT[a.type] || "";
    const v = a.value != null ? `${a.value} ${u}` : "—";
    const t = a.threshold != null ? ` / ${a.threshold} ${u}` : "";
    return `<div class="alert-row" role="listitem">
      <span class="sev ${a.severity}">
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="${s.icon}"/></svg>
        ${s.label}
      </span>
      <span class="alert-type">${TYPE_LABEL[a.type] || a.type}</span>
      <span>
        <span style="font-size:13.5px">${a.message}</span><br>
        <span class="alert-window">${G.fmtTime(a.window_start)} – ${G.fmtTime(a.window_end)} · ${a.level} ${a.entity_id}</span>
      </span>
      <span class="alert-nums"><strong>${v}</strong>${t}</span>
    </div>`;
  }

  function emptyState() {
    return `<div class="state">
      <span class="state-icon"><svg viewBox="0 0 24 24" width="34" height="34" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="m8.5 12.5 2.5 2.5 5-5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
      <h3>No active alerts</h3>
      <p>The latest run found no peak, ramp, heatwave, drift or low-confidence issues above threshold.</p>
    </div>`;
  }
})();
