# ARCHITECTURE

**Project:** Cloud-RT-IDS  
**Document version:** 2.0  
**Date:** 2026-09-23

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Cloud-RT-IDS  v2                            │
│                                                                  │
│  ┌─────────────────┐     ┌────────────────────────────────────┐ │
│  │  Traffic Source │     │           React Frontend           │ │
│  │                 │     │  Dashboard · Monitor · Insights    │ │
│  │  Live Scapy     │     │  Alerts · Settings                 │ │
│  │  Capture  OR    │     └──────────────┬─────────────────────┘ │
│  │  Synthetic      │                    │  HTTP (polling / SSE) │
│  │  Simulator      │                    ▼                       │
│  └────────┬────────┘     ┌────────────────────────────────────┐ │
│           │              │        Flask REST API               │ │
│           │ POST /capture│  /predict  /capture  /simulate     │ │
│           └─────────────►│  /alerts  /insights  /health       │ │
│                          │  /metrics  /model/info             │ │
│                          └──────────────┬─────────────────────┘ │
│                                         │                       │
│                          ┌──────────────▼─────────────────────┐ │
│                          │      Inference Engine              │ │
│                          │                                    │ │
│                          │  Random Forest  (model_rf.pkl)     │ │
│                          │  SVM            (model_svm.pkl)    │ │
│                          │  Neural Network (model_nn.pkl)     │ │
│                          │  Hybrid Ensemble(model_hybrid.pkl) │ │
│                          │                                    │ │
│                          │  Active model selected via         │ │
│                          │  /settings  ml_model key          │ │
│                          └──────────────┬─────────────────────┘ │
│                                         │                       │
│                    ┌────────────────────┼──────────────────┐   │
│                    │                    │                   │   │
│                    ▼                    ▼                   ▼   │
│           ┌──────────────┐  ┌─────────────────┐  ┌──────────┐ │
│           │ Alert Engine │  │ Prediction Hist │  │ settings │ │
│           │ severity map │  │ (JSON, 10k cap) │  │  .json   │ │
│           │ uuid4 IDs    │  │                 │  │          │ │
│           │ alerts.json  │  │ history.json    │  │          │ │
│           └──────────────┘  └─────────────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory

| Component | File(s) | Technology | Role |
|---|---|---|---|
| Packet capture | `backend/url_kdd.py` | Scapy 2.5 | Capture live flows on loopback |
| Flow builder | `backend/url_kdd.py` | Python dataclass | Bidirectional flow aggregation |
| Feature extractor | `backend/url_kdd.py` | NumPy | 27-feature vector per flow |
| Traffic simulator | `backend/simulator.py` | Python + NumPy | Synthetic flows for all 5 classes |
| Training pipeline | `backend/model/train_model.py` | scikit-learn 1.5 | RF + SVM + NN + Hybrid |
| Preprocessing | embedded in `.pkl` Pipelines | scikit-learn | StandardScaler + OHE |
| Inference engine | `backend/app.py` | Flask + joblib | Model routing + latency |
| Alert engine | `backend/app.py` | Python | Severity map, uuid4 IDs |
| Persistence | `backend/data/*.json` | JSON files | Alerts, history, settings |
| REST API | `backend/app.py` | Flask 3.0 + flask-cors | 18 endpoints |
| Structured logging | `backend/app.py` | Python logging (JSON) | All requests + predictions |
| Frontend | `frontend/src/` | React 18 + Vite 5 + TS | Dashboard + monitoring UI |
| Charts | `frontend/src/` | Recharts 2 | Time-series + bar + pie + line |
| Containerisation | `docker/` | Docker + nginx | Backend + frontend images |
| Orchestration | `k8s/` | Kubernetes | Deployments + HPA |
| Tests | `tests/` | pytest | Unit + integration + smoke |

---

## 3. Data Flow

### 3.1 Live Capture Path

```
\Device\NPF_Loopback (Windows Npcap)
          │
          ▼
Scapy sniff()  →  process_packet()
          │
          ▼
NetworkFlow dataclass  (accumulated per flow key)
          │
          ▼
build_feature_vector()  →  27-feature dict
          │
          ▼
pd.DataFrame(27 cols)
          │
          ▼
pipeline.predict()  +  pipeline.predict_proba()
          │
     perf_counter timing  →  latency_ms
          │
     ┌────┴────┐
     ▼         ▼
prediction   confidence
     │
     ├──► prediction_history.json  (capped 10k)
     │
     └──► if non-normal AND confidence ≥ threshold:
              Alert object (uuid4 id, severity, event_id)
                  │
                  ▼
              alerts.json
```

### 3.2 Manual Prediction Path

```
POST /predict  { "features": {...27 features...} }
     │
     ▼
Input validation (type, enum, completeness)
     │
     ▼
pd.DataFrame  →  active_model().predict()
     │
     ▼
Return: prediction, confidence, latency_ms, event_id
```

### 3.3 Training Pipeline

```
live_flows.csv  +  test_flows.csv
     │
     ▼
clean_dataset()  →  lowercase labels, drop NaN, coerce numerics
     │
     ▼
train_test_split(stratify, 80/20, seed=42)
     │
     ▼
ColumnTransformer: StandardScaler(26) + OHE(1)
     │
     ├──► RandomForestClassifier(300 trees, balanced)
     ├──► SVC(rbf, C=10, probability=True, balanced)
     ├──► MLPClassifier(128-64-32, adam, early_stop)
     └──► VotingClassifier(soft, RF+SVM+NN)
          │
          ▼
For each model:
  - metrics_<name>.json  (full metrics, MD5, schema version)
  - model_<name>.pkl
          │
          ▼
metrics_all.json  (comparison table + default model metrics)
          │
          ▼
experiments/baseline/<timestamp>/  (archived run)
```

