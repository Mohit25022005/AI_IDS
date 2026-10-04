# Cloud-RT-IDS

**Cloud-Based Real-Time Intrusion Detection System Using Artificial Intelligence**  
**Version:** 3.0 — Enterprise Edition  
**Dataset:** CIC-IDS-2017 (2.83M real network flows, 7 attack classes)

A full-stack, enterprise-grade IDS trained on real network traffic. Classifies flows
across 7 attack categories using four ML models, detects zero-days via IsolationForest,
explains every prediction with SHAP, streams alerts in real-time via SSE, and persists
all data in SQLite.

---

## System at a Glance

```
Real Network Traffic / CIC-IDS-2017
            │
            ▼
  Scapy Packet Capture  OR  REST /predict
            │
            ▼
   27-Feature Flow Vector
            │
     ┌──────┴──────┐
     ▼             ▼
 Classifier    IsolationForest
 (RF/SVM/NN/   (anomaly layer —
  Hybrid)       zero-day detection)
     │             │
     └──────┬───────┘
            ▼
      Alert Engine
   (severity + SHAP top-5)
            │
      SQLite Database
            │
     SSE Stream → React Dashboard
```

---

## Quickstart

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| Npcap (Windows) | Latest — [npcap.com](https://npcap.com/) |
| Docker (optional) | 24+ |

### 1 — Install backend

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2 — Build the dataset from CIC-IDS-2017

Place the 8 CIC-IDS-2017 CSVs in `MachineLearningCSV/MachineLearningCVE/`, then:

```powershell
cd backend
python cicids_pipeline.py
```

This reads 2.83M real flows, maps 79 CIC columns to our 27-feature schema,
balances classes, and writes:

```
backend/data/live_flows.csv   — 209,067 training rows
backend/data/test_flows.csv   —  52,267 test rows (held-out)
```

### 3 — Train all models

```powershell
python model/train_model.py   # RF + LinearSVM + NN + Hybrid (~30 min)
python train_anomaly.py       # IsolationForest on normal-only traffic
```

Artifacts saved to `backend/model/`.

### 4 — Start the backend

```powershell
python app.py
```

Runs at `http://127.0.0.1:5000`. Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

### 5 — Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`.

---

## Project Structure

```
AI_IDS/
│
├── backend/
│   ├── app.py                     Flask API v3 (SQLite, SSE, SHAP, rate limiting)
│   ├── cicids_pipeline.py         CIC-IDS-2017 → 27-feature data pipeline
│   ├── train_anomaly.py           IsolationForest training script
│   ├── augment_dataset.py         Synthetic data augmentation utility
│   ├── simulator.py               Synthetic traffic generator (7 classes)
│   ├── url_kdd.py                 Scapy packet capture + feature extraction
│   ├── clean_dataset.py           Dataset cleaning utility
│   ├── inspect_dataset.py         Dataset inspection utility
│   ├── evaluate_model.py          Standalone evaluation script
│   ├── requirements.txt           Pinned Python dependencies
│   │
│   ├── model/
│   │   ├── train_model.py         Multi-model training (RF + LinearSVM + NN + Hybrid)
│   │   ├── model_random_forest.pkl
│   │   ├── model_svm.pkl          (SGD / Linear SVM, CalibratedClassifierCV)
│   │   ├── model_neural_network.pkl
│   │   ├── model_hybrid.pkl       (Soft voting: RF + SVM + NN)
│   │   ├── model_anomaly.pkl      IsolationForest (normal-only training)
│   │   ├── model.pkl              Legacy RF alias (backward compat)
│   │   ├── metrics_random_forest.json
│   │   ├── metrics_svm.json
│   │   ├── metrics_neural_network.json
│   │   ├── metrics_hybrid.json
│   │   ├── metrics_anomaly.json
│   │   └── metrics_all.json       Comparison table + active model metrics
│   │
│   ├── data/
│   │   ├── live_flows.csv         Training set (CIC-IDS-2017, 209,067 rows)
│   │   ├── test_flows.csv         Held-out test set (52,267 rows)
│   │   ├── ids.db                 SQLite — alerts, history, settings
│   │   └── feedback.jsonl         Analyst label corrections (for future retrain)
│   │
│   └── utils/
│       └── preprocessing.py       Shared schema constants + validators
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx      6 KPIs + real-time traffic/threat charts
│       │   ├── Monitor.tsx        Manual predict + live capture
│       │   ├── Insights.tsx       Metrics, confusion matrix, model comparison, latency
│       │   ├── Alerts.tsx         SSE-powered alert stream + SHAP + anomaly bar
│       │   └── Settings.tsx       Model selection + threshold
│       ├── components/
│       │   ├── TrafficChart.tsx   Real-data rolling time-series
│       │   └── ThreatDistribution.tsx  Real-data class distribution pie
│       └── lib/api.ts             Typed Axios client
│
├── MachineLearningCSV/
│   └── MachineLearningCVE/        CIC-IDS-2017 raw CSVs (8 files, 2.83M rows)
│
├── docker/
│   ├── Dockerfile.backend         python:3.11-slim + libpcap
│   ├── Dockerfile.frontend        node:20-alpine build + nginx:1.27-alpine serve
│   └── nginx.conf
│
├── k8s/
│   ├── configmap.yaml
│   ├── secret.template.yaml
│   ├── deployment-backend.yaml
│   ├── deployment-frontend.yaml
│   ├── service-backend.yaml       ClusterIP :5000
│   ├── service-frontend.yaml      NodePort :30080
│   └── hpa-backend.yaml           HPA 1–4 replicas, CPU 70%
│
├── tests/
│   ├── conftest.py
│   ├── test_preprocessing.py
│   ├── test_model.py
│   ├── test_api.py
│   ├── test_simulator.py
│   └── test_smoke.py
│
├── experiments/
│   └── baseline/<timestamp>/      Timestamped experiment archives
│
├── docker-compose.yml
├── pytest.ini
├── .env.example                   Backend environment template
├── frontend/.env.example          Frontend environment template
│
└── docs/
    ├── README.md                  This file
    ├── ARCHITECTURE.md
    ├── DATASET_DOCUMENTATION.md
    ├── DATASET_CHANGELOG.md
    ├── EXPERIMENTS.md
    ├── FINAL_RESULTS.md
    ├── PROJECT_AUDIT.md
    └── JOURNAL_TRACEABILITY.md
```

---

## API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/` | GET | — | Version + health message |
| `/health` | GET | — | Model status, uptime, anomaly model, latency |
| `/metrics` | GET | — | Prometheus-compatible metrics |
| `/predict` | POST | ✓ | Single-flow inference + SHAP + anomaly score |
| `/capture` | POST | ✓ | Live Scapy capture + inference |
| `/simulate` | POST | ✓ | Synthetic flow generation + inference |
| `/stream/alerts` | GET | — | SSE — real-time alert push (no polling needed) |
| `/monitor/history` | GET | ✓ | Paginated + filtered prediction history |
| `/alerts` | GET | ✓ | Paginated + filtered alerts |
| `/alerts/<id>` | PATCH | ✓ | Update alert status |
| `/feedback` | POST | ✓ | Submit analyst-corrected label for an alert |
| `/settings` | GET/POST | ✓ | Read / update IDS settings (SQLite-persisted) |
| `/model/info` | GET | — | Active model metadata + metrics |
| `/model/comparison` | GET | — | All-model comparison table |
| `/model/reload` | POST | ✓ | Reload all .pkl artifacts from disk |
| `/model/reset` | POST | ✓ | Reset settings + reload models |
| `/insights/metrics` | GET | — | Test-set metrics for active model |
| `/insights/metrics/perclass` | GET | — | Per-class precision / recall / F1 |
| `/insights/confusion` | GET | — | Confusion matrix (dynamic, from saved JSON) |
| `/insights/traffic` | GET | — | Live prediction class counts |
| `/insights/latency` | GET | — | Latency samples + p50 / p95 / p99 |

Auth ✓ = `X-API-Key` header required when `IDS_API_KEY` env variable is set.

---

## Environment Configuration

Copy `.env.example` to `.env`:

```ini
IDS_HOST=0.0.0.0
IDS_PORT=5000
IDS_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
IDS_API_KEY=                    # leave empty to disable auth
IDS_MAX_HISTORY=10000
IDS_LOG_LEVEL=INFO
IDS_DB_URL=sqlite:///data/ids.db
```

Copy `frontend/.env.example` to `frontend/.env.local`:

```ini
VITE_API_URL=http://127.0.0.1:5000
VITE_API_KEY=                   # match IDS_API_KEY above
```

---

## Attack Classes

| Label | CIC-IDS-2017 Source | Severity | Train Rows | Test Rows |
|---|---|---|---|---|
| `normal` | BENIGN | info | 80,000 | 20,000 |
| `dos` | DoS Hulk, GoldenEye, slowloris, Slowhttptest, Heartbleed | high | 40,000 | 10,000 |
| `ddos` | DDoS | critical | 40,000 | 10,000 |
| `probe` | PortScan | medium | 40,000 | 10,000 |
| `r2l` | FTP-Patator, SSH-Patator, Infiltration | high | 5,920 | 1,480 |
| `web_attack` | Web Attack (Brute Force, XSS, SQLi) | high | 1,620 | 405 |
| `bot` | Bot | critical | 1,527 | 382 |

---

## Model Results (CIC-IDS-2017, Independent Test Set)

| Model | Accuracy | Precision | Recall | F1 Macro | Training Time | Latency |
|---|---|---|---|---|---|---|
| **Hybrid** (RF+SVM+NN) | **99.29%** | **95.00%** | **95.75%** | **95.05%** | 704.6 s | 0.039 ms |
| Neural Network (256-128-64) | 99.13% | 94.53% | 94.95% | 94.36% | 668.9 s | 0.027 ms |
| Random Forest (300 trees) | 99.14% | 90.72% | 99.30% | 94.12% | 8.2 s | 0.012 ms |
| Linear SVM (SGD) | 93.03% | 75.97% | 79.41% | 77.47% | 4.6 s | 0.003 ms |

All values are from `backend/model/metrics_all.json` — never hardcoded.

---

## Switching Models

```powershell
# Via API
Invoke-RestMethod -Uri "http://127.0.0.1:5000/settings" `
  -Method POST -ContentType "application/json" `
  -Body '{"ml_model": "hybrid"}'

# Available values: "random-forest", "svm", "neural-network", "hybrid"

# Check current model + metrics
Invoke-RestMethod http://127.0.0.1:5000/model/info
```

Or use the **Settings** page in the frontend — all four models are available.

---

## Running with Docker

```powershell
docker compose up --build

# Backend:  http://localhost:5000
# Frontend: http://localhost:8080
```

> Live Scapy capture inside Docker requires `--network host` and Npcap on
> the host. All non-capture endpoints work without special permissions.

---

## Running with Kubernetes

```powershell
minikube start

# Build images into minikube
minikube docker-env | Invoke-Expression
docker build -f docker/Dockerfile.backend  -t ids-backend:latest  .
docker build -f docker/Dockerfile.frontend -t ids-frontend:latest .

# Apply all manifests
kubectl apply -f k8s/

# Access the dashboard
minikube service ids-frontend

# Scale the inference service manually
kubectl scale deployment ids-backend --replicas=3

# Watch autoscaler
kubectl get hpa ids-backend-hpa --watch
```

---

## Simulating Traffic

The simulator generates statistically-representative synthetic flows for all
7 classes. Useful for testing the pipeline without live capture.

```powershell
# Generate 20 DDoS flows and run them through the active model
Invoke-RestMethod -Uri "http://127.0.0.1:5000/simulate" `
  -Method POST -ContentType "application/json" `
  -Body '{"class": "ddos", "count": 20}'

# Available: normal, dos, ddos, probe, r2l, bot, web_attack
```

---

## Running Tests

```powershell
# All tests (model tests skipped if models not trained)
pytest

# Specific suites
pytest tests/test_preprocessing.py -v
pytest tests/test_simulator.py -v
pytest tests/test_api.py -v
pytest tests/test_smoke.py -v  # requires running backend
```

---

## Rebuilding the Dataset

Run the pipeline again at any time with different sampling settings:

```powershell
# Default: 100k normal, 50k per attack class
python backend/cicids_pipeline.py

# Custom sampling
python backend/cicids_pipeline.py --normal-samples 200000 --samples-per-class 100000

# Preview without writing
python backend/cicids_pipeline.py --dry-run

# Then retrain
python backend/model/train_model.py
python backend/train_anomaly.py
```

---

## Analyst Feedback Loop

When an analyst marks an alert as a false positive, the system records the
correction for future retraining:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/feedback" `
  -Method POST -ContentType "application/json" `
  -Body '{"alert_id": "<id>", "true_label": "normal"}'
```

Corrections are appended to `backend/data/feedback.jsonl`. Include this file
when rerunning `train_model.py` to improve accuracy over time.

---

## Research Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system design, data flow, API reference, deployment |
| [DATASET_DOCUMENTATION.md](DATASET_DOCUMENTATION.md) | 27-feature schema, CIC-IDS-2017 mapping, preprocessing |
| [DATASET_CHANGELOG.md](DATASET_CHANGELOG.md) | Evolution from NSL-KDD → live-flow → CIC-IDS-2017 |
| [EXPERIMENTS.md](EXPERIMENTS.md) | Experiment results with real measured values |
| [FINAL_RESULTS.md](FINAL_RESULTS.md) | Complete results summary with all metrics |
| [PROJECT_AUDIT.md](PROJECT_AUDIT.md) | Initial repository audit (pre-upgrade baseline) |
| [JOURNAL_TRACEABILITY.md](JOURNAL_TRACEABILITY.md) | Journal requirement → implementation traceability |

---

## Security Notes

- Never commit `.env`, `k8s/secret.yaml`, or `ids.db` to version control
- Set `IDS_API_KEY` in production to protect all write endpoints
- `IDS_DEBUG=true` must never be used in production (exposes Werkzeug debugger)
- Live capture (`/capture`) is rate-limited to 10 requests/minute
- Probe generator is restricted to `127.0.0.1` only

---

## Known Limitations

| Limitation | Impact |
|---|---|
| `bot` (60% precision) and `web_attack` (75% precision) | Low precision due to small training set for these classes (1.5k–1.6k rows vs. 40k for majority classes) |
| `source_port` set to 0 for CIC data | Not present in CIC-IDS-2017; model relies on other features |
| Live capture on Windows loopback only | Not equivalent to monitoring a real network adapter |
| Autoscaling not benchmarked | K8s HPA manifests exist but scaling performance is undocumented |
| IsolationForest 47.4% anomaly detection rate | Expected on real diverse traffic — anomaly layer supplements classifier, not replaces it |
