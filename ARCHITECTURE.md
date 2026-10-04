# ARCHITECTURE

**Project:** Cloud-RT-IDS  
**Version:** 3.0 — Enterprise Edition  
**Date:** 2026-10-04

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Cloud-RT-IDS  v3                             │
│                                                                     │
│  ┌──────────────────┐         ┌──────────────────────────────────┐  │
│  │  Traffic Source  │         │        React Frontend            │  │
│  │                  │         │  Dashboard · Monitor · Insights  │  │
│  │  Live Scapy  OR  │         │  Alerts  · Settings              │  │
│  │  /simulate   OR  │         └────────────┬─────────────────────┘  │
│  │  REST /predict   │                      │ HTTP + SSE             │
│  └────────┬─────────┘                      ▼                        │
│           │                  ┌──────────────────────────────────┐   │
│           └────────────────► │      Flask REST API  v3          │   │
│                              │  Rate limiting · API Key auth    │   │
│                              │  JSON structured logging         │   │
│                              └────────────┬─────────────────────┘   │
│                                           │                         │
│                           ┌───────────────▼──────────────────────┐  │
│                           │         Inference Engine             │  │
│                           │                                      │  │
│                           │  ┌─────────────┐  ┌───────────────┐ │  │
│                           │  │  Classifier  │  │ IsolationForest│ │  │
│                           │  │  RF/SVM/NN/  │  │  (zero-day    │ │  │
│                           │  │  Hybrid      │  │   anomaly)    │ │  │
│                           │  └──────┬───────┘  └───────┬───────┘ │  │
│                           │         │  SHAP top-5       │ score   │  │
│                           └─────────┼───────────────────┼─────────┘  │
│                                     │                   │            │
│                           ┌─────────▼───────────────────▼─────────┐  │
│                           │          Alert Engine                  │  │
│                           │  severity · risk · uuid4 ID           │  │
│                           └────────────────┬──────────────────────┘  │
│                                            │                         │
│                    ┌───────────────────────┼───────────────────┐     │
│                    ▼                       ▼                   ▼     │
│           ┌──────────────┐       ┌──────────────┐    ┌──────────────┐│
│           │   SQLite DB  │       │  SSE Stream  │    │  Prometheus  ││
│           │  alerts      │       │  /stream/    │    │  /metrics    ││
│           │  history     │       │  alerts      │    │              ││
│           │  settings    │       │              │    │              ││
│           └──────────────┘       └──────────────┘    └──────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory

| Component | File(s) | Technology | Role |
|---|---|---|---|
| Data pipeline | `backend/cicids_pipeline.py` | pandas, NumPy | CIC-IDS-2017 → 27-feature CSV |
| Packet capture | `backend/url_kdd.py` | Scapy 2.5 | Live bidirectional flow capture |
| Feature extractor | `backend/url_kdd.py` | NumPy | 27-feature vector per flow |
| Synthetic simulator | `backend/simulator.py` | Python + NumPy | 7-class synthetic flow generator |
| Classifier training | `backend/model/train_model.py` | scikit-learn 1.5 | RF + LinearSVM + MLP + Hybrid |
| Anomaly training | `backend/train_anomaly.py` | scikit-learn 1.5 | IsolationForest on normal-only |
| Preprocessing | Embedded in `.pkl` Pipelines | scikit-learn | StandardScaler + OHE |
| SHAP explainability | Inline in `app.py` | shap 0.46 | Top-5 feature contributions per prediction |
| Inference engine | `backend/app.py` | Flask 3.0 + joblib | Model routing + latency + anomaly scoring |
| Alert engine | `backend/app.py` | Python | Severity map, uuid4 IDs, SSE broadcast |
| SSE broadcaster | `backend/app.py` | Flask streaming | Real-time alert push to all subscribers |
| Database | `backend/data/ids.db` | SQLite + SQLAlchemy | Alerts, history, settings |
| Rate limiter | `backend/app.py` | flask-limiter | Per-endpoint request rate limits |
| REST API | `backend/app.py` | Flask 3.0 + flask-cors | 21 endpoints |
| Structured logging | `backend/app.py` | Python logging (JSON) | All requests + predictions |
| Frontend | `frontend/src/` | React 18 + Vite 5 + TypeScript | Security operations dashboard |
| Charts | `frontend/src/` | Recharts 2 | Time-series, bar, pie, line charts |
| Containerisation | `docker/` | Docker + nginx | Backend + frontend images |
| Orchestration | `k8s/` | Kubernetes | Deployments + Services + HPA |
| Tests | `tests/` | pytest | Unit + integration + smoke |

