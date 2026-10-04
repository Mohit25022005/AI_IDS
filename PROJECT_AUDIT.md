# PROJECT AUDIT

**Project:** Cloud-RT-IDS — Enterprise Edition  
**Audit Date:** 2026-10-04  
**Version:** 3.0 (post-CIC-IDS-2017 upgrade)

> This document reflects the current state of the project after all
> enterprise upgrades. For the original pre-upgrade audit, see git history.

---

## 1. Current Architecture

```
CIC-IDS-2017 (2.83M rows, 8 CSVs)
        │
        ▼
cicids_pipeline.py
  → 27-feature CSV (209k train / 52k test, 7 classes)
        │
        ▼
train_model.py         train_anomaly.py
  → RF + SVM + NN         → IsolationForest
  + Hybrid Ensemble         (normal-only)
        │
        ▼
  model_*.pkl + metrics_*.json
        │
        ▼
Flask REST API  (app.py v3)
  → Rate limiting
  → API key auth
  → SQLite (SQLAlchemy)
  → SSE streaming
  → SHAP explainability
  → Anomaly scoring
        │
     ┌──┴──┐
     ▼     ▼
  SQLite  SSE broadcast
  ids.db  → React frontend
```

---

## 2. Technologies

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Backend framework | Flask | 3.0.3 | Production-mode via threaded=True |
| CORS | flask-cors | 4.0.1 | Origin-restricted |
| Rate limiting | flask-limiter | 3.7.0 | Per-endpoint limits |
| ORM | SQLAlchemy + flask-sqlalchemy | 2.0.36 + 3.1.1 | SQLite backing |
| ML | scikit-learn | 1.5.1 | RF, SGD, MLP, Voting, IsolationForest |
| Explainability | shap | 0.46.0 | TreeExplainer for RF |
| Data | pandas | 2.2.2 | |
| Data | numpy | 1.26.4 | |
| Serialisation | joblib | 1.4.2 | |
| Packet capture | Scapy | 2.5.0 | Windows Npcap loopback |
| Config | python-dotenv | 1.0.1 | .env loading |
| Imbalanced learn | imbalanced-learn | 0.12.3 | Available, not yet applied |
| Frontend | React 18 + TypeScript | Vite 5 | |
| Charts | Recharts | 2.15.4 | |
| HTTP client | Axios | 1.12.2 | |
| Routing | React Router DOM | 6.30.1 | |
| Styling | Tailwind CSS + shadcn/ui | 3.4.17 | |
| Database | SQLite | Built-in | `data/ids.db` |
| Container | Docker | 24+ | Multi-stage builds |
| Orchestration | Kubernetes | 1.28+ | 7 manifests + HPA |

---

## 3. Data Flow

See `ARCHITECTURE.md` Section 3 for the complete data flow diagrams.

Summary:
- **Live capture:** Scapy → NetworkFlow → 27 features → classifier + anomaly → alert → SQLite + SSE
- **REST predict:** POST body → validate → classifier + SHAP + anomaly → response + SQLite
- **Dashboard:** React polls REST endpoints + subscribes to SSE `/stream/alerts`

---

## 4. ML Pipeline

| Stage | Implementation |
|---|---|
| Data source | CIC-IDS-2017 (real network traffic, 2017) |
| Feature schema | 27 features, version 2 |
| Preprocessing | StandardScaler (26 numeric) + OHE (1 categorical) |
| Train/test split | Stratified 80/20, random_state=42 |
| Classifiers | RF (300 trees), LinearSVM (SGD), MLP (256-128-64), Hybrid (soft voting) |
| Anomaly model | IsolationForest (200 estimators, normal-only, 80k samples) |
| Explainability | SHAP TreeExplainer (RF only, top-5 features) |
| Metrics saved | accuracy, precision, recall, F1 macro/weighted, per-class, confusion matrix, latency, MD5, timestamp |
| Data leakage | None — scaler fit on X_train only; pipeline prevents leakage |

---

## 5. Dataset

| Property | Value |
|---|---|
| Source | CIC-IDS-2017 |
| Classes | 7: normal, dos, ddos, probe, r2l, web_attack, bot |
| Training rows | 209,067 |
| Test rows | 52,267 |
| Train MD5 | `c782c77456ffaf3524d77b6bb9a56c2e` |
| Test MD5 | `aea2939883be91f5f24033c0b694fbb8` |

See `DATASET_DOCUMENTATION.md` for full schema and `DATASET_CHANGELOG.md` for history.

---

## 6. API Endpoints (21 total)

All endpoints documented in `ARCHITECTURE.md` Section 4.

New endpoints added in v3:
- `GET /stream/alerts` — SSE real-time push
- `POST /feedback` — analyst label correction
- `GET /insights/latency` — latency percentiles

---

## 7. Database / Storage

| Store | Technology | Contents | Persistence |
|---|---|---|---|
| Main database | SQLite (`ids.db`) | alerts, prediction_history, settings | ✅ File on disk |
| Model artifacts | `.pkl` files | Trained sklearn Pipelines | ✅ File on disk |
| Metrics | `.json` files | Training results, class dist, MD5s | ✅ File on disk |
| Feedback | `feedback.jsonl` | Analyst corrections | ✅ Append-only |
| Experiment archive | `experiments/baseline/` | Timestamped run results | ✅ File on disk |

