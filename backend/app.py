"""
Cloud-RT-IDS  ·  Flask API  v3
================================
Enterprise upgrades over v2:
  1. SQLite persistence  (SQLAlchemy) — alerts, history, settings
  2. Rate limiting       (flask-limiter)
  3. SSE streaming       (GET /stream/alerts — no polling needed)
  4. SHAP explainability (top-5 feature contributions per prediction)
  5. IsolationForest     (anomaly layer runs alongside classifier)

Environment variables (see .env.example):
  IDS_HOST               default 0.0.0.0
  IDS_PORT               default 5000
  IDS_CORS_ORIGINS       default http://localhost:5173,http://127.0.0.1:5173
  IDS_MAX_HISTORY        default 10000
  IDS_API_KEY            optional – X-API-Key header auth
  IDS_LOG_LEVEL          default INFO
  IDS_DB_URL             default sqlite:///data/ids.db
"""

import os
import json
import time
import uuid
import queue
import logging
import threading
from datetime import datetime
from functools import wraps

import joblib
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, Response, g, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Text, Float, Integer, String, DateTime
from dotenv import load_dotenv

# Ensure backend/ is on sys.path so relative imports (simulator, url_kdd)
# work regardless of where the process is launched from.
import sys
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from simulator import generate_synthetic_flows
from url_kdd import (
    capture_flows,
    build_feature_vector,
    generate_local_probe_traffic,
)

# ==================================================================
# Environment / config
# ==================================================================
load_dotenv()

HOST         = os.getenv("IDS_HOST", "0.0.0.0")
PORT         = int(os.getenv("IDS_PORT", "5000"))
CORS_ORIGINS = os.getenv(
    "IDS_CORS_ORIGINS",
    "http://localhost:8081,http://127.0.0.1:8081,http://localhost:5173,http://127.0.0.1:5173",
).split(",")
MAX_HISTORY  = int(os.getenv("IDS_MAX_HISTORY", "10000"))
API_KEY      = os.getenv("IDS_API_KEY", "")
LOG_LEVEL    = os.getenv("IDS_LOG_LEVEL", "INFO").upper()
DEBUG_MODE   = os.getenv("IDS_DEBUG", "false").lower() == "true"

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "model")
os.makedirs(DATA_DIR, exist_ok=True)

DB_URL = os.getenv("IDS_DB_URL", f"sqlite:///{os.path.join(DATA_DIR, 'ids.db')}")

# ==================================================================
# Structured JSON logging
# ==================================================================
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "ts":     datetime.utcnow().isoformat() + "Z",
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log)

_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), handlers=[_handler])
logger = logging.getLogger("ids")

# ==================================================================
# Feature schema
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

MODEL_FILES = {
    "random-forest":  "model_random_forest.pkl",
    "svm":            "model_svm.pkl",
    "neural-network": "model_neural_network.pkl",
    "hybrid":         "model_hybrid.pkl",
}
LEGACY_MODEL_FILE      = "model.pkl"
ANOMALY_MODEL_FILE     = "model_anomaly.pkl"
METRICS_ALL_FILE       = os.path.join(MODEL_DIR, "metrics_all.json")

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
# Severity map
# ==================================================================
ATTACK_SEVERITY_MAP = {
    "normal":     "info",
    "probe":      "medium",
    "dos":        "high",
    "ddos":       "critical",
    "r2l":        "high",
    "u2r":        "critical",
    "bot":        "critical",
    "web_attack": "high",
    "anomaly":    "high",
}

def get_alert_severity(prediction: str, confidence: float) -> str:
    base = ATTACK_SEVERITY_MAP.get(prediction.lower(), "medium")
    upgrade = {
        "info":     "info",
        "medium":   "high"     if confidence >= 0.90 else "medium",
        "high":     "critical" if confidence >= 0.90 else "high",
        "critical": "critical",
    }
    return upgrade.get(base, base)

# ==================================================================
# Flask app + extensions
# ==================================================================
app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)

# ── Rate limiter ─────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300/minute"],
    storage_uri="memory://",
)

# ── SQLAlchemy ───────────────────────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"]        = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ==================================================================
# Database models
# ==================================================================
class AlertRow(db.Model):
    __tablename__ = "alerts"
    id              = db.Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id        = db.Column(String(36),  nullable=False, index=True)
    timestamp       = db.Column(String(26),  nullable=False, index=True)
    type            = db.Column(String(64),  nullable=False)
    severity        = db.Column(String(16),  nullable=False, index=True)
    source_ip       = db.Column(String(45),  nullable=False, default="N/A")
    destination_ip  = db.Column(String(45),  nullable=False, default="N/A")
    source_port     = db.Column(Integer,     nullable=True)
    destination_port= db.Column(Integer,     nullable=True)
    protocol        = db.Column(String(8),   nullable=True)
    confidence      = db.Column(Float,       nullable=True)
    latency_ms      = db.Column(Float,       nullable=True)
    model_used      = db.Column(String(32),  nullable=True)
    description     = db.Column(Text,        nullable=True)
    status          = db.Column(String(16),  nullable=False, default="active", index=True)
    anomaly_score   = db.Column(Float,       nullable=True)   # IsolationForest score
    shap_top5       = db.Column(Text,        nullable=True)   # JSON list of {feature, value}

    def to_dict(self):
        return {
            "id":              self.id,
            "event_id":        self.event_id,
            "timestamp":       self.timestamp,
            "type":            self.type,
            "severity":        self.severity,
            "sourceIP":        self.source_ip,
            "destinationIP":   self.destination_ip,
            "sourcePort":      self.source_port,
            "destinationPort": self.destination_port,
            "protocol":        self.protocol,
            "confidence":      self.confidence,
            "latency_ms":      self.latency_ms,
            "model_used":      self.model_used,
            "description":     self.description,
            "status":          self.status,
            "anomaly_score":   self.anomaly_score,
            "shap_top5":       json.loads(self.shap_top5) if self.shap_top5 else [],
        }


