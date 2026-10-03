"""API smoke tests (mock mode: runs/ empty -> contracts/sample served)."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_entities(client):
    r = client.get("/entities")
    assert r.status_code == 200
    body = r.json()
    assert body["portfolio"] == ["all"]
    assert "zone" in body and "house" in body


def test_runs_list_in_mock_mode(client):
    r = client.get("/runs")
    assert r.status_code == 200
    runs = r.json()
    assert len(runs) >= 1
    assert runs[0]["run_id"] == "sample"
    assert "origin_time" in runs[0] and "created_at" in runs[0]


def test_forecast_mock(client):
    r = client.get("/forecast", params={"level": "portfolio", "entity_id": "all"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 48
    assert body["points"][0]["slot"] == 0
    assert body["points"][0]["p10"] <= body["points"][0]["p50"] <= body["points"][0]["p90"]
    assert len(body["history"]) == 48


def test_forecast_csv(client):
    r = client.get("/forecast/csv", params={"level": "portfolio", "entity_id": "all"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert len(lines) == 49  # header + 48 slots
    assert lines[0].startswith("timestamp_local,level,entity_id,horizon_slot,load_kw_p10")


def test_forecast_invalid_level(client):
    r = client.get("/forecast", params={"level": "moon"})
    assert r.status_code == 404
    assert "level" in r.json()["detail"]


def test_forecast_unknown_run(client, env, monkeypatch):
    # force a real (non-mock) run folder so unknown run_id -> 404
    from backend.config import get_app_config
    from backend.services.run_service import ensure_bundle
    from backend.services.run_store import Bundle

    sample = (env.sample_dir / "forecast.json").read_text()
    run_dir = env.runs_dir / "2013-02-15T00-00"
    run_dir.mkdir(parents=True)
    (run_dir / "forecast.json").write_text(sample)
    ensure_bundle(Bundle(run_dir, run_dir.name, False), get_app_config())

    r = client.get("/forecast", params={"run_id": "does-not-exist"})
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_alerts_mock(client):
    r = client.get("/alerts")
    assert r.status_code == 200
    alerts = r.json()
    assert isinstance(alerts, list) and alerts
    a = alerts[0]
    for field in ("id", "type", "severity", "level", "entity_id", "window_start", "window_end", "value", "threshold", "message"):
        assert field in a, field


def test_plan_mock(client):
    r = client.get("/plan")
    assert r.status_code == 200
    plan = r.json()
    assert plan["mode"] == "advisory"
    assert len(plan["slots"]) == 48
    assert plan["saving"] >= 0
    assert plan["cost_after"] <= plan["cost_before"] + 1e-6


def test_metrics_mock(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    names = {m["model"] for m in body["by_model"]}
    assert "ensemble" in names and "seasonal_naive" in names


def test_chat_without_llm_key(client, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    r = client.post("/chat", json={"question": "Summarize this run for the operator"})
    assert r.status_code == 200
    body = r.json()
    assert body["used_llm"] is False
    assert len(body["answer"]) > 40
    assert "peak" in body["answer"].lower() or "kwh" in body["answer"].lower()


def test_chat_unknown_question_answers_from_context(client, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    r = client.post("/chat", json={"question": "Why is the evening peak high?"})
    assert r.status_code == 200
    assert r.json()["used_llm"] is False


def test_control_override_persists(client):
    r1 = client.post("/control/override")
    assert r1.status_code == 200
    assert r1.json() == {"control_enabled": False, "dry_run": True}
    r2 = client.post("/control/override")
    assert r2.json()["control_enabled"] is False


def test_run_missing_ml_returns_clear_error(client):
    r = client.post("/run", json={"origin_time": "2013-02-15T00:00:00+11:00"})
    assert r.status_code == 500
    assert "ml.run_cycle" in r.json()["detail"]
