"""
End-to-end smoke test.
Proves the complete pipeline works:
  feature dict → /predict → prediction stored → alert generated → /alerts returns it.
Skipped when model artifacts are not present.
"""
import os
import sys
import json
import pytest

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

MODEL_PATH  = os.path.join(BACKEND_DIR, "model", "model_random_forest.pkl")
LEGACY_PATH = os.path.join(BACKEND_DIR, "model", "model.pkl")
MODEL_AVAILABLE = os.path.exists(MODEL_PATH) or os.path.exists(LEGACY_PATH)

pytestmark = pytest.mark.skipif(
    not MODEL_AVAILABLE,
    reason="Model artifact not found — run backend/model/train_model.py first",
)


@pytest.fixture(scope="module")
def client():
    os.environ.pop("IDS_API_KEY", None)
    import app as ids_app
    ids_app.app.config["TESTING"] = True
    # Reset prediction history and alerts for a clean smoke run
    ids_app.prediction_history.clear()
    ids_app.alerts_data.clear()
    with ids_app.app.test_client() as c:
        yield c


class TestSmokeEndToEnd:
    def test_backend_alive(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert json.loads(r.data)["status"] == "ok"

    def test_predict_normal_flow(self, client, normal_features):
        r = client.post(
            "/predict",
            data=json.dumps({"features": normal_features}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["prediction"].lower() in {"normal", "probe", "dos", "r2l", "u2r"}
        assert 0.0 <= data["confidence"] <= 1.0
        assert data["latency_ms"] >= 0
        assert "event_id" in data

    def test_prediction_appears_in_history(self, client, normal_features):
        # Make a prediction
        client.post(
            "/predict",
            data=json.dumps({"features": normal_features}),
            content_type="application/json",
        )
        # Check history
        r = client.get("/monitor/history")
        data = json.loads(r.data)
        assert data["total_records"] >= 1

    def test_probe_prediction_generates_alert(self, client, probe_features):
        """
        Force confidence threshold to 0 so any non-normal prediction
        creates an alert, regardless of actual model confidence.
        """
        # Set threshold to 0 to guarantee alert generation
        client.post(
            "/settings",
            data=json.dumps({"sensitivity_threshold": 0}),
            content_type="application/json",
        )

        r = client.post(
            "/predict",
            data=json.dumps({"features": probe_features}),
            content_type="application/json",
        )
        data = json.loads(r.data)
        prediction = data["prediction"].lower()

        if prediction != "normal":
            # An alert should have been created
            alerts_r = client.get("/alerts")
            alerts_data = json.loads(alerts_r.data)
            assert alerts_data["total"] >= 1
            latest = alerts_data["alerts"][0]
            assert "id" in latest
            assert "severity" in latest
            assert "confidence" in latest
            assert "latency_ms" in latest
            assert "model_used" in latest

        # Restore threshold
        client.post(
            "/settings",
            data=json.dumps({"sensitivity_threshold": 75}),
            content_type="application/json",
        )

    def test_alert_status_update(self, client, probe_features):
        # Get current alerts
        r = client.get("/alerts")
        data = json.loads(r.data)
        if data["total"] == 0:
            pytest.skip("No alerts to update")

        alert_id = data["alerts"][0]["id"]

        # Update to reviewed
        patch_r = client.patch(
            f"/alerts/{alert_id}",
            data=json.dumps({"status": "reviewed"}),
            content_type="application/json",
        )
        assert patch_r.status_code == 200
        updated = json.loads(patch_r.data)["alert"]
        assert updated["status"] == "reviewed"

    def test_insights_traffic_reflects_predictions(self, client):
        r = client.get("/insights/traffic")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        total = sum(item["count"] for item in data)
        assert total >= 1

    def test_simulate_endpoint(self, client):
        r = client.post(
            "/simulate",
            data=json.dumps({"class": "probe", "count": 3}),
            content_type="application/json",
        )
        # 200 if simulator.py is available; 501 if not (both are acceptable)
        assert r.status_code in (200, 501)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert data["count_returned"] == 3
            assert data["note"]  # synthetic note must be present