class HistoryRow(db.Model):
    __tablename__ = "prediction_history"
    id               = db.Column(Integer,    primary_key=True, autoincrement=True)
    event_id         = db.Column(String(36), nullable=False, index=True)
    timestamp        = db.Column(String(26), nullable=False, index=True)
    ingested_at      = db.Column(String(26), nullable=True)
    prediction       = db.Column(String(32), nullable=False, index=True)
    confidence       = db.Column(Float,      nullable=True)
    latency_ms       = db.Column(Float,      nullable=True)
    model_used       = db.Column(String(32), nullable=True)
    source_ip        = db.Column(String(45), nullable=True)
    destination_ip   = db.Column(String(45), nullable=True)
    source_port      = db.Column(Integer,    nullable=True)
    destination_port = db.Column(Integer,    nullable=True)
    protocol         = db.Column(String(8),  nullable=True)
    anomaly_score    = db.Column(Float,      nullable=True)

    def to_dict(self):
        return {
            "event_id":        self.event_id,
            "timestamp":       self.timestamp,
            "ingested_at":     self.ingested_at,
            "prediction":      self.prediction,
            "confidence":      self.confidence,
            "latency_ms":      self.latency_ms,
            "model_used":      self.model_used,
            "sourceIP":        self.source_ip,
            "destinationIP":   self.destination_ip,
            "sourcePort":      self.source_port,
            "destinationPort": self.destination_port,
            "protocol":        self.protocol,
            "anomaly_score":   self.anomaly_score,
        }


class SettingRow(db.Model):
    __tablename__ = "settings"
    key   = db.Column(String(64), primary_key=True)
    value = db.Column(Text, nullable=False)


# Create tables
with app.app_context():
    db.create_all()
    logger.info("Database tables ready")

# ==================================================================
# Settings (DB-backed)
# ==================================================================
def load_settings() -> dict:
    with app.app_context():
        rows = SettingRow.query.all()
        saved = {}
        for r in rows:
            try:
                saved[r.key] = json.loads(r.value)
            except Exception:
                saved[r.key] = r.value
    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    return merged

def save_settings(s: dict):
    with app.app_context():
        for k, v in s.items():
            row = db.session.get(SettingRow, k)
            if row is None:
                row = SettingRow(key=k, value=json.dumps(v))
                db.session.add(row)
            else:
                row.value = json.dumps(v)
        db.session.commit()

settings = load_settings()

# ==================================================================
# Model loading
# ==================================================================
_models: dict = {}
_metrics_cache: dict = {}
_anomaly_model = None      # IsolationForest pipeline

def _load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default

def _load_metrics_cache():
    global _metrics_cache
    data = _load_json_file(METRICS_ALL_FILE, {})
    _metrics_cache = data if isinstance(data, dict) else {}

def _load_anomaly_model():
    global _anomaly_model
    path = os.path.join(MODEL_DIR, ANOMALY_MODEL_FILE)
    if os.path.exists(path):
        try:
            _anomaly_model = joblib.load(path)
            logger.info("Loaded IsolationForest anomaly model")
        except Exception as exc:
            logger.warning(f"Could not load anomaly model: {exc}")
    else:
        logger.warning("Anomaly model not found — run train_anomaly.py to build it")

def _load_single_model(model_key: str):
    fname = MODEL_FILES.get(model_key)
    if fname:
        path = os.path.join(MODEL_DIR, fname)
        if os.path.exists(path):
            try:
                return joblib.load(path)
            except Exception as exc:
                logger.error(f"Failed to load {fname}: {exc}")
    if model_key == "random-forest":
        legacy = os.path.join(MODEL_DIR, LEGACY_MODEL_FILE)
        if os.path.exists(legacy):
            try:
                return joblib.load(legacy)
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
    _load_anomaly_model()

load_all_models()

def active_model():
    key = settings.get("ml_model", "random-forest")
    return _models.get(key) or next(iter(_models.values()), None)

def active_model_key() -> str:
    key = settings.get("ml_model", "random-forest")
    if key in _models:
        return key
    return next(iter(_models.keys()), "random-forest")

# ==================================================================
# SHAP explainer cache (lazy, one per model key)
# ==================================================================
_shap_explainers: dict = {}
_shap_lock = threading.Lock()

