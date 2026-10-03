/* GridSight app shell: state, tabs, data loading, global selectors, states. */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    level: "portfolio",
    entity: "all",
    runId: null,
    data: null,          // { forecast, alerts, plan, metrics, entities, runs, context }
    activeTab: localStorage.getItem("gs.tab") || "overview",
    loading: false,
  };

  const panels = {};
  const tabs = {};
  ["overview", "granularity", "alerts", "optimizer", "accuracy", "assistant", "settings"]
    .forEach((id) => {
      panels[id] = $(`#panel-${id}`);
      tabs[id] = window.Tabs[id];
    });

  /* ---------- states (loading / empty / error) ---------- */
  function showLoading(panel, msg) {
    panel.innerHTML = `
      <div class="kpi-grid">${"<div class='skel' style='height:118px'></div>".repeat(4)}</div>
      <div class="skel" style="height:360px"></div>
      <div style="text-align:center;padding:18px 0 4px;color:var(--muted);font-size:13px" class="mono">${msg || "Loading…"}</div>`;
  }
  function showError(panel, err) {
    panel.innerHTML = `<div class="card"><div class="state">
      <span class="state-icon"><svg viewBox="0 0 24 24" width="34" height="34" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M12 3 2.5 20h19L12 3zm0 6.5v4.5m0 3v.5"/></svg></span>
      <h3>Could not load data</h3>
      <p>${escapeHtml(err.message || "Unknown error")}</p>
      <button class="btn primary" type="button" data-retry>Try again</button>
    </div></div>`;
    panel.querySelector("[data-retry]").addEventListener("click", refresh);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* ---------- data loading ---------- */
  async function refresh() {
    if (state.loading) return;
    state.loading = true;
    showLoading(panels[state.activeTab], "Loading run data…");
    const q = { level: state.level, entity_id: state.entity, run_id: state.runId };
    try {
      const [forecast, alerts, plan, metrics, entities, runs, context] = await Promise.all([
        Api.getForecast(q.level, q.entity_id, q.run_id),
        Api.getAlerts(),
        Api.getPlan(),
        Api.getMetrics(),
        Api.getEntities(),
        Api.getRuns(),
        Api.getContext(),
      ]);
      state.data = { forecast, alerts, plan, metrics, entities, runs, context };
      syncRunSelector();
      syncEntitySelector();
      if (q.run_id && forecast && forecast.run_id !== q.run_id) toast("No data for that run — showing latest.");
      renderActive();
    } catch (err) {
      // empty-run case (mock: old run) vs real error
      if (String(err.message).includes("No forecast data")) {
        state.data = { forecast: null, alerts: [], plan: null, metrics: null, entities: { portfolio: ["all"], zone: [], house: [] }, runs: state.data ? state.data.runs : null, context: null };
        renderActive();
      } else {
        showError(panels[state.activeTab], err);
      }
    } finally {
      state.loading = false;
      updateFooter();
      updateAlertCount();
    }
  }

  function renderActive() {
    const t = tabs[state.activeTab];
    if (!t) return;
    const p = panels[state.activeTab];
    GsCharts.destroyCharts(p);
    if (!state.data) return;
    if (state.activeTab === "assistant") {
      // build once; keep conversation
      if (!p._gsBuilt) t.render(p, state.data, { runId: state.data.forecast ? state.data.forecast.run_id : state.runId });
    } else if (state.data.forecast || !needsForecast(state.activeTab)) {
      t.render(p, state.data);
    } else {
      p.innerHTML = emptyRun(state.activeTab);
    }
    animateIn(p);
  }

  // staggered fade-up entry for cards/KPIs on every render (GPU: transform/opacity/filter)
  function animateIn(panel) {
    requestAnimationFrame(() => {
      $$(".card", panel).forEach((c, i) => {
        c.style.setProperty("--i", String(Math.min(i, 6)));
        c.classList.add("gs-in");
      });
    });
  }

  function needsForecast(id) {
    return ["overview", "granularity", "optimizer"].includes(id);
  }
  function emptyRun(id) {
    const txt = {
      overview: "This run has no forecast data in mock mode. Pick the latest run above.",
      granularity: "This run has no forecast data in mock mode.",
      optimizer: "No battery plan for this run in mock mode.",
    }[id] || "No data for the selected run.";
    return `<div class="card"><div class="state">
      <span class="state-icon"><svg viewBox="0 0 24 24" width="34" height="34" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" d="M4 6h16M4 12h16M4 18h10"/></svg></span>
      <h3>No data for this run</h3><p>${txt}</p>
      <button class="btn" type="button" data-latest>Use latest run</button>
    </div></div>`;
  }

  /* ---------- selectors ---------- */
  function syncRunSelector() {
    const sel = $("#runSelect");
    const runs = state.data.runs || [];
    const current = state.runId || (state.data.forecast ? state.data.forecast.run_id : null);
    sel.innerHTML = [
      `<option value="">Latest run</option>`,
      ...runs.map((r) => `<option value="${r.run_id}"${r.run_id === current ? " selected" : ""}>${GsCharts.fmtDateTime(r.origin_time)} · ${r.run_id}</option>`),
    ].join("");
  }
  function syncEntitySelector() {
    const sel = $("#entitySelect");
    const ents = (state.data.entities || {})[state.level] || [];
    if (ents.includes(state.entity)) {
      sel.innerHTML = ents.map((e) => `<option value="${e}"${e === state.entity ? " selected" : ""}>${state.level === "portfolio" ? "All (portfolio)" : `${state.level} ${e}`}</option>`).join("");
      return;
    }
    state.entity = ents[0] || "all";
    sel.innerHTML = ents.length ? ents.map((e) => `<option value="${e}">${state.level === "portfolio" ? "All (portfolio)" : `${state.level} ${e}`}</option>`).join("") : "<option value=\"all\">—</option>";
  }

  function updateAlertCount() {
    const n = state.data && state.data.alerts ? state.data.alerts.length : 0;
    const el = $("#alertsCount");
    el.hidden = n === 0;
    el.textContent = n;
    el.setAttribute("aria-label", `${n} active alerts`);
  }

  function updateFooter() {
    const badge = $("#sourceBadge");
    const f = state.data && state.data.forecast;
    if (Api.mock) {
      badge.innerHTML = `<span class="dot mock"></span> MOCK · contracts/sample`;
    } else {
      badge.innerHTML = `<span class="dot live"></span> LIVE · ${Api.apiBase}`;
    }
    $("#metaLine").textContent = f
      ? `run ${f.run_id} · model ${f.model_version} · weather ${f.weather_source}`
      : "no run loaded";
  }

  // ticking Australia/Sydney clock (terminal status line)
  function startClock() {
    const el = $("#liveClock");
    const tick = () => {
      el.textContent = new Date().toLocaleTimeString("en-AU", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        hour12: false, timeZone: "Australia/Sydney",
      }) + " AEST";
    };
    tick();
    setInterval(tick, 1000);
  }

  /* ---------- tabs ---------- */
  function activate(id, push = true) {
    if (!tabs[id]) return;
    if (push) localStorage.setItem("gs.tab", id);
    state.activeTab = id;
    $$(".tab").forEach((b) => {
      const on = b.dataset.tab === id;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    Object.entries(panels).forEach(([k, p]) => { p.hidden = k !== id; });
    renderActive();
  }

  /* ---------- toast ---------- */
  let toastTimer;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 4200);
  }

  /* ---------- boot ---------- */
  startClock();
  $("#refreshBtn").addEventListener("click", () => refresh());

  $$(".tab").forEach((btn) => {
    btn.addEventListener("click", () => activate(btn.dataset.tab));
    btn.addEventListener("keydown", (e) => {
      const list = $$(".tab");
      const i = list.indexOf(btn);
      if (e.key === "ArrowRight") { list[(i + 1) % list.length].focus(); activate(list[(i + 1) % list.length].dataset.tab); }
      if (e.key === "ArrowLeft") { list[(i - 1 + list.length) % list.length].focus(); activate(list[(i - 1 + list.length) % list.length].dataset.tab); }
    });
  });

  $("#levelSelect").addEventListener("change", (e) => {
    state.level = e.target.value;
    state.entity = "all";
    refresh();
  });
  $("#entitySelect").addEventListener("change", (e) => { state.entity = e.target.value; refresh(); });
  $("#runSelect").addEventListener("change", (e) => { state.runId = e.target.value || null; refresh(); });

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-latest]")) { state.runId = null; $("#runSelect").value = ""; refresh(); }
  });

  // keep the published runId in sync so tabs can request level-specific forecasts
  Object.defineProperty(window, "Gs", {
    value: {
      state, refresh, activate,
      get runId() { return state.runId || (state.data && state.data.forecast ? state.data.forecast.run_id : null); },
    },
    configurable: true,
  });

  activate(state.activeTab, false);
  refresh();
})();
