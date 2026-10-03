"""
Cloud-RT-IDS  ·  Flask API
===========================
Serves the IDS backend: live capture, manual prediction, alerts,
model management, insights, health, metrics, and simulation.

All metrics are loaded dynamically from metrics_all.json (produced by
train_model.py).  Nothing is hardcoded.

Environment variables (see .env.example):
  IDS_HOST               default 0.0.0.0
  IDS_PORT               default 5000
  IDS_CORS_ORIGINS       default http://localhost:8081,http://127.0.0.1:8081
  IDS_MAX_HISTORY        default 10000
  IDS_API_KEY            optional – if set, all non-health endpoints require
                           X-API-Key header matching this value
  IDS_LOG_LEVEL          default INFO
"""

import os
import json
import time
import uuid
import logging
import threading
from datetime import datetime, timedelta
from functools import wraps

import joblib
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, Response, g
from flask_cors import CORS
from dotenv import load_dotenv

from url_kdd import (
    capture_flows,
    build_feature_vector,
    generate_local_probe_traffic,
)

# ==================================================================
# Environment / config
# ==================================================================
load_dotenv()

HOST            = os.getenv("IDS_HOST", "0.0.0.0")
PORT            = int(os.getenv("IDS_PORT", "5000"))
CORS_ORIGINS    = os.getenv(
    "IDS_CORS_ORIGINS",
    "http://localhost:8081,http://127.0.0.1:8081,http://localhost:5173,http://127.0.0.1:5173"
).split(",")
MAX_HISTORY     = int(os.getenv("IDS_MAX_HISTORY", "10000"))
API_KEY         = os.getenv("IDS_API_KEY", "")          # empty = no auth
LOG_LEVEL       = os.getenv("IDS_LOG_LEVEL", "INFO").upper()
DEBUG_MODE      = os.getenv("IDS_DEBUG", "false").lower() == "true"

# ==================================================================
# Structured logging (JSON)
# ==================================================================
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), handlers=[handler])
logger = logging.getLogger("ids")

# ==================================================================
# Paths
# ==================================================================
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR    = os.path.join(BASE_DIR, "model")
DATA_DIR     = os.path.join(BASE_DIR, "data")

ALERTS_FILE         = os.path.join(DATA_DIR, "alerts.json")
HISTORY_FILE        = os.path.join(DATA_DIR, "prediction_history.json")
SETTINGS_FILE       = os.path.join(DATA_DIR, "settings.json")
METRICS_ALL_FILE    = os.path.join(MODEL_DIR, "metrics_all.json")

# ==================================================================
# Feature schema  (must match train_model.py)
# ==================================================================
FEATURE_SCHEMA_VERSION = "v2"

LIVE_FEATURE_COLUMNS = [
    "duration", "source_port", "destination_port",
    "forward_packets", "backward_packets",
    "forward_bytes", "backward_bytes",
    "total_packets", "total_bytes",
    "packets_per_second", "bytes_per_second",
    "mean_packet_size", "min_packet_size", "max_packet_size", "packet_size_std",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count",
    "forward_packet_ratio", "backward_packet_ratio",
    "forward_byte_ratio", "backward_byte_ratio",
    "syn_ratio", "rst_ratio",
    "protocol",
]

# Map settings key → model pickle filename
MODEL_FILES = {
    "random-forest":   "model_random_forest.pkl",
    "svm":             "model_svm.pkl",
    "neural-network":  "model_neural_network.pkl",
    "hybrid":          "model_hybrid.pkl",
}
# Fallback to legacy model.pkl when individual files not yet built
LEGACY_MODEL_FILE = "model.pkl"

# ==================================================================
# Default settings
# ==================================================================
DEFAULT_SETTINGS = {
    "live_detection":        True,
    "ml_model":              "random-forest",
    "sensitivity_threshold": 75,
    "auto_retrain":          False,
    "email_alerts":          False,
    "desktop_notifications": False,
}