def _get_shap_explainer(model_key: str):
    """Return a cached SHAP explainer for the given model key, or None."""
    try:
        import shap
    except ImportError:
        return None

    with _shap_lock:
        if model_key in _shap_explainers:
            return _shap_explainers[model_key]

        pipeline = _models.get(model_key)
        if pipeline is None:
            return None

        try:
            preprocessor = pipeline.named_steps["preprocessor"]
            estimator    = pipeline.named_steps["model"]

            # Use TreeExplainer for RF (fast), LinearExplainer for SVM, KernelExplainer otherwise
            if hasattr(estimator, "estimators_"):
                # Random Forest or VotingClassifier with RF
                explainer = shap.TreeExplainer(estimator)
            else:
                # Fallback: use a small background to keep it fast
                explainer = None   # skip for SVM/NN to avoid blocking startup

            _shap_explainers[model_key] = explainer
            return explainer
        except Exception as exc:
            logger.warning(f"SHAP explainer init failed for {model_key}: {exc}")
            _shap_explainers[model_key] = None
            return None


def _compute_shap_top5(features_df: pd.DataFrame, model_key: str) -> list:
    """
    Return top-5 SHAP contributions as [{feature, contribution}].
    Falls back to an empty list if SHAP is unavailable or fails.
    """
    try:
        import shap
        pipeline   = _models.get(model_key)
        if pipeline is None:
            return []

        preprocessor = pipeline.named_steps["preprocessor"]
        estimator    = pipeline.named_steps["model"]

        # Transform features through the preprocessor
        X_transformed = preprocessor.transform(features_df)

        # Build feature names after OHE expansion
        num_features = [c for c in LIVE_FEATURE_COLUMNS if c != "protocol"]
        try:
            cat_features = list(preprocessor.named_transformers_["categorical"]
                                .get_feature_names_out(["protocol"]))
        except Exception:
            cat_features = ["protocol_tcp", "protocol_udp", "protocol_other"]
        all_feature_names = num_features + cat_features

        if hasattr(estimator, "estimators_") and not isinstance(estimator,
                   type(None)):
            # Random Forest — TreeExplainer
            explainer  = shap.TreeExplainer(estimator)
            shap_vals  = explainer.shap_values(X_transformed)
            # shap_vals is list of arrays (one per class); pick predicted class
            pred_class_idx = int(np.argmax(estimator.predict_proba(X_transformed)[0]))
            contributions  = shap_vals[pred_class_idx][0]
        else:
            return []   # skip slow explainers at inference time

        # Pair names with absolute contributions, sort, take top 5
        pairs = list(zip(all_feature_names, contributions))
        pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        return [
            {"feature": name, "contribution": round(float(val), 5)}
            for name, val in pairs[:5]
        ]
    except Exception as exc:
        logger.debug(f"SHAP computation skipped: {exc}")
        return []

# ==================================================================
# IsolationForest anomaly scoring
# ==================================================================
def _anomaly_score(features_df: pd.DataFrame) -> float | None:
    """
    Return a normalised IsolationForest anomaly score in [0, 1].
    0.0 = perfectly normal, 1.0 = highly anomalous.

    IsolationForest.decision_function() returns:
      - Higher (more positive) values → normal traffic
      - Lower (more negative) values → anomalous traffic

    The CIC-IDS-2017 decision_function range is approximately [-0.28, +0.17].
    We rescale so that the most anomalous raw value maps to 1.0 and the most
    normal maps to 0.0, then clamp to [0, 1].
    """
    if _anomaly_model is None:
        return None
    try:
        raw = float(_anomaly_model.decision_function(features_df)[0])

        # Empirical bounds from training data (CIC-IDS-2017 normal subset)
        #   raw_min = -0.2843  (most anomalous seen in training)
        #   raw_max =  0.1658  (most normal seen in training)
        RAW_MIN = -0.2843
        RAW_MAX =  0.1658

        # Invert and rescale: low raw → high score (anomalous)
        score = (RAW_MAX - raw) / (RAW_MAX - RAW_MIN)
        score = max(0.0, min(1.0, score))
        return round(score, 4)
    except Exception as exc:
        logger.debug(f"Anomaly scoring failed: {exc}")
        return None

# ==================================================================
# SSE alert broadcaster
# ==================================================================
_alert_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()

def _broadcast_alert(alert_dict: dict):
    """Push a new alert to all active SSE subscribers."""
    payload = f"data: {json.dumps(alert_dict)}\n\n"
    with _subscribers_lock:
        dead = []
        for q in _alert_subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _alert_subscribers.remove(q)

# ==================================================================
# DB helpers
# ==================================================================
def _db_append_alert(alert: AlertRow):
    with app.app_context():
        db.session.add(alert)
        db.session.commit()
    _broadcast_alert(alert.to_dict())

def _db_append_history(row: HistoryRow):
    with app.app_context():
        db.session.add(row)
        # Cap history
        count = db.session.query(HistoryRow).count()
        if count > MAX_HISTORY:
            oldest = (db.session.query(HistoryRow)
                      .order_by(HistoryRow.id.asc())
                      .first())
            if oldest:
                db.session.delete(oldest)
        db.session.commit()

# ==================================================================
# Request logging
# ==================================================================
_request_count    = 0
_prediction_count_by_class: dict = {}
_latency_samples:  list = []
_start_time = time.monotonic()