---

## 3. Data Flow

### 3.1 Live Capture Path

```
\Device\NPF_Loopback (Windows Npcap)
            │
            ▼
Scapy sniff() → process_packet()
            │
            ▼
NetworkFlow dataclass (accumulated per flow key)
            │
            ▼
build_feature_vector() → 27-feature dict
            │
            ▼
pd.DataFrame(27 cols)
            │
     ┌──────┴──────────────────────┐
     ▼                             ▼
pipeline.predict()          _anomaly_model
+ predict_proba()           .decision_function()
     │                             │
     ▼                             ▼
prediction + confidence      anomaly_score (0-1)
     │
     ▼
_compute_shap_top5()   (RF only — TreeExplainer)
     │
     ▼
latency_ms measured via perf_counter
     │
     ├──► HistoryRow → SQLite
     │
     └──► if non-normal AND confidence ≥ threshold:
               AlertRow(uuid4 id, severity, shap_top5, anomaly_score)
                    │
                    ├──► SQLite
                    └──► SSE broadcast → all connected clients
```

### 3.2 REST Predict Path

```
POST /predict  { "features": {...27 features...} }
     │
     ▼
Input validation (type checking, protocol enum)
     │
     ▼
pd.DataFrame → classifier → SHAP → anomaly score
     │
     ▼
Return: prediction, confidence, latency_ms, shap_top5, anomaly_score, alert
```

### 3.3 SSE Alert Stream

```
GET /stream/alerts
     │
     ▼
Register Queue in _alert_subscribers list
     │
     ├── Initial replay: last 50 alerts from SQLite
     │
     ▼
Event loop (blocking generator):
  - q.get(timeout=15) → "data: {...}\n\n"
  - queue.Empty timeout → ": heartbeat\n\n"
  - GeneratorExit → deregister queue
```

### 3.4 Training Pipeline

```
MachineLearningCSV/ (2.83M rows, 8 CSVs)
          │
          ▼
cicids_pipeline.py
  → map 79 CIC cols → 27 features
  → label normalisation
  → clean NaN/Inf
  → remove 549,968 duplicates
  → balance: normal=100k, attacks=50k cap
  → stratified 80/20 split
          │
          ▼
live_flows.csv (209,067 rows) + test_flows.csv (52,267 rows)
          │
          ▼
train_model.py
  → ColumnTransformer (StandardScaler + OHE)
  → RF (300 trees, balanced)
  → LinearSVM (SGD modified_huber + CalibratedClassifierCV)
  → MLP (256-128-64, adam, early_stopping)
  → Hybrid VotingClassifier (soft: RF+SVM+MLP)
  → save model_*.pkl + metrics_*.json + metrics_all.json
          │
          ▼
train_anomaly.py
  → normal-only subset (80,000 rows)
  → IsolationForest (200 estimators, contamination=auto)
  → save model_anomaly.pkl + metrics_anomaly.json
```

---

## 4. API Reference