No JSON-based storage remains for operational data (all moved to SQLite in v3).

---

## 8. Streaming

| Item | Status |
|---|---|
| SSE endpoint | ✅ `GET /stream/alerts` |
| Alert broadcast | ✅ `_broadcast_alert()` → all subscribed queues |
| Initial replay | ✅ Last 50 alerts sent on connect |
| Heartbeat | ✅ 15-second keep-alive comments |
| Auto-reconnect | ✅ Frontend reconnects after 5s on error |
| Redis migration path | 📋 Documented in ARCHITECTURE.md Section 9 |

---

## 9. Deployment

| Item | Status |
|---|---|
| `docker/Dockerfile.backend` | ✅ python:3.11-slim + libpcap |
| `docker/Dockerfile.frontend` | ✅ node:20-alpine + nginx:1.27 |
| `docker-compose.yml` | ✅ backend + frontend + healthchecks |
| `k8s/deployment-backend.yaml` | ✅ With liveness + readiness probes |
| `k8s/deployment-frontend.yaml` | ✅ |
| `k8s/service-backend.yaml` | ✅ ClusterIP :5000 |
| `k8s/service-frontend.yaml` | ✅ NodePort :30080 |
| `k8s/hpa-backend.yaml` | ✅ 1–4 replicas, CPU 70% |
| `k8s/configmap.yaml` | ✅ |
| `k8s/secret.template.yaml` | ✅ |
| `.env.example` | ✅ All variables documented |
| `frontend/.env.example` | ✅ |

---

## 10. Monitoring / Observability

| Item | Status |
|---|---|
| Structured JSON logging | ✅ All requests, predictions, errors |
| Prometheus metrics | ✅ `GET /metrics` |
| Health endpoint | ✅ `GET /health` (model, uptime, anomaly, SQLite) |
| Per-prediction latency | ✅ Stored in history, exposed via `/insights/latency` |
| Alert count metrics | ✅ In `/metrics` and `/health` |
| Request count | ✅ In `/metrics` |
| Grafana | ❌ Not configured (Prometheus endpoint is compatible) |

---

## 11. Security

| Control | Status |
|---|---|
| API key auth | ✅ Optional `X-API-Key`, env-configured |
| Rate limiting | ✅ Per-endpoint (flask-limiter) |
| CORS restriction | ✅ Configurable `IDS_CORS_ORIGINS` |
| Input validation | ✅ All 27 features type + enum checked |
| No hardcoded secrets | ✅ All config via `.env` |
| SQL injection protection | ✅ SQLAlchemy ORM (no raw SQL) |
| Structured audit log | ✅ |
| HTTPS | 📋 Nginx SSL config documented |
| Capture safety | ✅ Probe generator → 127.0.0.1 only |

---

## 12. Tests

| Test file | Coverage |
|---|---|
| `tests/conftest.py` | Shared fixtures (feature dicts) |
| `tests/test_preprocessing.py` | Schema validation, feature ordering |
| `tests/test_model.py` | Model loading, predict, proba, edge cases |
| `tests/test_api.py` | All REST endpoints, happy + sad paths |
| `tests/test_simulator.py` | All 7 classes, count clamping, reproducibility |
| `tests/test_smoke.py` | End-to-end: predict → history → alert → patch |

Tests skip model-dependent cases gracefully when artifacts not present.

---

## 13. Outstanding Gaps (from original audit — current status)

| Original Gap | Current Status |
|---|---|
| No SVM | ✅ LinearSVM (SGD) implemented |
| No Neural Network | ✅ MLP 256-128-64 implemented |
| No ensemble | ✅ Soft-voting Hybrid implemented |
| Hardcoded metrics | ✅ Fixed — all dynamic from JSON |
| Mock chart data | ✅ Fixed — all charts use real API data |
| JSON-only storage | ✅ Fixed — SQLite + SQLAlchemy |
| No streaming | ✅ Fixed — SSE `/stream/alerts` |
| No rate limiting | ✅ Fixed — flask-limiter |
| No SHAP | ✅ Fixed — TreeExplainer top-5 |
| No anomaly detection | ✅ Fixed — IsolationForest |
| Synthetic dataset | ✅ Fixed — CIC-IDS-2017 (2.83M real flows) |
| Binary classification | ✅ Fixed — 7 classes |
| No Docker | ✅ Fixed |
| No Kubernetes | ✅ Fixed |
| No tests | ✅ Fixed — 5 test files, 50+ test cases |
| Scapy missing from requirements | ✅ Fixed |
| Alert ID collisions | ✅ Fixed — uuid4 |
| Settings not persisted | ✅ Fixed — SQLite |
| Wrong confusion matrix labels | ✅ Fixed |

---

## 14. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `bot` class: 60% precision (RF) | Medium | Add more bot training data |
| `web_attack` class: 75% precision (RF) | Medium | Add more web attack data |
| Autoscaling not benchmarked | Low | K8s HPA manifests exist |
| CIC-IDS-2017 is from 2017 | Medium | Upgrade to newer dataset |
| Live capture Windows-only (Npcap) | Medium | Cross-platform support via libpcap |

---

*End of PROJECT_AUDIT.md*
