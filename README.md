# Cloud-RT-IDS

**Cloud-Based Real-Time Intrusion Detection System Using Artificial Intelligence**

A full-stack, research-oriented IDS prototype that captures live network flows,
classifies traffic with four ML models (Random Forest, SVM, Neural Network,
Hybrid Ensemble), generates alerts, and displays real-time results on a React
security dashboard.

> **Research note:** The project uses a custom 27-feature live-flow schema —
> not the original NSL-KDD 41-feature schema. This is a deliberate research
> contribution. See [DATASET_DOCUMENTATION.md](DATASET_DOCUMENTATION.md).

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Windows: [Npcap](https://npcap.com/) installed (required for live capture)
- *(Optional)* Docker Desktop for containerised deployment

### 1. Clone and set up the backend

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install all dependencies (pinned versions)
pip install -r backend/requirements.txt
```

### 2. Train the models

Run this once before starting the backend. It produces four model artifacts
and saves full metrics to JSON files.

```powershell
python backend/model/train_model.py
```

This creates:
```
backend/model/
  model_random_forest.pkl
  model_svm.pkl
  model_neural_network.pkl
  model_hybrid.pkl
  model.pkl               ← legacy fallback (RF copy)
  metrics_random_forest.json
  metrics_svm.json
  metrics_neural_network.json
  metrics_hybrid.json
  metrics_all.json        ← comparison table + current metrics

experiments/baseline/<timestamp>/
  metrics_all.json
  run_info.json
```

### 3. Start the backend

```powershell
python backend/app.py
```

Backend runs at `http://127.0.0.1:5000`

Verify:
```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

### 4. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` (or the port Vite prints).

---

## Project Structure

```
AI_IDS/
│
├── backend/
│   ├── app.py                    ← Flask REST API (18 endpoints)
│   ├── url_kdd.py                ← Scapy capture + feature extraction
│   ├── simulator.py              ← Synthetic traffic generator
│   ├── clean_dataset.py          ← Dataset cleaning utility
│   ├── inspect_dataset.py        ← Dataset inspection utility
│   ├── evaluate_model.py         ← Standalone evaluation script
│   ├── requirements.txt          ← Pinned Python dependencies
│   │
│   ├── model/
│   │   ├── train_model.py        ← Multi-model training script
│   │   ├── model_*.pkl           ← Trained sklearn Pipelines
│   │   └── metrics_*.json        ← Saved metrics + metadata
│   │
│   ├── data/
│   │   ├── live_flows.csv        ← Training dataset (27 features)
│   │   ├── test_flows.csv        ← Independent test set
│   │   ├── alerts.json           ← Persisted alerts
│   │   ├── prediction_history.json
│   │   ├── settings.json         ← Persisted IDS settings
│   │   ├── KDDTrain+.txt         ← NSL-KDD (reference only)
│   │   └── KDDTest+.txt          ← NSL-KDD (reference only)
│   │
│   └── utils/
│       └── preprocessing.py      ← Shared schema constants + validators
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx     ← 6 KPIs + real-time charts
│       │   ├── Monitor.tsx       ← Manual predict + live capture
│       │   ├── Insights.tsx      ← Metrics + confusion matrix + comparison
│       │   ├── Alerts.tsx        ← Alert lifecycle management
│       │   └── Settings.tsx      ← Model selection + threshold
│       ├── components/
│       │   ├── TrafficChart.tsx  ← Real-data time-series chart
│       │   └── ThreatDistribution.tsx ← Real-data pie chart
│       └── lib/api.ts            ← Typed Axios client
│
├── docker/
│   ├── Dockerfile.backend        ← python:3.11-slim + libpcap
│   ├── Dockerfile.frontend       ← node:20-alpine + nginx:1.27-alpine
│   └── nginx.conf                ← SPA routing + API proxy
│
├── k8s/
│   ├── configmap.yaml
│   ├── secret.template.yaml
│   ├── deployment-backend.yaml
│   ├── deployment-frontend.yaml
│   ├── service-backend.yaml      ← ClusterIP :5000
│   ├── service-frontend.yaml     ← NodePort :30080
│   └── hpa-backend.yaml          ← 1–4 replicas, CPU 70%
│
├── tests/
│   ├── conftest.py               ← Shared fixtures
│   ├── test_preprocessing.py     ← Schema validation tests
│   ├── test_model.py             ← Model loading + inference tests
│   ├── test_api.py               ← REST endpoint tests
│   ├── test_simulator.py         ← Synthetic traffic tests
│   └── test_smoke.py             ← End-to-end pipeline test
│
├── experiments/
│   ├── baseline/                 ← Timestamped baseline runs
│   ├── random_forest/
│   ├── svm/
│   ├── neural_network/
│   ├── hybrid/
│   └── imbalance_experiments/
│
├── docker-compose.yml
├── pytest.ini
├── .env.example                  ← Backend env template
├── frontend/.env.example         ← Frontend env template
│
├── README.md                     ← This file
├── PROJECT_AUDIT.md              ← Full repository audit
├── JOURNAL_TRACEABILITY.md       ← 142 journal requirements mapped
├── ARCHITECTURE.md               ← System design + data flow
├── DATASET_DOCUMENTATION.md      ← Feature schema + methodology
├── DATASET_CHANGELOG.md          ← NSL-KDD → live-flow evolution
├── EXPERIMENTS.md                ← Experiment templates + results
└── FINAL_RESULTS.md              ← Research summary (fill after training)
```

---

## Backend API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Version check |
| `/health` | GET | Model status, uptime, latency |
| `/metrics` | GET | Prometheus-compatible metrics |
| `/predict` | POST | Single-flow inference (27 features) |
| `/capture` | POST | Live Scapy capture + inference |
| `/simulate` | POST | Synthetic flow generation + inference |
| `/monitor/history` | GET | Paginated prediction history |
| `/alerts` | GET | Paginated + filtered alerts |
| `/alerts/<id>` | PATCH | Update alert status |
| `/settings` | GET/POST | Read / update IDS settings |
| `/model/info` | GET | Active model metadata + metrics |
| `/model/comparison` | GET | All-model comparison table |
| `/model/reload` | POST | Reload .pkl artifacts from disk |
| `/model/reset` | POST | Reset to defaults |
| `/insights/metrics` | GET | Test-set metrics (active model) |
| `/insights/metrics/perclass` | GET | Per-class precision/recall/F1 |
| `/insights/confusion` | GET | Confusion matrix (dynamic) |
| `/insights/traffic` | GET | Live prediction class counts |
| `/insights/latency` | GET | Latency samples + p50/p95/p99 |

---

## Configuration

Copy `.env.example` to `.env` in the project root and set variables:

```ini
IDS_HOST=0.0.0.0
IDS_PORT=5000
IDS_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
IDS_API_KEY=          # leave empty to disable auth
IDS_MAX_HISTORY=10000
IDS_LOG_LEVEL=INFO
```

Copy `frontend/.env.example` to `frontend/.env.local`:

```ini
VITE_API_URL=http://127.0.0.1:5000
VITE_API_KEY=         # leave empty if backend auth is disabled
```

---

## Running with Docker

```powershell
# Build and start both services
docker compose up --build

# Backend:  http://localhost:5000
# Frontend: http://localhost:8080

# Stop
docker compose down
```

**Note:** Live Scapy capture requires `--network host` and Npcap on the
host. The Docker image supports all non-capture endpoints without
additional permissions.

---

## Running with Kubernetes (minikube)

```powershell
# Start minikube
minikube start

# Build images into minikube's Docker daemon
minikube docker-env | Invoke-Expression
docker build -f docker/Dockerfile.backend  -t ids-backend:latest  .
docker build -f docker/Dockerfile.frontend -t ids-frontend:latest .

# Create secret (fill in base64 values first)
# cp k8s/secret.template.yaml k8s/secret.yaml
# kubectl apply -f k8s/secret.yaml

# Apply all manifests
kubectl apply -f k8s/

# Access frontend
minikube service ids-frontend

# Scale inference manually
kubectl scale deployment ids-backend --replicas=3

# Watch HPA
kubectl get hpa ids-backend-hpa --watch
```

---

## Running Tests

```powershell
# Run all tests (skips model tests if train_model.py not run yet)
pytest

# Run specific suite
pytest tests/test_preprocessing.py -v
pytest tests/test_simulator.py -v
pytest tests/test_smoke.py -v

# Run after training (all tests including model tests)
python backend/model/train_model.py
pytest
```

---

## Dataset Setup and Collection

### Inspect the existing dataset

```powershell
cd backend
python inspect_dataset.py
```

### Collect new training data

```powershell
# Collect normal traffic (5 seconds of loopback traffic)
python -c "
from url_kdd import capture_flows, save_flows_to_csv
flows = capture_flows(capture_time=10)
save_flows_to_csv(flows, 'data/live_flows.csv', label='normal')
"

# Collect probe traffic
python -c "
from url_kdd import capture_flows, generate_local_probe_traffic, save_flows_to_csv
import threading, time
flows = []
def capture():
    flows.extend(capture_flows(capture_time=10))
t = threading.Thread(target=capture)
t.start()
time.sleep(1)
generate_local_probe_traffic()
t.join()
save_flows_to_csv(flows, 'data/live_flows.csv', label='probe')
"

# Clean dataset (verify probe ports, separate unlabeled)
python clean_dataset.py
```

### Collect independent test data

Repeat the capture steps above but save to `data/test_flows.csv`.
**Keep training and test data from separate capture sessions.**

---

## Live Detection Demo

```
1.  python backend/app.py          ← start backend
2.  cd frontend && npm run dev     ← start frontend
3.  Open http://localhost:5173
4.  Navigate to Network Monitor
5.  Click "Capture & Detect"       ← captures 5s of loopback traffic
6.  View predictions in the table
7.  Switch capture mode to "Controlled Probe Test"
8.  Click "Capture Probe"          ← generates port-scan + captures
9.  Watch alert appear in Alerts page
10. Open Insights to see:
      - Active model performance metrics
      - Per-class precision/recall/F1
      - Confusion matrix
      - Model comparison table (after training all 4 models)
      - Detection latency trend chart
```

---

## Switching ML Models

Via the Settings page in the frontend, or via API:

```powershell
# Switch to SVM
Invoke-RestMethod -Uri "http://127.0.0.1:5000/settings" `
  -Method POST -ContentType "application/json" `
  -Body '{"ml_model": "svm"}'

# Switch to Hybrid Ensemble
Invoke-RestMethod -Uri "http://127.0.0.1:5000/settings" `
  -Method POST -ContentType "application/json" `
  -Body '{"ml_model": "hybrid"}'

# Check active model info
Invoke-RestMethod http://127.0.0.1:5000/model/info

# See full model comparison
Invoke-RestMethod http://127.0.0.1:5000/model/comparison
```

---

## Simulate Traffic (No Capture Required)

```powershell
# Generate 10 synthetic DoS flows and classify them
Invoke-RestMethod -Uri "http://127.0.0.1:5000/simulate" `
  -Method POST -ContentType "application/json" `
  -Body '{"class": "dos", "count": 10}'
```

Supported classes: `normal`, `probe`, `dos`, `r2l`, `u2r`

---

## Research Documentation

| Document | Contents |
|---|---|
| [PROJECT_AUDIT.md](PROJECT_AUDIT.md) | Full repo audit: architecture, risks, missing items |
| [JOURNAL_TRACEABILITY.md](JOURNAL_TRACEABILITY.md) | 142 journal requirements mapped to implementation |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, API reference, deployment |
| [DATASET_DOCUMENTATION.md](DATASET_DOCUMENTATION.md) | 27-feature schema, preprocessing, methodology |
| [DATASET_CHANGELOG.md](DATASET_CHANGELOG.md) | NSL-KDD → live-flow evolution, 6 documented changes |
| [EXPERIMENTS.md](EXPERIMENTS.md) | Experiment templates (populate after training) |
| [FINAL_RESULTS.md](FINAL_RESULTS.md) | Summary template (populate after training) |

---

## Known Limitations

- Training set is small (~115 samples) — metrics are not statistically stable
- Probe traffic is highly uniform — accuracy is likely inflated
- All data captured on Windows loopback — not equivalent to real network monitoring
- Binary classification only (normal/probe) — live multi-class detection requires more data
- Docker live capture requires special network configuration
- Autoscaling benchmarks not yet measured on local hardware

See [FINAL_RESULTS.md](FINAL_RESULTS.md) for the complete limitations table.

---

## Important: What NOT to Do

- Do not replace `live_flows.csv` or `test_flows.csv` with original NSL-KDD data
- Do not manually edit `metrics_*.json` — always regenerate via `train_model.py`
- Do not set `IDS_DEBUG=true` in production
- Do not commit `.env` or `k8s/secret.yaml` to version control