| Endpoint | Method | Rate limit | Description |
|---|---|---|---|
| `/` | GET | — | Version check |
| `/health` | GET | — | Model status, uptime, anomaly model, SQLite, latency |
| `/metrics` | GET | — | Prometheus text format |
| `/stream/alerts` | GET | — | SSE — real-time alert push |
| `/predict` | POST | 120/min | Inference + SHAP + anomaly score |
| `/capture` | POST | 10/min | Live Scapy capture + inference |
| `/simulate` | POST | 30/min | Synthetic flow generation + inference |
| `/feedback` | POST | 60/min | Analyst label correction |
| `/monitor/history` | GET | 300/min | Paginated + filtered prediction history |
| `/alerts` | GET | 300/min | Paginated + filtered alerts |
| `/alerts/<id>` | PATCH | 300/min | Update alert status |
| `/settings` | GET | — | Current IDS settings |
| `/settings` | POST | 300/min | Update settings (SQLite-persisted) |
| `/model/info` | GET | — | Active model metadata + metrics |
| `/model/comparison` | GET | — | All-model comparison table |
| `/model/reload` | POST | — | Reload all .pkl from disk |
| `/model/reset` | POST | — | Reset to defaults |
| `/insights/metrics` | GET | — | Test metrics for active model |
| `/insights/metrics/perclass` | GET | — | Per-class precision/recall/F1 |
| `/insights/confusion` | GET | — | Confusion matrix (dynamic) |
| `/insights/traffic` | GET | — | Live prediction class counts |
| `/insights/latency` | GET | — | Latency samples + p50/p95/p99 |

---

## 5. ML Architecture

### 5.1 Preprocessing

```
Input: 27 features per flow

ColumnTransformer
  ├── StandardScaler           → 26 numeric features (fit on X_train only)
  └── OneHotEncoder            → 1 categorical (protocol → 3 columns)
      handle_unknown="ignore"    tcp / udp / other

Output: 29-column dense matrix
```

### 5.2 Model Specifications

| Model | Algorithm | Key Parameters | Test Accuracy | F1 Macro | Latency |
|---|---|---|---|---|---|
| Random Forest | `RandomForestClassifier` | n_estimators=300, class_weight=balanced | 99.14% | 94.12% | 0.012 ms |
| Linear SVM | `SGDClassifier` + `CalibratedClassifierCV` | loss=modified_huber, alpha=1e-4, cv=3 | 93.03% | 77.47% | 0.003 ms |
| Neural Network | `MLPClassifier` | hidden=(256,128,64), adam, batch=512, early_stop | 99.13% | 94.36% | 0.027 ms |
| **Hybrid** | `VotingClassifier` | soft voting over [RF, SVM, NN] | **99.29%** | **95.05%** | 0.039 ms |
| Anomaly | `IsolationForest` | n_estimators=200, contamination=auto | — | — | — |

### 5.3 Ensemble Strategy

The Hybrid model uses **soft voting**: class probabilities from all three base
estimators are averaged. The class with the highest mean probability wins.
Confidence = `max(averaged_proba)`.

Preferred over hard voting because it preserves uncertainty from each model
and degrades gracefully when one estimator is less confident.

### 5.4 Anomaly Detection Layer

The `IsolationForest` is trained **on normal traffic only**. During inference:

- `decision_function(X)` returns a score; lower = more anomalous
- Normalised to 0–1 range via `score = clamp(0.5 - raw, 0, 1)`
- If classifier predicts "normal" but `anomaly_score > 0.75`: fire an **Anomaly Detection** alert
- This catches zero-days and evasion attempts that fool the classifier

Detection rate on CIC attack traffic: **47.4%** (honest — real attacks often
resemble normal traffic statistically).

### 5.5 SHAP Explainability

For Random Forest predictions only (TreeExplainer — fast, exact):

- Transform features through the pipeline preprocessor
- Run `shap.TreeExplainer(rf).shap_values(X_transformed)`
- Select SHAP values for the predicted class
- Return top 5 features sorted by `|contribution|`
- Positive contribution = pushed toward this attack class
- Negative contribution = pushed toward normal

SHAP values are stored in the alert record and displayed in the Alerts UI.

---

## 6. Database Schema (SQLite)