---

## 4. API Endpoint Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/` | GET | — | Health message |
| `/health` | GET | — | Structured health: model, uptime, latency |
| `/metrics` | GET | — | Prometheus-compatible text metrics |
| `/predict` | POST | ✓ | Single-flow inference |
| `/capture` | POST | ✓ | Live Scapy capture + inference |
| `/simulate` | POST | ✓ | Synthetic flow generation + inference |
| `/monitor/history` | GET | ✓ | Paginated prediction history |
| `/alerts` | GET | ✓ | Paginated + filtered alerts |
| `/alerts/<id>` | PATCH | ✓ | Update alert status |
| `/settings` | GET | — | Current IDS settings |
| `/settings` | POST | ✓ | Update settings (persisted) |
| `/model/info` | GET | — | Active model metadata + metrics |
| `/model/comparison` | GET | — | All models comparison table |
| `/model/reload` | POST | ✓ | Reload model artifacts from disk |
| `/model/reset` | POST | ✓ | Reset to defaults + reload |
| `/insights/metrics` | GET | — | Active model test metrics |
| `/insights/metrics/perclass` | GET | — | Per-class precision/recall/F1 |
| `/insights/confusion` | GET | — | Confusion matrix (dynamic) |
| `/insights/traffic` | GET | — | Live prediction class counts |
| `/insights/latency` | GET | — | Latency samples + p50/p95/p99 |

Auth ✓ = requires `X-API-Key` header when `IDS_API_KEY` env variable is set.

---

## 5. ML Model Architecture

### 5.1 Preprocessing (shared by all models)

```
Input: 27 features per flow

ColumnTransformer
  ├── StandardScaler        → 26 numeric features
  └── OneHotEncoder         → 1 categorical (protocol → 3 columns)
      handle_unknown=ignore    tcp / udp / other

Output: dense feature matrix (29 values after OHE expansion)
```

### 5.2 Model Specifications

| Model | Class | Key Parameters |
|---|---|---|
| Random Forest | `RandomForestClassifier` | n_estimators=300, class_weight=balanced, random_state=42 |
| SVM | `SVC` | kernel=rbf, C=10.0, gamma=scale, probability=True, class_weight=balanced |
| Neural Network | `MLPClassifier` | hidden=(128,64,32), relu, adam, alpha=1e-4, early_stopping=True |
| Hybrid | `VotingClassifier` | voting=soft, estimators=[RF, SVM, NN] |

### 5.3 Ensemble Strategy

The Hybrid model uses **soft voting**: class probabilities from each base
estimator are averaged. The class with the highest mean probability is the
final prediction. Confidence is `max(averaged_proba)`.

This is preferred over majority voting because:
- It preserves uncertainty information from each model
- It is more robust when one model is less confident
- It is supported natively by scikit-learn's VotingClassifier

---

## 6. Alert Severity Rules

| Predicted Class | Base Severity | Upgraded to… |
|---|---|---|
| normal | info | — |
| probe | medium | high (if confidence ≥ 90%) |
| dos | high | critical (if confidence ≥ 90%) |
| r2l | high | critical (if confidence ≥ 90%) |
| u2r | critical | critical (always) |

---

## 7. Deployment Architecture

### 7.1 Local Development

```
Terminal 1: python backend/app.py          → http://127.0.0.1:5000
Terminal 2: cd frontend && npm run dev     → http://localhost:5173
```

### 7.2 Docker Compose

```
docker compose up --build

ids-backend   → 0.0.0.0:5000  (Flask, python:3.11-slim)
ids-frontend  → 0.0.0.0:8080  (nginx:1.27, static React bundle)
```

### 7.3 Kubernetes

```
kubectl apply -f k8s/

ids-backend  Deployment  → ClusterIP Service :5000
ids-frontend Deployment  → NodePort Service  :30080
HPA          → scales backend 1–4 replicas at 70% CPU
```

---

## 8. Streaming Layer (Current and Future)

**Current implementation:** synchronous HTTP request-response.
The frontend polls REST endpoints every 3–5 seconds.

**Internal event flow (Phase 8 foundation):**
Each prediction record carries:
- `event_id` — uuid4 generated at ingestion
- `ingested_at` — timestamp at flow capture
- `timestamp` — timestamp at prediction completion
- `latency_ms` — inference time in milliseconds

**Future migration path to Redis Streams:**
The current synchronous inference call in `app.py:_run_inference()` can be
replaced with:
```python
# Producer
redis_client.xadd("ids:flows", {"event_id": ..., "features": json.dumps(fv)})

# Consumer (separate worker)
events = redis_client.xread({"ids:flows": "$"}, block=1000)
for event in events:
    _run_inference(...)
```
No other application code needs to change because `event_id` propagation
is already in place.

---

## 9. Security Architecture

| Control | Implementation | Status |
|---|---|---|
| API authentication | `X-API-Key` header, env var `IDS_API_KEY` | ✅ Optional |
| CORS restriction | Configurable origins via `IDS_CORS_ORIGINS` | ✅ |
| Input validation | All 27 features validated type + enum | ✅ |
| No hardcoded secrets | All config via env vars / `.env` | ✅ |
| Capture safety | Probe generator restricted to `127.0.0.1` | ✅ |
| Rate limiting | `flask-limiter` included in requirements | 🚧 Configured in next phase |
| HTTPS | SSL termination via nginx or cloud LB | 📋 Documented |
| Audit logging | Structured JSON request log | ✅ |

---

*End of ARCHITECTURE.md*
