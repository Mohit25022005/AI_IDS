"""
Tests for the Flask REST API endpoints.
Uses Flask's test client — no network required.
"""
import os
import sys
import json
import pytest

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

MODEL_PATH = os.path.join(BACKEND_DIR, "model", "model_random_forest.pkl")
LEGACY_PATH = os.path.join(BACKEND_DIR, "model", "model.pkl")
MODEL_AVAILABLE = os.path.exists(MODEL_PATH) or os.path.exists(LEGACY_PATH)


@pytest.fixture(scope="module")
def client():
    """Return a Flask test client with models loaded."""
    # Ensure no API key blocks the test client
    os.environ.pop("IDS_API_KEY", None)
    import app as ids_app
    ids_app.app.config["TESTING"] = True
    with ids_app.app.test_client() as c:
        yield c


# ── Health endpoints (always available) ──────────────────────────
class TestHealthEndpoints:
    def test_root_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "message" in data

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert "models_loaded" in data

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert b"ids_uptime_seconds" in r.data


# ── Settings endpoints ───────────────────────────────────────────
class TestSettingsEndpoints:
    def test_get_settings(self, client):
        r = client.get("/settings")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "ml_model" in data
        assert "sensitivity_threshold" in data

    def test_update_valid_threshold(self, client):
        r = client.post(
            "/settings",
            data=json.dumps({"sensitivity_threshold": 80}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["settings"]["sensitivity_threshold"] == 80

    def test_update_invalid_threshold(self, client):
        r = client.post(
            "/settings",
            data=json.dumps({"sensitivity_threshold": 150}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_update_invalid_model(self, client):
        r = client.post(
            "/settings",
            data=json.dumps({"ml_model": "gpt-4"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_update_valid_model(self, client):
        r = client.post(
            "/settings",
            data=json.dumps({"ml_model": "random-forest"}),
            content_type="application/json",
        )
        assert r.status_code == 200


# ── Predict endpoint (requires model) ────────────────────────────
@pytest.mark.skipif(not MODEL_AVAILABLE, reason="Model not trained yet")
class TestPredictEndpoint:
    def test_predict_returns_prediction(self, client, normal_features):
        r = client.post(
            "/predict",
            data=json.dumps({"features": normal_features}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "prediction" in data
        assert "confidence" in data
        assert "latency_ms" in data
        assert "event_id" in data

    def test_predict_missing_features(self, client, normal_features):
        bad = {k: v for k, v in normal_features.items() if k != "duration"}
        r = client.post(
            "/predict",
            data=json.dumps({"features": bad}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "missing_features" in data or "error" in data

    def test_predict_extra_features(self, client, normal_features):
        bad = {**normal_features, "extra_field": 99}
        r = client.post(
            "/predict",
            data=json.dumps({"features": bad}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_predict_invalid_protocol(self, client, normal_features):
        bad = {**normal_features, "protocol": "icmp"}
        r = client.post(
            "/predict",
            data=json.dumps({"features": bad}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_predict_non_numeric_feature(self, client, normal_features):
        bad = {**normal_features, "duration": "not_a_number"}
        r = client.post(
            "/predict",
            data=json.dumps({"features": bad}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_predict_empty_body(self, client):
        r = client.post("/predict", data="", content_type="application/json")
        assert r.status_code == 400

    def test_confidence_range(self, client, normal_features):
        r = client.post(
            "/predict",
            data=json.dumps({"features": normal_features}),
            content_type="application/json",
        )
        data = json.loads(r.data)
        assert 0.0 <= data["confidence"] <= 1.0

    def test_latency_positive(self, client, normal_features):
        r = client.post(
            "/predict",
            data=json.dumps({"features": normal_features}),
            content_type="application/json",
        )
        data = json.loads(r.data)
        assert data["latency_ms"] >= 0


# ── Alerts endpoints ─────────────────────────────────────────────
class TestAlertsEndpoints:
    def test_get_alerts_returns_200(self, client):
        r = client.get("/alerts")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "alerts" in data
        assert "total" in data

    def test_get_alerts_pagination(self, client):
        r = client.get("/alerts?page=1&limit=5")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data["alerts"]) <= 5

    def test_patch_nonexistent_alert(self, client):
        r = client.patch(
            "/alerts/nonexistent-id-12345",
            data=json.dumps({"status": "reviewed"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_patch_invalid_status(self, client):
        r = client.patch(
            "/alerts/1",
            data=json.dumps({"status": "invalid_status"}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ── Monitor history ──────────────────────────────────────────────
class TestMonitorHistory:
    def test_history_returns_200(self, client):
        r = client.get("/monitor/history")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "records" in data
        assert "normal_count" in data
        assert "attack_count" in data
        assert "attack_rate" in data


# ── Insights endpoints ───────────────────────────────────────────
class TestInsightsEndpoints:
    def test_traffic_returns_list(self, client):
        r = client.get("/insights/traffic")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_latency_returns_samples(self, client):
        r = client.get("/insights/latency")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "samples" in data
        assert "avg_ms" in data

    def test_model_comparison_returns_list(self, client):
        r = client.get("/model/comparison")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