# ==================================================================
# Severity lookup  (attack type → base severity)
# ==================================================================
ATTACK_SEVERITY_MAP = {
    "normal": "info",
    "probe":  "medium",
    "dos":    "high",
    "r2l":    "high",
    "u2r":    "critical",
}

def get_alert_severity(prediction: str, confidence: float) -> str:
    base = ATTACK_SEVERITY_MAP.get(prediction.lower(), "medium")
    # Upgrade severity when confidence is very high
    upgrade = {
        "info":     "info",
        "medium":   "high"    if confidence >= 0.90 else "medium",
        "high":     "critical" if confidence >= 0.90 else "high",
        "critical": "critical",
    }
    return upgrade.get(base, base)

# ==================================================================
# Startup statistics  (in-memory, not persisted)
# ==================================================================
_start_time = time.monotonic()
_request_count = 0
_prediction_count_by_class: dict = {}
_latency_samples: list = []          # last 1000 inference latency values (ms)

# ==================================================================
# Flask app
# ==================================================================
app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)

# ==================================================================
# Optional API-key auth decorator
# ==================================================================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_KEY:
            key = request.headers.get("X-API-Key", "")
            if key != API_KEY:
                logger.warning("Unauthorized request", extra={"path": request.path})
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ==================================================================
# Request logging
# ==================================================================
@app.before_request
def _before():
    global _request_count
    _request_count += 1
    g.start_ts = time.perf_counter()

@app.after_request
def _after(response):
    elapsed_ms = round((time.perf_counter() - g.start_ts) * 1000, 2)
    logger.info(
        "request",
        extra={},
    )
    # Log as structured dict inside the message field
    logger.info(json.dumps({
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duration_ms": elapsed_ms,
    }))
    return response

# ==================================================================
# Persistent storage helpers
# ==================================================================
def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data
    except (json.JSONDecodeError, OSError):
        return default

def _save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

# ==================================================================
# Settings  (persisted to settings.json)
# ==================================================================
def load_settings() -> dict:
    saved = _load_json(SETTINGS_FILE, {})
    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    return merged

def save_settings(s: dict):
    _save_json(SETTINGS_FILE, s)

settings = load_settings()

# ==================================================================
# Prediction history  (capped at MAX_HISTORY)
# ==================================================================
prediction_history: list = _load_json(HISTORY_FILE, [])
if not isinstance(prediction_history, list):
    prediction_history = []

def _append_history(record: dict):
    prediction_history.append(record)
    if len(prediction_history) > MAX_HISTORY:
        del prediction_history[: len(prediction_history) - MAX_HISTORY]
    _save_json(HISTORY_FILE, prediction_history)

# ==================================================================
# Alerts  (with uuid IDs)
# ==================================================================
alerts_data: list = _load_json(ALERTS_FILE, [])
if not isinstance(alerts_data, list):
    alerts_data = []

def _append_alert(record: dict):
    alerts_data.append(record)
    _save_json(ALERTS_FILE, alerts_data)

def _save_alerts():
    _save_json(ALERTS_FILE, alerts_data)

# ==================================================================
# Model loading
# ==================================================================
_models: dict = {}          # key → loaded sklearn Pipeline
_metrics_cache: dict = {}   # loaded from metrics_all.json

def _load_metrics_cache():
    global _metrics_cache
    data = _load_json(METRICS_ALL_FILE, {})
    _metrics_cache = data if isinstance(data, dict) else {}
    if _metrics_cache:
        logger.info("Loaded metrics_all.json")
    else:
        logger.warning("metrics_all.json not found — run train_model.py first")

def _load_single_model(model_key: str):
    """Load one model by settings key.  Returns the pipeline or None."""
    fname = MODEL_FILES.get(model_key)
    if fname:
        path = os.path.join(MODEL_DIR, fname)
        if os.path.exists(path):
            try:
                m = joblib.load(path)
                logger.info(f"Loaded model: {fname}")
                return m
            except Exception as exc:
                logger.error(f"Failed to load {fname}: {exc}")

    # Fallback: legacy model.pkl (Random Forest only)
    if model_key == "random-forest":
        legacy = os.path.join(MODEL_DIR, LEGACY_MODEL_FILE)
        if os.path.exists(legacy):
            try:
                m = joblib.load(legacy)
                logger.info("Loaded legacy model.pkl as random-forest fallback")
                return m
            except Exception as exc:
                logger.error(f"Failed to load legacy model: {exc}")
    return None