@app.before_request
def _before():
    global _request_count
    _request_count += 1
    g.start_ts = time.perf_counter()

@app.after_request
def _after(response):
    elapsed_ms = round((time.perf_counter() - g.start_ts) * 1000, 2)
    logger.info(json.dumps({
        "method":      request.method,
        "path":        request.path,
        "status":      response.status_code,
        "duration_ms": elapsed_ms,
    }))
    return response

# ==================================================================
# Auth decorator
# ==================================================================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_KEY:
            key = request.headers.get("X-API-Key", "")
            if key != API_KEY:
                logger.warning("Unauthorized request")
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ==================================================================
# Prediction core
# ==================================================================
def _run_inference(features_df: pd.DataFrame):
    """
    Run classifier inference + SHAP + anomaly score.
    Returns (prediction, confidence, latency_ms, shap_top5, anomaly_score).
    """
    model = active_model()
    if model is None:
        raise RuntimeError("No model loaded")

    t0         = time.perf_counter()
    prediction = str(model.predict(features_df)[0])
    proba      = model.predict_proba(features_df)
    confidence = float(np.max(proba))
    latency_ms = round((time.perf_counter() - t0) * 1000, 4)

    # In-memory stats
    _prediction_count_by_class[prediction] = (
        _prediction_count_by_class.get(prediction, 0) + 1
    )
    _latency_samples.append(latency_ms)
    if len(_latency_samples) > 1000:
        del _latency_samples[0]

    # SHAP (only for RF — fast tree explainer)
    mkey = active_model_key()
    shap_top5 = _compute_shap_top5(features_df, mkey) if mkey == "random-forest" else []

    # Anomaly score
    ascore = _anomaly_score(features_df)

    return prediction, confidence, latency_ms, shap_top5, ascore

# ==================================================================
# ────────────────────────  ROUTES  ────────────────────────────────
# ==================================================================

# ── Health ──────────────────────────────────────────────────────────
@app.route("/")
def home():
    return jsonify({"message": "Intrusion Detection API Running!", "version": "3.0"})

@app.route("/health")
def health():
    uptime      = round(time.monotonic() - _start_time, 1)
    avg_latency = (
        round(sum(_latency_samples) / len(_latency_samples), 3)
        if _latency_samples else None
    )
    with app.app_context():
        alert_count   = db.session.query(AlertRow).count()
        history_count = db.session.query(HistoryRow).count()
    return jsonify({
        "status":                  "ok",
        "uptime_seconds":          uptime,
        "active_model":            active_model_key(),
        "models_loaded":           list(_models.keys()),
        "model_loaded":            active_model() is not None,
        "anomaly_model_loaded":    _anomaly_model is not None,
        "metrics_loaded":          bool(_metrics_cache),
        "history_count":           history_count,
        "alert_count":             alert_count,
        "avg_inference_latency_ms": avg_latency,
        "feature_schema_version":  FEATURE_SCHEMA_VERSION,
        "persistence":             "sqlite",
    })

