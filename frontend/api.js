/* GridSight API layer — the ONLY file that calls fetch().
 * MOCK=true  -> reads ../contracts/sample/*.json (or the embedded MockData fallback
 *               when the page is opened via file:// and local fetch is blocked).
 * MOCK=false -> calls the FastAPI at API_BASE (Member 2).
 */
(function () {
  "use strict";

  const API_BASE = "http://localhost:8000";
  const SAMPLE_DIR = "../contracts/sample/";

  const params = new URLSearchParams(location.search);
  const stored = localStorage.getItem("gs.mock");
  let mock = params.has("mock") ? params.get("mock") !== "0" : stored === null ? true : stored === "1";

  async function j(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(`HTTP ${res.status} (${url})`);
    return res.json();
  }

  async function getJson(url, fallback) {
    if (!mock) return j(API_BASE + url);
    try {
      return await j(SAMPLE_DIR + fallback);
    } catch {
      if (!window.MockData) throw new Error("Mock data unavailable");
      return MockFile[fallback];
    }
  }

  const MockFile = {
    get "alerts.json"() { return MockData.alerts; },
    get "metrics.json"() { return MockData.metrics; },
    get "plan.json"() { return MockData.plan; },
    get "entities.json"() { return MockData.entities; },
    get "explain_context.json"() { return MockData.explainContext; },
    get "forecast.json"() { return MockData.deriveForecast("portfolio", "all", null); },
    get "runs.json"() { return MockData.runs; },
  };

  const Api = {
    get mock() { return mock; },
    set mock(v) {
      mock = v;
      localStorage.setItem("gs.mock", v ? "1" : "0");
    },
    get apiBase() { return API_BASE; },

    getHealth: () => mock ? Promise.resolve({ status: "ok", version: "mock" }) : j(`${API_BASE}/health`),

    getEntities: () => getJson("/entities", "entities.json"),

    getRuns: () => getJson("/runs", "runs.json"),

    getForecast(level, entityId, runId) {
      if (!mock) {
        const q = new URLSearchParams({ level, entity_id: entityId });
        if (runId) q.set("run_id", runId);
        return j(`${API_BASE}/forecast?${q}`);
      }
      return new Promise((resolve, reject) => setTimeout(() => {
        const fc = MockData.deriveForecast(level, entityId, runId);
        fc ? resolve(fc) : reject(new Error("No forecast data for this run in mock mode"));
      }, 120));
    },

    getAlerts: () => getJson("/alerts", "alerts.json"),
    getPlan: () => getJson("/plan", "plan.json"),
    getMetrics: () => getJson("/metrics", "metrics.json"),

    // explain_context.json: member 2 may not expose an endpoint yet -> graceful null.
    async getContext() {
      if (!mock) {
        try { return await j(`${API_BASE}/explain-context`); } catch { return null; }
      }
      return getJson("/explain-context", "explain_context.json");
    },

    chat(question, runId) {
      if (!mock) {
        return j(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, run_id: runId || null }),
        });
      }
      return new Promise((resolve) => setTimeout(() => resolve(MockData.mockChat(question, {
        context: MockData.explainContext, plan: MockData.plan, metrics: MockData.metrics,
      })), 450));
    },

    // Live mode can stream the CSV endpoint; mock builds it from the JSON we already have.
    forecastCsv(forecast) {
      const head = "timestamp_local,level,entity_id,horizon_slot,load_kw_p10,load_kw_p50,load_kw_p90,model_version,run_id,weather_source";
      const rows = forecast.points.map((p) =>
        [p.timestamp, forecast.level, forecast.entity_id, p.slot, p.p10, p.p50, p.p90, forecast.model_version, forecast.run_id, forecast.weather_source].join(","));
      return [head, ...rows].join("\n");
    },
  };

  window.Api = Api;
})();