def load_all_models():
    global _models
    _models = {}
    for key in MODEL_FILES:
        m = _load_single_model(key)
        if m is not None:
            _models[key] = m
    if not _models:
        logger.error("No models loaded — run train_model.py first")
    else:
        logger.info(f"Available models: {list(_models.keys())}")
    _load_metrics_cache()

load_all_models()

def active_model():
    """Return the currently-active sklearn pipeline, or None."""
    key = settings.get("ml_model", "random-forest")
    return _models.get(key) or next(iter(_models.values()), None)

def active_model_key() -> str:
    key = settings.get("ml_model", "random-forest")
    if key in _models:
        return key
    return next(iter(_models.keys()), "random-forest")

# ==================================================================
# Prediction core  (shared by /predict and /capture)
# ==================================================================
def _run_inference(features_df: pd.DataFrame):
    """
    Run inference on a single-row DataFrame.
    Returns (prediction_str, confidence_float, latency_ms).
    """
    model = active_model()
    if model is None:
        raise RuntimeError("No model loaded")

    t0 = time.perf_counter()
    prediction = str(model.predict(features_df)[0])
    proba = model.predict_proba(features_df)
    confidence = float(np.max(proba))
    latency_ms = round((time.perf_counter() - t0) * 1000, 4)

    # Update in-memory stats
    _prediction_count_by_class[prediction] = (
        _prediction_count_by_class.get(prediction, 0) + 1
    )
    _latency_samples.append(latency_ms)
    if len(_latency_samples) > 1000:
        del _latency_samples[0]

    return prediction, confidence, latency_ms

# ==================================================================
# ────────────────────────  ROUTES  ────────────────────────────────
# ==================================================================

# ── Health ──────────────────────────────────────────────────────────
@app.route("/")
def home():
    return jsonify({"message": "Intrusion Detection API Running!", "version": "2.0"})

@app.route("/health")
def health():
    uptime = round(time.monotonic() - _start_time, 1)
    avg_latency = (
        round(sum(_latency_samples) / len(_latency_samples), 3)
        if _latency_samples else None
    )
    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime,
        "active_model": active_model_key(),
        "models_loaded": list(_models.keys()),
        "model_loaded": active_model() is not None,
        "metrics_loaded": bool(_metrics_cache),
        "history_count": len(prediction_history),
        "alert_count": len(alerts_data),
        "avg_inference_latency_ms": avg_latency,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
    })