# ── Prometheus metrics ───────────────────────────────────────────────
@app.route("/metrics")
def prometheus_metrics():
    uptime      = round(time.monotonic() - _start_time, 1)
    total_preds = sum(_prediction_count_by_class.values())
    avg_latency = (
        round(sum(_latency_samples) / len(_latency_samples), 3)
        if _latency_samples else 0
    )
    with app.app_context():
        alert_count   = db.session.query(AlertRow).count()
        history_count = db.session.query(HistoryRow).count()

    lines = [
        "# HELP ids_uptime_seconds Seconds since backend started",
        "# TYPE ids_uptime_seconds gauge",
        f"ids_uptime_seconds {uptime}",
        "",
        "# HELP ids_requests_total Total HTTP requests",
        "# TYPE ids_requests_total counter",
        f"ids_requests_total {_request_count}",
        "",
        "# HELP ids_predictions_total Total predictions",
        "# TYPE ids_predictions_total counter",
        f"ids_predictions_total {total_preds}",
        "",
        "# HELP ids_predictions_by_class Predictions by class",
        "# TYPE ids_predictions_by_class counter",
    ]
    for cls, cnt in _prediction_count_by_class.items():
        lines.append(f'ids_predictions_by_class{{class="{cls}"}} {cnt}')
    lines += [
        "",
        "# HELP ids_alerts_total Total alerts in DB",
        "# TYPE ids_alerts_total counter",
        f"ids_alerts_total {alert_count}",
        "",
        "# HELP ids_inference_latency_ms_avg Average inference latency ms",
        "# TYPE ids_inference_latency_ms_avg gauge",
        f"ids_inference_latency_ms_avg {avg_latency}",
        "",
        "# HELP ids_history_size Prediction history rows",
        "# TYPE ids_history_size gauge",
        f"ids_history_size {history_count}",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain; version=0.0.4")

# ── SSE alert stream ─────────────────────────────────────────────────
@app.route("/stream/alerts")
def stream_alerts():
    """
    Server-Sent Events endpoint.
    Clients connect once; new alerts are pushed immediately.
    """
    q: queue.Queue = queue.Queue(maxsize=100)
    with _subscribers_lock:
        _alert_subscribers.append(q)

    def generate():
        # Send a heartbeat comment every 15 s to keep the connection alive
        try:
            # Send all active alerts on initial connect
            with app.app_context():
                existing = (AlertRow.query
                            .order_by(AlertRow.timestamp.desc())
                            .limit(50)
                            .all())
            for alert in reversed(existing):
                yield f"data: {json.dumps(alert.to_dict())}\n\n"

            while True:
                try:
                    msg = q.get(timeout=15)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with _subscribers_lock:
                if q in _alert_subscribers:
                    _alert_subscribers.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# ── Predict ──────────────────────────────────────────────────────────
@app.route("/predict", methods=["POST"])
@require_api_key
@limiter.limit("120/minute")
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
        prediction, confidence, latency_ms, shap_top5, ascore = _run_inference(features_df)
    except Exception as exc:
        logger.error(f"Inference error: {exc}")
        return jsonify({"error": f"Inference failed: {exc}"}), 500

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    event_id  = str(uuid.uuid4())

    # Persist history
    hist_row = HistoryRow(
        event_id=event_id,
        timestamp=timestamp,
        prediction=prediction,
        confidence=round(confidence * 100, 2),
        latency_ms=latency_ms,
        model_used=active_model_key(),
        source_ip="N/A",
        destination_ip="N/A",
        source_port=int(numeric_features["source_port"]),
        destination_port=int(numeric_features["destination_port"]),
        protocol=numeric_features["protocol"],
        anomaly_score=ascore,
    )
    threading.Thread(target=_db_append_history, args=(hist_row,), daemon=True).start()

    # Generate alert if warranted
    alert_dict = None
    if (
        prediction.lower() != "normal"
        and confidence * 100 >= settings["sensitivity_threshold"]
    ):
        severity = get_alert_severity(prediction, confidence)
        description = (
            f"{prediction.title()} activity detected. "
            f"Confidence: {confidence*100:.1f}%. "
            f"Protocol: {numeric_features['protocol'].upper()}, "
            f"destination port: {int(numeric_features['destination_port'])}."
        )
        if ascore is not None and ascore > 0.6:
            description += f" Anomaly score: {ascore:.2f} (elevated)."

        alert = AlertRow(
            id=str(uuid.uuid4()),
            event_id=event_id,
            timestamp=timestamp,
            type=f"{prediction.title()} Detection",
            severity=severity,
            source_ip="N/A",
            destination_ip="N/A",
            source_port=int(numeric_features["source_port"]),
            destination_port=int(numeric_features["destination_port"]),
            protocol=numeric_features["protocol"],
            confidence=round(confidence * 100, 2),
            latency_ms=latency_ms,
            model_used=active_model_key(),
            description=description,
            status="active",
            anomaly_score=ascore,
            shap_top5=json.dumps(shap_top5),
        )
        _db_append_alert(alert)
        alert_dict = alert.to_dict()

    # Anomaly-only alert: classifier says normal but anomaly score is high
    elif (
        prediction.lower() == "normal"
        and ascore is not None
        and ascore > 0.60
    ):
        alert = AlertRow(
            id=str(uuid.uuid4()),
            event_id=event_id,
            timestamp=timestamp,
            type="Anomaly Detection",
            severity="high",
            source_ip="N/A",
            destination_ip="N/A",
            source_port=int(numeric_features["source_port"]),
            destination_port=int(numeric_features["destination_port"]),
            protocol=numeric_features["protocol"],
            confidence=round(ascore * 100, 2),
            latency_ms=latency_ms,
            model_used="isolation-forest",
            description=(
                f"Anomalous flow detected by IsolationForest (score={ascore:.2f}). "
                "Classifier returned normal — potential zero-day or evasion attempt."
            ),
            status="active",
            anomaly_score=ascore,
            shap_top5=json.dumps(shap_top5),
        )
        _db_append_alert(alert)
        alert_dict = alert.to_dict()

    return jsonify({
        "event_id":      event_id,
        "prediction":    prediction,
        "confidence":    confidence,
        "latency_ms":    latency_ms,
        "timestamp":     timestamp,
        "model_used":    active_model_key(),
        "shap_top5":     shap_top5,
        "anomaly_score": ascore,
        "alert":         alert_dict,
        "features_used": {f: numeric_features[f] for f in LIVE_FEATURE_COLUMNS},
    })

# ── Live capture ─────────────────────────────────────────────────────
@app.route("/capture", methods=["POST"])
@require_api_key
@limiter.limit("10/minute")
def capture_network_flows():
    try:
        data         = request.get_json(silent=True) or {}
        capture_time = float(data.get("capture_time", 8))
        mode         = str(data.get("mode", "normal")).lower()

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

        detected    = []
        ingested_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        for flow in captured_flows:
            fv          = build_feature_vector(flow)
            features_df = pd.DataFrame([fv], columns=LIVE_FEATURE_COLUMNS)

            try:
                prediction, confidence, latency_ms, shap_top5, ascore = _run_inference(features_df)
            except Exception as exc:
                logger.error(f"Inference error on captured flow: {exc}")
                continue

            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            event_id  = str(uuid.uuid4())

            hist_row = HistoryRow(
                event_id=event_id,
                timestamp=timestamp,
                ingested_at=ingested_at,
                prediction=prediction,
                confidence=round(confidence * 100, 2),
                latency_ms=latency_ms,
                model_used=active_model_key(),
                source_ip=flow.src_ip,
                destination_ip=flow.dst_ip,
                source_port=int(flow.src_port),
                destination_port=int(flow.dst_port),
                protocol=str(flow.protocol).lower(),
                anomaly_score=ascore,
            )
            _db_append_history(hist_row)

            if (
                prediction.lower() != "normal"
                and confidence * 100 >= settings["sensitivity_threshold"]
            ):
                severity    = get_alert_severity(prediction, confidence)
                description = (
                    f"{prediction.title()} activity detected. "
                    f"Confidence: {confidence*100:.1f}%. "
                    f"{str(flow.protocol).upper()} traffic from "
                    f"{flow.src_ip}:{flow.src_port} to "
                    f"{flow.dst_ip}:{flow.dst_port}."
                )
                alert = AlertRow(
                    id=str(uuid.uuid4()),
                    event_id=event_id,
                    timestamp=timestamp,
                    type=f"{prediction.title()} Detection",
                    severity=severity,
                    source_ip=flow.src_ip,
                    destination_ip=flow.dst_ip,
                    source_port=int(flow.src_port),
                    destination_port=int(flow.dst_port),
                    protocol=str(flow.protocol).lower(),
                    confidence=round(confidence * 100, 2),
                    latency_ms=latency_ms,
                    model_used=active_model_key(),
                    description=description,
                    status="active",
                    anomaly_score=ascore,
                    shap_top5=json.dumps(shap_top5),
                )
                _db_append_alert(alert)

            detected.append({
                "event_id":    event_id,
                "features":    fv,
                "prediction":  prediction,
                "confidence":  confidence,
                "latency_ms":  latency_ms,
                "shap_top5":   shap_top5,
                "anomaly_score": ascore,
                "timestamp":   timestamp,
            })

        return jsonify({
            "message":        "Network capture and detection completed",
            "mode":           mode,
            "flows_captured": len(detected),
            "flows":          detected,
        })

    except Exception as exc:
        logger.error(f"Capture failed: {exc}")
        return jsonify({"error": f"Network capture failed: {exc}"}), 500

# ── Monitor history ──────────────────────────────────────────────────
@app.route("/monitor/history")
@require_api_key
def monitor_history():
    page       = max(1, int(request.args.get("page", 1)))
    limit      = min(200, max(1, int(request.args.get("limit", 50))))
    pred_filter = request.args.get("prediction", "").lower()

    with app.app_context():
        query = db.session.query(HistoryRow)
        if pred_filter:
            query = query.filter(HistoryRow.prediction == pred_filter)
        total   = query.count()
        records = (query.order_by(HistoryRow.id.desc())
                   .offset((page - 1) * limit)
                   .limit(limit)
                   .all())

        counts_by_class: dict = {}
        for r in db.session.query(HistoryRow).all():
            cls = (r.prediction or "unknown").lower()
            counts_by_class[cls] = counts_by_class.get(cls, 0) + 1

    normal_count = counts_by_class.get("normal", 0)
    attack_count = sum(v for k, v in counts_by_class.items() if k != "normal")
    total_all    = normal_count + attack_count
    attack_rate  = round(attack_count / total_all * 100, 2) if total_all > 0 else 0.0
    avg_latency  = (
        round(sum(_latency_samples) / len(_latency_samples), 3)
        if _latency_samples else None
    )

    return jsonify({
        "records":         [r.to_dict() for r in records],
        "total_records":   total,
        "page":            page,
        "limit":           limit,
        "normal_count":    normal_count,
        "attack_count":    attack_count,
        "attack_rate":     attack_rate,
        "counts_by_class": counts_by_class,
        "avg_latency_ms":  avg_latency,
        "active_model":    active_model_key(),
    })

# ── Alerts ───────────────────────────────────────────────────────────
@app.route("/alerts")
@require_api_key
def get_alerts():
    page     = max(1, int(request.args.get("page", 1)))
    limit    = min(200, max(1, int(request.args.get("limit", 50))))
    severity = request.args.get("severity", "").lower()
    pred     = request.args.get("prediction", "").lower()
    status   = request.args.get("status", "").lower()

    with app.app_context():
        query = db.session.query(AlertRow)
        if severity:
            query = query.filter(AlertRow.severity == severity)
        if pred:
            query = query.filter(AlertRow.type.ilike(f"%{pred}%"))
        if status:
            query = query.filter(AlertRow.status == status)

        total = query.count()
        items = (query.order_by(AlertRow.timestamp.desc())
                 .offset((page - 1) * limit)
                 .limit(limit)
                 .all())

    return jsonify({
        "alerts": [a.to_dict() for a in items],
        "total":  total,
        "page":   page,
        "limit":  limit,
    })

@app.route("/alerts/<alert_id>", methods=["PATCH"])
@require_api_key
def update_alert(alert_id: str):
    data       = request.get_json(silent=True) or {}
    new_status = data.get("status")
    allowed    = {"active", "reviewed", "false-positive", "resolved"}
    if new_status not in allowed:
        return jsonify({"error": "Invalid status", "allowed": list(allowed)}), 400

    with app.app_context():
        alert = db.session.get(AlertRow, alert_id)
        if alert is None:
            return jsonify({"error": f"Alert {alert_id} not found"}), 404
        alert.status = new_status
        db.session.commit()
        return jsonify({"message": "Alert updated", "alert": alert.to_dict()})

# ── Settings ──────────────────────────────────────────────────────────
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
            return jsonify({"error": "Unsupported model", "allowed_models": allowed_models}), 400
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

# ── Model management ──────────────────────────────────────────────────
_METRICS_KEY_MAP = {
    "random-forest":  "random_forest",
    "svm":            "svm",
    "neural-network": "neural_network",
    "hybrid":         "hybrid",
}

@app.route("/model/info")
def model_info():
    key          = active_model_key()
    mkey         = _METRICS_KEY_MAP.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    model_metrics = _load_json_file(metrics_file, {})
    return jsonify({
        "active_model_key":       key,
        "available_models":       list(_models.keys()),
        "anomaly_model_loaded":   _anomaly_model is not None,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_columns":        LIVE_FEATURE_COLUMNS,
        "n_features":             len(LIVE_FEATURE_COLUMNS),
        "training_timestamp":     model_metrics.get("training_timestamp"),
        "n_train_samples":        model_metrics.get("n_train_samples"),
        "n_test_samples":         model_metrics.get("n_test_samples"),
        "classes":                model_metrics.get("classes"),
        "hyperparameters":        model_metrics.get("hyperparameters"),
        "train_dataset_md5":      model_metrics.get("train_dataset_md5"),
        "independent_test":       model_metrics.get("independent_test", {}),
        "feature_importances":    model_metrics.get("feature_importances"),
    })

@app.route("/model/comparison")
def model_comparison():
    summary = _load_json_file(METRICS_ALL_FILE, {})
    return jsonify(summary.get("model_comparison", []))

@app.route("/model/reload", methods=["POST"])
@require_api_key
def reload_model():
    load_all_models()
    if not _models:
        return jsonify({"error": "Failed to reload models"}), 500
    return jsonify({"message": "Models reloaded", "available": list(_models.keys()),
                    "anomaly_model": _anomaly_model is not None})

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

@app.route("/model/retrain", methods=["POST"])
@require_api_key
def retrain_model():
    return jsonify({"error": "Use train_model.py to retrain — automatic retraining not enabled"}), 501

# ── Insights ──────────────────────────────────────────────────────────
@app.route("/insights/metrics")
def insights_metrics():
    key          = active_model_key()
    mkey         = _METRICS_KEY_MAP.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    data         = _load_json_file(metrics_file, {})

    if not data:
        summary = _load_json_file(METRICS_ALL_FILE, {})
        test_m  = summary.get("current_metrics", {})
    else:
        test_m = data.get("independent_test", {})

    if not test_m:
        return jsonify({"error": "Metrics not available — run train_model.py first"}), 503

    return jsonify({
        "model":           key,
        "evaluation_type": "independent_test_set",
        "n_test_samples":  test_m.get("n_samples"),
        "accuracy":        round(test_m.get("accuracy", 0) * 100, 2),
        "precision_macro": round(test_m.get("precision_macro", 0) * 100, 2),
        "recall_macro":    round(test_m.get("recall_macro", 0) * 100, 2),
        "f1_macro":        round(test_m.get("f1_macro", 0) * 100, 2),
        "f1_weighted":     round(test_m.get("f1_weighted", 0) * 100, 2),
        "roc_auc":         test_m.get("roc_auc"),
        "pr_auc":          test_m.get("pr_auc"),
        # Legacy compat
        "precision":       round(test_m.get("precision_macro", 0) * 100, 2),
        "recall":          round(test_m.get("recall_macro", 0) * 100, 2),
        "f1":              round(test_m.get("f1_macro", 0) * 100, 2),
    })

@app.route("/insights/metrics/perclass")
def insights_metrics_perclass():
    key          = active_model_key()
    mkey         = _METRICS_KEY_MAP.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    data         = _load_json_file(metrics_file, {})
    test_m       = data.get("independent_test", {})
    return jsonify({
        "model":     key,
        "per_class": test_m.get("per_class", {}),
        "classes":   test_m.get("confusion_matrix_labels", []),
    })

@app.route("/insights/confusion")
def insights_confusion():
    key          = active_model_key()
    mkey         = _METRICS_KEY_MAP.get(key, key)
    metrics_file = os.path.join(MODEL_DIR, f"metrics_{mkey}.json")
    data         = _load_json_file(metrics_file, {})
    test_m       = data.get("independent_test", {})
    return jsonify({
        "model":  key,
        "labels": test_m.get("confusion_matrix_labels", []),
        "matrix": test_m.get("confusion_matrix", []),
    })

@app.route("/insights/traffic")
def insights_traffic():
    counts: dict = {}
    for r in db.session.query(HistoryRow).all():
        cls = (r.prediction or "unknown").lower()
        counts[cls] = counts.get(cls, 0) + 1
    return jsonify([
        {"name": cls.title(), "count": cnt}
        for cls, cnt in sorted(counts.items())
    ])

@app.route("/insights/latency")
def insights_latency():
    n        = min(200, max(1, int(request.args.get("n", 50))))
    samples  = _latency_samples[-n:]
    avg      = round(sum(samples) / len(samples), 3) if samples else None
    sorted_s = sorted(samples)

    def pct(p):
        if not sorted_s:
            return None
        idx = int(len(sorted_s) * p / 100)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    return jsonify({
        "samples": samples,
        "avg_ms":  avg,
        "p50_ms":  pct(50),
        "p95_ms":  pct(95),
        "p99_ms":  pct(99),
        "n":       len(samples),
    })

# ── Simulate ──────────────────────────────────────────────────────────
@app.route("/simulate", methods=["POST"])
@require_api_key
@limiter.limit("30/minute")
def simulate():
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
            prediction, confidence, latency_ms, shap_top5, ascore = _run_inference(features_df)
        except Exception as exc:
            logger.error(f"Simulation inference error: {exc}")
            continue

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        event_id  = str(uuid.uuid4())

        # Persist to prediction history so it shows in Monitor + Dashboard
        hist_row = HistoryRow(
            event_id=event_id,
            timestamp=timestamp,
            prediction=prediction,
            confidence=round(confidence * 100, 2),
            latency_ms=latency_ms,
            model_used=f"{active_model_key()} [synthetic:{cls}]",
            source_ip="synthetic",
            destination_ip="synthetic",
            source_port=int(fv.get("source_port", 0)),
            destination_port=int(fv.get("destination_port", 0)),
            protocol=str(fv.get("protocol", "tcp")),
            anomaly_score=ascore,
        )
        _db_append_history(hist_row)

        # Generate alert if warranted (same rules as live traffic)
        if (
            prediction.lower() != "normal"
            and confidence * 100 >= settings["sensitivity_threshold"]
        ):
            severity = get_alert_severity(prediction, confidence)
            alert = AlertRow(
                id=str(uuid.uuid4()),
                event_id=event_id,
                timestamp=timestamp,
                type=f"{prediction.title()} Detection",
                severity=severity,
                source_ip="synthetic",
                destination_ip="synthetic",
                source_port=int(fv.get("source_port", 0)),
                destination_port=int(fv.get("destination_port", 0)),
                protocol=str(fv.get("protocol", "tcp")),
                confidence=round(confidence * 100, 2),
                latency_ms=latency_ms,
                model_used=f"{active_model_key()} [synthetic:{cls}]",
                description=(
                    f"[SYNTHETIC] {prediction.title()} detected from simulated "
                    f"{cls} traffic. Confidence: {confidence*100:.1f}%."
                ),
                status="active",
                anomaly_score=ascore,
                shap_top5=json.dumps(shap_top5),
            )
            _db_append_alert(alert)

        results.append({
            "event_id":      event_id,
            "synthetic_class": cls,
            "prediction":    prediction,
            "confidence":    round(confidence * 100, 2),
            "latency_ms":    latency_ms,
            "shap_top5":     shap_top5,
            "anomaly_score": ascore,
            "timestamp":     timestamp,
        })

    return jsonify({
        "requested_class": cls,
        "count_requested": count,
        "count_returned":  len(results),
        "results":         results,
        "note":            "These are SYNTHETIC flows — not real captured traffic.",
    })

# ── Feedback (confirmed labels for future retraining) ─────────────────
@app.route("/feedback", methods=["POST"])
@require_api_key
@limiter.limit("60/minute")
def feedback():
    """
    Accept analyst-confirmed labels for alerts.
    Body: {"alert_id": "...", "true_label": "dos"}
    Persists to data/feedback.jsonl for future retraining use.
    """
    data = request.get_json(silent=True) or {}
    alert_id   = data.get("alert_id")
    true_label = data.get("true_label", "").lower()

    valid_labels = {"normal", "probe", "dos", "ddos", "r2l", "bot", "web_attack"}
    if not alert_id:
        return jsonify({"error": "alert_id required"}), 400
    if true_label not in valid_labels:
        return jsonify({"error": f"true_label must be one of {valid_labels}"}), 400

    with app.app_context():
        alert = db.session.get(AlertRow, str(alert_id))
        if alert is None:
            return jsonify({"error": f"Alert {alert_id} not found"}), 404
        alert.status = "reviewed"
        db.session.commit()
        alert_dict = alert.to_dict()

    feedback_path = os.path.join(DATA_DIR, "feedback.jsonl")
    entry = {
        "alert_id":   alert_id,
        "event_id":   alert_dict.get("event_id"),
        "true_label": true_label,
        "timestamp":  datetime.utcnow().isoformat() + "Z",
    }
    with open(feedback_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")

    logger.info(f"Feedback recorded: alert={alert_id} true_label={true_label}")
    return jsonify({"message": "Feedback recorded", "entry": entry})

# ==================================================================
# Entry point
# ==================================================================
if __name__ == "__main__":
    logger.info(f"Starting IDS API v3 on {HOST}:{PORT}")
    app.run(debug=DEBUG_MODE, host=HOST, port=PORT, threaded=True)