### `alerts` table

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | uuid4 |
| `event_id` | TEXT | Links alert to history row |
| `timestamp` | TEXT | UTC datetime string |
| `type` | TEXT | "Dos Detection", "Anomaly Detection", etc. |
| `severity` | TEXT | info / medium / high / critical |
| `source_ip` | TEXT | Source IP (or "N/A") |
| `destination_ip` | TEXT | Destination IP (or "N/A") |
| `source_port` | INT | — |
| `destination_port` | INT | — |
| `protocol` | TEXT | tcp / udp / other |
| `confidence` | FLOAT | Model confidence (0–100) |
| `latency_ms` | FLOAT | Inference latency |
| `model_used` | TEXT | Active model key |
| `description` | TEXT | Human-readable description |
| `status` | TEXT | active / reviewed / false-positive / resolved |
| `anomaly_score` | FLOAT | IsolationForest score (0–1) |
| `shap_top5` | TEXT | JSON list of {feature, contribution} |

### `prediction_history` table

| Column | Type | Description |
|---|---|---|
| `id` | INT PK | Auto-increment |
| `event_id` | TEXT | Correlation ID |
| `timestamp` | TEXT | UTC datetime |
| `prediction` | TEXT | Predicted class |
| `confidence` | FLOAT | 0–100 |
| `latency_ms` | FLOAT | ms |
| `model_used` | TEXT | |
| `source_ip` | TEXT | |
| `destination_ip` | TEXT | |
| `source_port` | INT | |
| `destination_port` | INT | |
| `protocol` | TEXT | |
| `anomaly_score` | FLOAT | |

### `settings` table

| Column | Type | Description |
|---|---|---|
| `key` | TEXT PK | Setting name |
| `value` | TEXT | JSON-encoded value |

---

## 7. Alert Severity Rules

| Predicted Class | Base Severity | Upgraded at ≥90% confidence |
|---|---|---|
| normal | info | — |
| probe | medium | high |
| dos | high | critical |
| ddos | critical | critical |
| r2l | high | critical |
| u2r | critical | critical |
| bot | critical | critical |
| web_attack | high | critical |
| anomaly (IF only) | high | high |

---

## 8. Deployment Architecture

### Local Development

```
Terminal 1: cd backend && python app.py      → http://127.0.0.1:5000
Terminal 2: cd frontend && npm run dev       → http://localhost:5173
```

### Docker Compose

```
docker compose up --build

ids-backend   → 0.0.0.0:5000   python:3.11-slim, libpcap
ids-frontend  → 0.0.0.0:8080   nginx:1.27-alpine, static React
```

### Kubernetes

```
kubectl apply -f k8s/

ids-backend   Deployment → ClusterIP Service :5000
ids-frontend  Deployment → NodePort Service  :30080
HPA           → scales backend 1–4 replicas at 70% CPU
```

---

## 9. Streaming Layer

**Current:** SSE (`/stream/alerts`) — push-based, no polling needed.
Each connected client subscribes to a `queue.Queue`. When `_db_append_alert()`
is called, it broadcasts to all active queues.

**Future migration to Redis Streams:**
```python
# Producer (replace _broadcast_alert)
redis_client.xadd("ids:alerts", {"data": json.dumps(alert_dict)})

# Consumer (frontend or separate service)
events = redis_client.xread({"ids:alerts": "$"}, block=1000)
```
No other application code changes because `event_id` propagation is
already in place end-to-end.

---

## 10. Security Architecture

| Control | Implementation | Status |
|---|---|---|
| API authentication | `X-API-Key` header, env `IDS_API_KEY` | ✅ Optional, production-ready |
| Rate limiting | flask-limiter: 120/min predict, 10/min capture | ✅ Active |
| CORS restriction | Configurable `IDS_CORS_ORIGINS` | ✅ |
| Input validation | All 27 features type/enum checked | ✅ |
| No hardcoded secrets | All config via `.env` | ✅ |
| Structured audit log | JSON request log (method, path, status, ms) | ✅ |
| SQL injection | ORM (SQLAlchemy) — no raw SQL | ✅ |
| Capture safety | Probe generator restricted to 127.0.0.1 | ✅ |
| HTTPS | SSL termination via nginx/cloud LB | 📋 Documented |
| Secrets in Kubernetes | `secret.template.yaml` with instructions | 📋 Template provided |

---

*End of ARCHITECTURE.md*