# ── Prometheus-compatible metrics ──────────────────────────────────
@app.route("/metrics")
def prometheus_metrics():
    uptime = round(time.monotonic() - _start_time, 1)
    total_preds = sum(_prediction_count_by_class.values())
    avg_latency = (
        round(sum(_latency_samples) / len(_latency_samples), 3)
        if _latency_samples else 0
    )

    lines = [
        "# HELP ids_uptime_seconds Seconds since the backend started",
        "# TYPE ids_uptime_seconds gauge",
        f"ids_uptime_seconds {uptime}",
        "",
        "# HELP ids_requests_total Total HTTP requests received",
        "# TYPE ids_requests_total counter",
        f"ids_requests_total {_request_count}",
        "",
        "# HELP ids_predictions_total Total predictions made",
        "# TYPE ids_predictions_total counter",
        f"ids_predictions_total {total_preds}",
        "",
        "# HELP ids_predictions_by_class Predictions broken down by class",
        "# TYPE ids_predictions_by_class counter",
    ]
    for cls, cnt in _prediction_count_by_class.items():
        lines.append(f'ids_predictions_by_class{{class="{cls}"}} {cnt}')

    lines += [
        "",
        "# HELP ids_alerts_total Total alerts generated",
        "# TYPE ids_alerts_total counter",
        f"ids_alerts_total {len(alerts_data)}",
        "",
        "# HELP ids_inference_latency_ms_avg Average inference latency in ms",
        "# TYPE ids_inference_latency_ms_avg gauge",
        f"ids_inference_latency_ms_avg {avg_latency}",
        "",
        "# HELP ids_history_size Current prediction history size",
        "# TYPE ids_history_size gauge",
        f"ids_history_size {len(prediction_history)}",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain; version=0.0.4")

# ── Predict ─────────────────────────────────────────────────────────
@app.route("/predict", methods=["POST"])
@require_api_key
def predict():
    if active_model() is None:
        return jsonify({"error": "Model not loaded"}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must contain JSON"}), 400

    features_input = data.get("features")
    if features_input is None:
        return jsonify({"error": "Missing 'features' in request body"}), 400
    if not isinstance(features_input, dict):
        return jsonify({"error": "'features' must be a JSON object"}), 400

    missing = [f for f in LIVE_FEATURE_COLUMNS if f not in features_input]
    if missing:
        return jsonify({"error": "Missing features", "missing_features": missing}), 400

    extra = [f for f in features_input if f not in LIVE_FEATURE_COLUMNS]
    if extra:
        return jsonify({"error": "Unknown features", "unknown_features": extra}), 400

    numeric_features = {}
    for feat in LIVE_FEATURE_COLUMNS:
        if feat == "protocol":
            proto = str(features_input[feat]).lower().strip()
            if proto not in ("tcp", "udp", "other"):
                return jsonify({"error": "protocol must be tcp, udp, or other"}), 400
            numeric_features[feat] = proto
        else:
            try:
                numeric_features[feat] = float(features_input[feat])
            except (TypeError, ValueError):
                return jsonify({"error": f"Feature '{feat}' must be numeric"}), 400

    features_df = pd.DataFrame([numeric_features], columns=LIVE_FEATURE_COLUMNS)

    try:
        prediction, confidence, latency_ms = _run_inference(features_df)
    except Exception as exc:
        logger.error(f"Inference error: {exc}")
        return jsonify({"error": f"Inference failed: {exc}"}), 500

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    event_id  = str(uuid.uuid4())

    record = {
        "event_id":    event_id,
        "timestamp":   timestamp,
        "prediction":  prediction,
        "confidence":  round(confidence * 100, 2),
        "latency_ms":  latency_ms,
        "model_used":  active_model_key(),
        "sourceIP":    "N/A",
        "destinationIP": "N/A",
        "sourcePort":   int(numeric_features["source_port"]),
        "destinationPort": int(numeric_features["destination_port"]),
        "protocol":    numeric_features["protocol"],
    }
    _append_history(record)

    if (
        prediction.lower() != "normal"
        and confidence * 100 >= settings["sensitivity_threshold"]
    ):
        severity = get_alert_severity(prediction, confidence)
        alert = {
            "id":            str(uuid.uuid4()),
            "event_id":      event_id,
            "timestamp":     timestamp,
            "type":          f"{prediction.title()} Detection",
            "severity":      severity,
            "sourceIP":      "N/A",
            "destinationIP": "N/A",
            "sourcePort":    int(numeric_features["source_port"]),
            "destinationPort": int(numeric_features["destination_port"]),
            "protocol":      numeric_features["protocol"],
            "confidence":    round(confidence * 100, 2),
            "latency_ms":    latency_ms,
            "model_used":    active_model_key(),
            "description": (
                f"{prediction.title()} activity detected. "
                f"Confidence: {confidence*100:.1f}%. "
                f"Protocol: {numeric_features['protocol'].upper()}, "
                f"destination port: {int(numeric_features['destination_port'])}."
            ),
            "status": "active",
        }
        _append_alert(alert)

    return jsonify({
        "event_id":    event_id,
        "prediction":  prediction,
        "confidence":  confidence,
        "latency_ms":  latency_ms,
        "timestamp":   timestamp,
        "model_used":  active_model_key(),
        "features_used": {f: numeric_features[f] for f in LIVE_FEATURE_COLUMNS},
    })

# ── Live capture ────────────────────────────────────────────────────
@app.route("/capture", methods=["POST"])
@require_api_key
def capture_network_flows():
    try:
        data = request.get_json(silent=True) or {}
        capture_time = float(data.get("capture_time", 8))
        mode = str(data.get("mode", "normal")).lower()

        if not (0 < capture_time <= 60):
            return jsonify({"error": "capture_time must be 1–60 seconds"}), 400
        if mode not in {"normal", "probe"}:
            return jsonify({"error": "mode must be 'normal' or 'probe'"}), 400
        if active_model() is None:
            return jsonify({"error": "ML model not loaded"}), 500

        captured_flows = []

        def run_capture():
            captured_flows.extend(capture_flows(capture_time=capture_time))

        thread = threading.Thread(target=run_capture, daemon=True)
        thread.start()
        time.sleep(0.5)

        if mode == "probe":
            generate_local_probe_traffic()

        thread.join()

        detected = []
        ingested_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        for flow in captured_flows:
            fv = build_feature_vector(flow)
            features_df = pd.DataFrame([fv], columns=LIVE_FEATURE_COLUMNS)

            try:
                prediction, confidence, latency_ms = _run_inference(features_df)
            except Exception as exc:
                logger.error(f"Inference error on captured flow: {exc}")
                continue

            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            event_id  = str(uuid.uuid4())

            record = {
                "event_id":      event_id,
                "timestamp":     timestamp,
                "ingested_at":   ingested_at,
                "prediction":    prediction,
                "confidence":    round(confidence * 100, 2),
                "latency_ms":    latency_ms,
                "model_used":    active_model_key(),
                "sourceIP":      flow.src_ip,
                "destinationIP": flow.dst_ip,
                "sourcePort":    int(flow.src_port),
                "destinationPort": int(flow.dst_port),
                "protocol":      str(flow.protocol).lower(),
            }
            _append_history(record)

            if (
                prediction.lower() != "normal"
                and confidence * 100 >= settings["sensitivity_threshold"]
            ):
                severity = get_alert_severity(prediction, confidence)
                alert = {
                    "id":            str(uuid.uuid4()),
                    "event_id":      event_id,
                    "timestamp":     timestamp,
                    "type":          f"{prediction.title()} Detection",
                    "severity":      severity,
                    "sourceIP":      flow.src_ip,
                    "destinationIP": flow.dst_ip,
                    "sourcePort":    int(flow.src_port),
                    "destinationPort": int(flow.dst_port),
                    "protocol":      str(flow.protocol).lower(),
                    "confidence":    round(confidence * 100, 2),
                    "latency_ms":    latency_ms,
                    "model_used":    active_model_key(),
                    "description": (
                        f"{prediction.title()} activity detected. "
                        f"Confidence: {confidence*100:.1f}%. "
                        f"{str(flow.protocol).upper()} traffic from "
                        f"{flow.src_ip}:{flow.src_port} to "
                        f"{flow.dst_ip}:{flow.dst_port}."
                    ),
                    "status": "active",
                }
                _append_alert(alert)

            detected.append({
                "event_id":   event_id,
                "features":   fv,
                "prediction": prediction,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "timestamp":  timestamp,
            })

        return jsonify({
            "message":       "Network capture and detection completed",
            "mode":          mode,
            "flows_captured": len(detected),
            "flows":         detected,
        })

    except Exception as exc:
        logger.error(f"Capture failed: {exc}")
        return jsonify({"error": f"Network capture failed: {exc}"}), 500

# ── Monitor history ─────────────────────────────────────────────────
@app.route("/monitor/history")
@require_api_key
def monitor_history():
    page  = max(1, int(request.args.get("page", 1)))
    limit = min(200, max(1, int(request.args.get("limit", 50))))
    severity_filter = request.args.get("severity")
    pred_filter = request.args.get("prediction", "").lower()

    records = prediction_history
    if pred_filter:
        records = [r for r in records if r.get("prediction", "").lower() == pred_filter]

    total = len(records)
    start = (page - 1) * limit
    page_records = records[-(start + limit): len(records) - start] if start < total else []

    counts_by_class: dict = {}
    for r in prediction_history:
        cls = r.get("prediction", "unknown").lower()
        counts_by_class[cls] = counts_by_class.get(cls, 0) + 1

    normal_count = counts_by_class.get("normal", 0)
    attack_count = sum(v for k, v in counts_by_class.items() if k != "normal")
    total_all = normal_count + attack_count
    attack_rate = round(attack_count / total_all * 100, 2) if total_all > 0 else 0.0

    avg_latency = None
    if _latency_samples:
        avg_latency = round(sum(_latency_samples) / len(_latency_samples), 3)

    return jsonify({
        "records":           list(reversed(page_records)),
        "total_records":     total,
        "page":              page,
        "limit":             limit,
        "normal_count":      normal_count,
        "attack_count":      attack_count,
        "attack_rate":       attack_rate,
        "counts_by_class":   counts_by_class,
        "avg_latency_ms":    avg_latency,
        "active_model":      active_model_key(),
    })

# ── Alerts ──────────────────────────────────────────────────────────
@app.route("/alerts")
@require_api_key
def get_alerts():
    page     = max(1, int(request.args.get("page", 1)))
    limit    = min(200, max(1, int(request.args.get("limit", 50))))
    severity = request.args.get("severity", "").lower()
    pred     = request.args.get("prediction", "").lower()
    status   = request.args.get("status", "").lower()

    filtered = alerts_data
    if severity:
        filtered = [a for a in filtered if a.get("severity", "").lower() == severity]
    if pred:
        filtered = [a for a in filtered if pred in a.get("type", "").lower()]
    if status:
        filtered = [a for a in filtered if a.get("status", "").lower() == status]

    total = len(filtered)
    start = (page - 1) * limit
    page_items = list(reversed(filtered))[start: start + limit]

    return jsonify({
        "alerts":  page_items,
        "total":   total,
        "page":    page,
        "limit":   limit,
    })

@app.route("/alerts/<alert_id>", methods=["PATCH"])
@require_api_key
def update_alert(alert_id: str):
    data       = request.get_json(silent=True) or {}
    new_status = data.get("status")
    allowed    = {"active", "reviewed", "false-positive", "resolved"}

    if new_status not in allowed:
        return jsonify({"error": "Invalid status", "allowed": list(allowed)}), 400

    for alert in alerts_data:
        if str(alert.get("id")) == str(alert_id):
            alert["status"] = new_status
            _save_alerts()
            return jsonify({"message": "Alert updated", "alert": alert})

    return jsonify({"error": f"Alert {alert_id} not found"}), 404

# ── Settings ─────────────────────────────────────────────────────────
@app.route("/settings", methods=["GET"])
def get_settings():
    return jsonify(settings)

@app.route("/settings", methods=["POST"])
@require_api_key
def update_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Body must be a JSON object"}), 400

    bool_keys = {"live_detection", "auto_retrain", "email_alerts", "desktop_notifications"}
    for k in bool_keys:
        if k in data:
            if not isinstance(data[k], bool):
                return jsonify({"error": f"'{k}' must be boolean"}), 400
            settings[k] = data[k]

    if "ml_model" in data:
        allowed_models = list(MODEL_FILES.keys())
        if data["ml_model"] not in allowed_models:
            return jsonify({
                "error": "Unsupported model",
                "allowed_models": allowed_models,
            }), 400
        settings["ml_model"] = data["ml_model"]

    if "sensitivity_threshold" in data:
        try:
            t = float(data["sensitivity_threshold"])
        except (TypeError, ValueError):
            return jsonify({"error": "'sensitivity_threshold' must be numeric"}), 400
        if not 0 <= t <= 100:
            return jsonify({"error": "'sensitivity_threshold' must be 0–100"}), 400
        settings["sensitivity_threshold"] = t

    save_settings(settings)
    return jsonify({"message": "Settings updated", "settings": settings})

# ── Model management ─────────────────────────────────────────────────
@app.route("/model/info")
def model_info():
    key = active_model_key()
    # Map settings key → metrics JSON key
    metrics_key_map = {
        "random-forest":  "random_forest",
        "svm":            "svm",
        "neural-network": "neural_network",
        "hybrid":         "hybrid",
    }
    mkey = metrics_key_map.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    model_metrics = _load_json(metrics_file, {})

    return jsonify({
        "active_model_key":      key,
        "available_models":      list(_models.keys()),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_columns":       LIVE_FEATURE_COLUMNS,
        "n_features":            len(LIVE_FEATURE_COLUMNS),
        "training_timestamp":    model_metrics.get("training_timestamp"),
        "n_train_samples":       model_metrics.get("n_train_samples"),
        "n_test_samples":        model_metrics.get("n_test_samples"),
        "classes":               model_metrics.get("classes"),
        "hyperparameters":       model_metrics.get("hyperparameters"),
        "train_dataset_md5":     model_metrics.get("train_dataset_md5"),
        "independent_test": model_metrics.get("independent_test", {}),
        "feature_importances": model_metrics.get("feature_importances"),
    })

@app.route("/model/comparison")
def model_comparison():
    summary = _load_json(METRICS_ALL_FILE, {})
    return jsonify(summary.get("model_comparison", []))

@app.route("/model/retrain", methods=["POST"])
@require_api_key
def retrain_model():
    return jsonify({"error": "Use train_model.py to retrain — automatic retraining not enabled"}), 501

@app.route("/model/reload", methods=["POST"])
@require_api_key
def reload_model():
    load_all_models()
    if not _models:
        return jsonify({"error": "Failed to reload models"}), 500
    return jsonify({"message": "Models reloaded", "available": list(_models.keys())})

@app.route("/model/reset", methods=["POST"])
@require_api_key
def reset_model():
    global settings
    settings = DEFAULT_SETTINGS.copy()
    save_settings(settings)
    load_all_models()
    if not _models:
        return jsonify({"error": "Failed to reload models"}), 500
    return jsonify({"message": "Reset to defaults", "settings": settings})

# ── Insights ─────────────────────────────────────────────────────────
@app.route("/insights/metrics")
def insights_metrics():
    """Return independent-test metrics for the active model (from saved JSON)."""
    key = active_model_key()
    metrics_key_map = {
        "random-forest":  "random_forest",
        "svm":            "svm",
        "neural-network": "neural_network",
        "hybrid":         "hybrid",
    }
    mkey = metrics_key_map.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    data = _load_json(metrics_file, {})

    if not data:
        # Fallback: look in metrics_all.json for the summary
        summary = _load_json(METRICS_ALL_FILE, {})
        test_m = summary.get("current_metrics", {})
    else:
        test_m = data.get("independent_test", {})

    if not test_m:
        return jsonify({
            "error": "Metrics not available — run train_model.py first"
        }), 503

    return jsonify({
        "model":              key,
        "evaluation_type":    "independent_test_set",
        "n_test_samples":     test_m.get("n_samples"),
        "accuracy":           round(test_m.get("accuracy", 0) * 100, 2),
        "precision_macro":    round(test_m.get("precision_macro", 0) * 100, 2),
        "recall_macro":       round(test_m.get("recall_macro", 0) * 100, 2),
        "f1_macro":           round(test_m.get("f1_macro", 0) * 100, 2),
        "f1_weighted":        round(test_m.get("f1_weighted", 0) * 100, 2),
        "roc_auc":            test_m.get("roc_auc"),
        "pr_auc":             test_m.get("pr_auc"),
        # Legacy fields kept for frontend compat
        "precision":          round(test_m.get("precision_macro", 0) * 100, 2),
        "recall":             round(test_m.get("recall_macro", 0) * 100, 2),
        "f1":                 round(test_m.get("f1_macro", 0) * 100, 2),
    })

@app.route("/insights/metrics/perclass")
def insights_metrics_perclass():
    """Return per-class precision/recall/F1 for the active model."""
    key = active_model_key()
    metrics_key_map = {
        "random-forest":  "random_forest",
        "svm":            "svm",
        "neural-network": "neural_network",
        "hybrid":         "hybrid",
    }
    mkey = metrics_key_map.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    data = _load_json(metrics_file, {})
    test_m = data.get("independent_test", {})
    return jsonify({
        "model":     key,
        "per_class": test_m.get("per_class", {}),
        "classes":   test_m.get("confusion_matrix_labels", []),
    })

@app.route("/insights/confusion")
def insights_confusion():
    """Return confusion matrix for the active model (from saved JSON)."""
    key = active_model_key()
    metrics_key_map = {
        "random-forest":  "random_forest",
        "svm":            "svm",
        "neural-network": "neural_network",
        "hybrid":         "hybrid",
    }
    mkey = metrics_key_map.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    data = _load_json(metrics_file, {})
    test_m = data.get("independent_test", {})

    return jsonify({
        "model":  key,
        "labels": test_m.get("confusion_matrix_labels", []),
        "matrix": test_m.get("confusion_matrix", []),
    })

@app.route("/insights/traffic")
def insights_traffic():
    counts_by_class: dict = {}
    for r in prediction_history:
        cls = r.get("prediction", "unknown").lower()
        counts_by_class[cls] = counts_by_class.get(cls, 0) + 1
    return jsonify([
        {"name": cls.title(), "count": cnt}
        for cls, cnt in sorted(counts_by_class.items())
    ])

@app.route("/insights/latency")
def insights_latency():
    """Return last N latency samples for trending."""
    n = min(200, max(1, int(request.args.get("n", 50))))
    samples = _latency_samples[-n:]
    avg = round(sum(samples) / len(samples), 3) if samples else None
    sorted_s = sorted(samples)
    def pct(p):
        if not sorted_s:
            return None
        idx = int(len(sorted_s) * p / 100)
        return sorted_s[min(idx, len(sorted_s) - 1)]
    return jsonify({
        "samples":  samples,
        "avg_ms":   avg,
        "p50_ms":   pct(50),
        "p95_ms":   pct(95),
        "p99_ms":   pct(99),
        "n":        len(samples),
    })

# ── Simulate ─────────────────────────────────────────────────────────
@app.route("/simulate", methods=["POST"])
@require_api_key
def simulate():
    """
    Generate synthetic flow feature vectors and run them through inference.
    Body: {"class": "dos", "count": 10}
    Delegates to backend/simulator.py
    """
    try:
        from simulator import generate_synthetic_flows
    except ImportError:
        return jsonify({"error": "simulator.py not found"}), 501

    data  = request.get_json(silent=True) or {}
    cls   = str(data.get("class", "normal")).lower()
    count = min(500, max(1, int(data.get("count", 10))))

    try:
        flows = generate_synthetic_flows(cls, count)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    results = []
    for fv in flows:
        features_df = pd.DataFrame([fv], columns=LIVE_FEATURE_COLUMNS)
        try:
            prediction, confidence, latency_ms = _run_inference(features_df)
        except Exception as exc:
            logger.error(f"Simulation inference error: {exc}")
            continue

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        results.append({
            "synthetic_class": cls,
            "prediction":  prediction,
            "confidence":  round(confidence * 100, 2),
            "latency_ms":  latency_ms,
            "timestamp":   timestamp,
        })

    return jsonify({
        "requested_class": cls,
        "count_requested": count,
        "count_returned":  len(results),
        "results":         results,
        "note":            "These are SYNTHETIC flows — not real captured traffic.",
    })

# ==================================================================
# Entry point
# ==================================================================
if __name__ == "__main__":
    logger.info(f"Starting IDS API on {HOST}:{PORT}")
    app.run(debug=DEBUG_MODE, host=HOST, port=PORT)
