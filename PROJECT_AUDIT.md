# PROJECT AUDIT

**Project:** AI-Powered Intrusion Detection System (AI IDS)
**Audit Date:** 2026-09-23
**Auditor:** Kiro Senior Engineering Review
**Audit Basis:** Full repository inspection — all source files, data, artifacts, and configs read directly.

---

## Table of Contents

1. [Existing Architecture](#1-existing-architecture)
2. [Existing Technologies](#2-existing-technologies)
3. [Existing Data Flow](#3-existing-data-flow)
4. [Existing ML Pipeline](#4-existing-ml-pipeline)
5. [Existing Dataset Modifications](#5-existing-dataset-modifications)
6. [Existing API Endpoints](#6-existing-api-endpoints)
7. [Existing Database / Storage](#7-existing-database--storage)
8. [Existing Streaming Implementation](#8-existing-streaming-implementation)
9. [Existing Deployment Support](#9-existing-deployment-support)
10. [Existing Monitoring](#10-existing-monitoring)
11. [Existing Security](#11-existing-security)
12. [Existing Tests](#12-existing-tests)
13. [Missing Journal Requirements](#13-missing-journal-requirements)
14. [Technical Risks](#14-technical-risks)
15. [Recommended Implementation Order](#15-recommended-implementation-order)

---

## 1. Existing Architecture

The project is a full-stack IDS prototype with three primary layers:

```
Windows Loopback Interface (Npcap)
              │
              ▼
  Scapy Packet Capture (url_kdd.py)
              │
              ▼
  Bidirectional Flow Builder (NetworkFlow dataclass)
              │
              ▼
  27 Flow-Level Feature Extraction (build_feature_vector)
              │
              ▼
  Random Forest sklearn Pipeline (model.pkl)
              │
         ┌────┴────┐
         ▼         ▼
       Normal    Probe
                   │
                   ▼
           Alert Engine (in-memory → alerts.json)
                   │
                   ▼
         React Dashboard (localhost:8081)
```

**All components run as a single monolith on one machine.**
There is no service separation, no message queue, no database, and no container layer.

---

## 2. Existing Technologies

| Layer | Technology | Version / Notes |
|---|---|---|
| Backend framework | Flask | Unversioned in requirements.txt |
| CORS | flask-cors | Unversioned |
| ML | scikit-learn | Unversioned |
| Data | pandas, numpy | Unversioned |
| Model serialization | joblib | Unversioned |
| Packet capture | Scapy | **Missing from requirements.txt** |
| Frontend framework | React 18 + TypeScript | Vite 5 |
| UI components | shadcn/ui + Radix UI | Multiple packages |
| Charts | Recharts 2 | |
| HTTP client | Axios | |
| State/fetch | TanStack React Query 5 | |
| Routing | React Router DOM 6 | |
| Build tool | Vite 5 | |
| Styling | Tailwind CSS 3 | |
| Package manager | npm (also bun.lockb present) | |
| OS | Windows (Npcap loopback specific) | |

**Notably absent:** PostgreSQL, SQLite, Redis, Kafka, Docker, Kubernetes, Prometheus, Grafana, JWT/auth.

---

## 3. Existing Data Flow

### Live Detection Path

```
POST /capture
     │
     ├── capture_time (default 8s), mode ("normal"│"probe")
     │
     ▼
capture_flows() — Scapy sniff on \Device\NPF_Loopback
     │
     ▼
NetworkFlow objects assembled from packets
     │
     ▼
build_feature_vector(flow) → 27-feature dict
     │
     ▼
pd.DataFrame([feature_vector], columns=LIVE_FEATURE_COLUMNS)
     │
     ▼
pipeline.predict() → prediction string ("normal"│"probe")
pipeline.predict_proba() → confidence float
     │
     ├──→ prediction_history list → save to prediction_history.json
     │
     └──→ if prediction != "normal" AND confidence >= threshold:
              create alert → save to alerts.json
```

### Manual Prediction Path

```
POST /predict  { "features": { ...27 features... } }
     │
     ▼
Input validation (type checking, protocol enum)
     │
     ▼
pd.DataFrame → pipeline.predict() + predict_proba()
     │
     ├──→ prediction_history
     └──→ alert if non-normal
```

### Dashboard Path

```
React Dashboard
     │
     ├── GET /monitor/history  (every 3s from Dashboard, every 5s from Monitor)
     ├── GET /alerts           (every 3s / 5s)
     ├── GET /insights/metrics (every 5s from Insights)
     ├── GET /insights/confusion (every 5s)
     └── GET /insights/traffic  (every 5s)
```

---

## 4. Existing ML Pipeline

### Feature Schema

The current model uses **27 flow-level features** derived from live packet capture. This is a **custom feature schema**, completely separate from the NSL-KDD 41-feature schema.

| # | Feature | Type | Description |
|---|---|---|---|
| 1 | duration | float | Flow duration in seconds |
| 2 | source_port | int | Source port number |
| 3 | destination_port | int | Destination port number |
| 4 | forward_packets | int | Packets in forward direction |
| 5 | backward_packets | int | Packets in backward direction |
| 6 | forward_bytes | int | Bytes in forward direction |
| 7 | backward_bytes | int | Bytes in backward direction |
| 8 | total_packets | int | Total packets in flow |
| 9 | total_bytes | int | Total bytes in flow |
| 10 | packets_per_second | float | Rate of packets |
| 11 | bytes_per_second | float | Rate of bytes |
| 12 | mean_packet_size | float | Mean packet size |
| 13 | min_packet_size | float | Minimum packet size |
| 14 | max_packet_size | float | Maximum packet size |
| 15 | packet_size_std | float | Std dev of packet sizes |
| 16 | syn_count | int | SYN flag count |
| 17 | ack_count | int | ACK flag count |
| 18 | fin_count | int | FIN flag count |
| 19 | rst_count | int | RST flag count |
| 20 | psh_count | int | PSH flag count |
| 21 | forward_packet_ratio | float | forward_packets / total_packets |
| 22 | backward_packet_ratio | float | backward_packets / total_packets |
| 23 | forward_byte_ratio | float | forward_bytes / total_bytes |
| 24 | backward_byte_ratio | float | backward_bytes / total_bytes |
| 25 | syn_ratio | float | syn_count / total_packets |
| 26 | rst_ratio | float | rst_count / total_packets |
| 27 | protocol | str | "tcp" │ "udp" │ "other" |

### Preprocessing

```
ColumnTransformer:
  - numeric features (26 features): StandardScaler
  - categorical feature (protocol): OneHotEncoder(handle_unknown="ignore")
```

Preprocessing is embedded inside the scikit-learn Pipeline (`model.pkl`). A separate `preprocessor.pkl` is also saved for backward compatibility but is not used independently.

`scaler.pkl` exists in the model directory and appears to be a legacy artifact from a previous pipeline iteration. It is NOT referenced by the current code.

### Model

```
RandomForestClassifier(
    n_estimators=300,
    random_state=42,
    class_weight="balanced",
    n_jobs=-1
)
```

### Training Procedure

1. Load `live_flows.csv` (training) and `test_flows.csv` (independent test)
2. Drop rows with NaN labels
3. Normalize label case to lowercase
4. Validate required columns exist in both sets
5. Validate test labels are a subset of training labels
6. 80/20 stratified split for validation
7. Fit pipeline on training split → evaluate on validation
8. Refit pipeline on full training data → evaluate on independent test
9. Save `model.pkl` and `preprocessor.pkl`

**Important: The final model is trained on ALL training data (no hold-out used for final fit), with the independent test set kept completely separate. This is correct procedure.**

### Current Reported Metrics (Hardcoded in app.py)

| Metric | Value |
|---|---|
| Accuracy | 98.08% |
| Precision | 98.00% |
| Recall | 98.00% |
| F1 Score | 98.00% |
| Test Samples | 52 (25 normal, 27 Probe) |

**⚠️ These metrics are hardcoded strings in `insights_metrics()` and `insights_confusion()` in `app.py`, not dynamically computed from the model at runtime.**

### Missing ML Components

- No SVM implementation
- No Neural Network implementation
- No ensemble/hybrid model
- No per-class precision/recall/F1 endpoint
- No macro/weighted F1 computation
- No ROC-AUC or PR-AUC
- No detection latency measurement
- No feature importance endpoint
- `utils/preprocessing.py` is completely empty

---

## 5. Existing Dataset Modifications

### What is the "modified dataset"?

The project has **completely replaced** the NSL-KDD 41-feature schema with a new, purpose-built 27-feature live network flow schema. This is the core research contribution of the existing project.

### NSL-KDD vs. Current Dataset Comparison

| Dimension | NSL-KDD | Current (live_flows) |
|---|---|---|
| Feature count | 41 + label + difficulty | 27 + label |
| Feature type | Connection-level KDD features | Live flow statistical features |
| Protocol encoding | Categorical (tcp/udp/icmp etc.) | Categorical (tcp/udp/other) |
| Service field | Yes (http, ftp, etc.) | No |
| Flag field | Yes (SF, REJ, etc.) | No — replaced by individual TCP flag counts |
| Bytes features | src_bytes, dst_bytes | forward_bytes, backward_bytes + ratios |
| Rate features | No | Yes (packets_per_second, bytes_per_second) |
| Packet size stats | No | Yes (mean/min/max/std) |
| Statistical features | 2-second window counts | Directional ratios |
| Label taxonomy | 23 attack types + normal | binary: normal / probe |
| Collection method | Simulated (DARPA/KDD Cup) | Live Scapy capture on loopback |
| Training samples | 125,973 | 115 |
| Test samples | 22,544 | 52 |
| Class balance (train) | Heavily imbalanced (~20% normal) | Unknown exact ratio (approximately balanced based on collection) |

### Dataset Files

| File | Role | Samples | Notes |
|---|---|---|---|
| `live_flows.csv` | Training data | 115 rows | Labels: "normal", "probe" (lowercase) |
| `test_flows.csv` | Independent test | 52 rows | Labels: "Normal", "Probe" (title-case) — normalized to lowercase during eval |
| `live_flows_unlabeled.csv` | Archived unlabeled | Unknown | Separated by clean_dataset.py |
| `KDDTrain+.txt` | Legacy reference | 125,973 rows | NOT used by current pipeline |
| `KDDTest+.txt` | Legacy reference | 22,544 rows | NOT used by current pipeline |

### Dataset Collection Pipeline

```
Scapy capture → NetworkFlow objects → build_feature_vector()
→ save_flows_to_csv() → live_flows.csv / test_flows.csv

clean_dataset.py:
  - Removes unlabeled samples (archived to live_flows_unlabeled.csv)
  - Verifies "Probe" samples have ports in range 8000–8049
  - Removes mis-labeled probe flows (e.g., background traffic mislabeled)
```

### Known Dataset Issues

1. **Very small dataset:** 115 training + 52 test samples. This is extremely small for ML research and means evaluation numbers are statistically unstable.
2. **Controlled and uniform probe traffic:** Probe samples come from a port-scan of 127.0.0.1:8000–8049. This creates a highly distinctive and repetitive pattern that inflates apparent model accuracy.
3. **Short-duration extreme rates:** Very short flows produce extremely large `packets_per_second` and `bytes_per_second` values (visible in test_flows.csv: values of 50,231 and 5,309,245 packets/bytes per second). This can cause numeric instability.
4. **Binary only:** Only normal vs. probe — no DoS, R2L, U2R classes.
5. **Loopback only:** All data captured on Windows NPF_Loopback, not real network traffic.

---

## 6. Existing API Endpoints

| Endpoint | Method | Status | Description |
|---|---|---|---|
| `/` | GET | ✅ Working | Health check |
| `/predict` | POST | ✅ Working | Manual 27-feature prediction |
| `/capture` | POST | ✅ Working | Live Scapy capture + predict |
| `/monitor/history` | GET | ✅ Working | Returns last 50 predictions + counts |
| `/alerts` | GET | ✅ Working | Returns last 50 alerts |
| `/alerts/<id>` | PATCH | ✅ Working | Update alert status |
| `/settings` | GET | ✅ Working | Return current settings |
| `/settings` | POST | ✅ Working | Update settings (validates types) |
| `/model/retrain` | POST | ⚠️ Stub | Returns 501 Not Implemented |
| `/model/reload` | POST | ✅ Working | Reload pkl from disk |
| `/model/reset` | POST | ✅ Working | Reset settings + reload model |
| `/insights/metrics` | GET | ⚠️ Hardcoded | Returns hardcoded 98.08% metrics |
| `/insights/confusion` | GET | ⚠️ Hardcoded | Returns hardcoded 2×2 matrix |
| `/insights/traffic` | GET | ✅ Working | Live counts from prediction_history |

**Missing endpoints:**
- No `/health` with deep health info (model loaded, disk space, etc.)
- No `/metrics` (Prometheus-format)
- No `/model/info` (version, training date, feature schema)
- No `/predict/batch` (batch inference)
- No `/predict/explain` (feature importance)
- No per-class metrics endpoint
- No authentication endpoints (no `/auth/token`)

---

## 7. Existing Database / Storage

| Storage | Technology | What is stored | Persistence |
|---|---|---|---|
| Prediction history | JSON file (`prediction_history.json`) | All predictions: timestamp, prediction, confidence, IPs, ports, protocol | File on disk — survives restart |
| Alerts | JSON file (`alerts.json`) | Alert objects: id, timestamp, type, severity, IPs, ports, protocol, confidence, description, status | File on disk — survives restart |
| Settings | In-memory Python dict | IDS configuration | Lost on restart (defaults restored) |
| Model artifacts | `.pkl` files | Trained sklearn pipeline + preprocessor | File on disk |

**No relational database.** No SQLite, PostgreSQL, or any other DB.
**No Redis.** No caching layer.
**No Kafka.** No message queue.

**Issues:**
- Alert IDs use `len(alerts_data) + 1` — this will produce duplicate IDs if alerts are deleted or the file is modified externally.
- Settings are not persisted — reset to defaults on every restart.
- prediction_history grows unboundedly (no rotation or archiving).
- No indexes, no query capability beyond sequential scan of JSON.

---

## 8. Existing Streaming Implementation

**There is no streaming implementation.**

The current approach is synchronous HTTP request-response:
- The frontend polls `/monitor/history` and `/alerts` every 3–5 seconds.
- There is no WebSocket, Server-Sent Events, Redis Streams, or Kafka.
- Capture is triggered by a REST call and blocks until complete.
- The capture runs in a background thread, but results are returned synchronously in the same HTTP response.

---

## 9. Existing Deployment Support

| Item | Status |
|---|---|
| Dockerfile (backend) | ❌ Not present |
| Dockerfile (frontend) | ❌ Not present |
| docker-compose.yml | ❌ Not present |
| Kubernetes manifests | ❌ Not present |
| .env file | ❌ Not present |
| Environment variable config | ❌ Config is hardcoded in source |
| Health endpoint | ⚠️ `/` returns a message but no structured health info |
| Graceful shutdown | ❌ Not implemented |
| Process manager | ❌ Flask dev server only (`debug=True`) |
| WSGI server (gunicorn/uWSGI) | ❌ Not configured |

`requirements.txt` is missing `scapy`, which is a required dependency for the backend's live capture functionality.

---

## 10. Existing Monitoring

| Item | Status |
|---|---|
| Structured logging | ❌ No logging module used anywhere |
| Request/response logs | ❌ Flask default only (debug mode) |
| Inference latency tracking | ❌ Not measured |
| Throughput tracking | ❌ Not measured |
| Error tracking | ❌ No error handling beyond try/except returning 500 |
| Prometheus metrics | ❌ Not present |
| Grafana | ❌ Not present |
| Health checks | ⚠️ Minimal (only `/` route) |
| Alerting/paging | ❌ Not implemented (email_alerts setting exists as placeholder) |

---

## 11. Existing Security

| Item | Status |
|---|---|
| Authentication | ❌ No auth on any endpoint |
| Authorization | ❌ No role checks |
| JWT | ❌ Not implemented |
| API keys | ❌ Not implemented |
| CORS | ⚠️ CORS enabled for all origins (`CORS(app)` with no restrictions) |
| Rate limiting | ❌ Not implemented |
| Input validation | ✅ Partial — `/predict` validates feature types; `/settings` validates types |
| Secret management | ⚠️ No secrets currently, but no `.env` framework either |
| HTTPS | ❌ HTTP only |
| SQL injection protection | N/A (no SQL used) |
| Capture safety | ✅ `generate_local_probe_traffic()` restricted to 127.0.0.1 |

---

## 12. Existing Tests

**There are no tests of any kind.**

- No unit tests
- No integration tests
- No smoke tests
- No pytest configuration
- No test runner configured

The only validation is manual testing described in README.md.

---

## 13. Missing Journal Requirements

The target research paper "Cloud-Based Real-Time IDS Using AI" defines requirements that are partially or fully absent from the current project.

| Category | Requirement | Current Status |
|---|---|---|
| ML | SVM model | ❌ Missing |
| ML | Neural Network model | ❌ Missing |
| ML | Ensemble/hybrid detection | ❌ Missing |
| ML | Multi-class classification | ❌ Missing (binary only) |
| ML | Per-class metrics | ❌ Not exposed dynamically |
| ML | Minority class analysis | ❌ Not present |
| ML | Class imbalance techniques (SMOTE etc.) | ⚠️ class_weight="balanced" only |
| ML | Model comparison table | ❌ Not present |
| ML | Confusion matrix (dynamic) | ❌ Hardcoded |
| ML | ROC-AUC, PR-AUC | ❌ Not computed |
| ML | Detection latency measurement | ❌ Not measured |
| Data | Reproducible experiment pipeline | ⚠️ Partially (train_model.py exists, no seed docs) |
| Data | Dataset hash / version | ❌ Not present |
| Data | DATASET_DOCUMENTATION.md | ❌ Not present |
| Data | DATASET_CHANGELOG.md | ❌ Not present |
| Data | Data leakage safeguards documented | ⚠️ Implemented correctly but not documented |
| Streaming | Kafka or Redis Streams | ❌ Not present |
| Streaming | Producer/consumer pattern | ❌ Not present |
| Streaming | Message timestamps + event IDs | ❌ Not present |
| Streaming | Dead-letter handling | ❌ Not present |
| Simulator | Multi-class traffic simulation | ❌ Probe-only localhost probe |
| Simulator | DoS simulation | ❌ Not present |
| Simulator | R2L / U2R simulation | ❌ Not present |
| Alert | Severity based on attack type | ⚠️ Confidence-only severity |
| Alert | Risk score | ❌ Not present |
| Alert | Alert correlation / deduplication | ❌ Not present |
| Alert | Event ID / correlation ID | ❌ Not present |
| Storage | Relational database | ❌ JSON files only |
| Storage | Proper indexes | ❌ N/A (no DB) |
| Storage | Model versioning table | ❌ Not present |
| Dashboard | Real-time traffic chart (real data) | ❌ TrafficChart uses hardcoded mock data |
| Dashboard | Threat distribution (real data) | ❌ ThreatDistribution uses wrong mock data |
| Dashboard | Detection latency display | ❌ Not present |
| Dashboard | Throughput display | ❌ Not present |
| Dashboard | Model comparison view | ❌ Not present |
| Dashboard | Time range filtering | ❌ Not present |
| Dashboard | Search / attack type filter | ❌ Not present |
| Deployment | Docker | ❌ Not present |
| Deployment | docker-compose | ❌ Not present |
| Deployment | Kubernetes manifests | ❌ Not present |
| Deployment | HPA (autoscaling) | ❌ Not present |
| Deployment | Health endpoint (structured) | ⚠️ Minimal |
| Deployment | Environment-based config | ❌ Hardcoded |
| Deployment | Graceful shutdown | ❌ Not present |
| Observability | Structured logging | ❌ Not present |
| Observability | Prometheus metrics | ❌ Not present |
| Observability | Request/inference latency | ❌ Not measured |
| Security | Authentication | ❌ Not present |
| Security | Rate limiting | ❌ Not present |
| Security | CORS restriction | ⚠️ Open CORS |
| Security | .env / secret management | ❌ Not present |
| Tests | Unit tests | ❌ Not present |
| Tests | Integration tests | ❌ Not present |
| Tests | Smoke test | ❌ Not present |
| Docs | EXPERIMENTS.md | ❌ Not present |
| Docs | ARCHITECTURE.md | ❌ Not present |
| Docs | FINAL_RESULTS.md | ❌ Not present |
| Docs | JOURNAL_TRACEABILITY.md | ❌ Not present |

---

## 14. Technical Risks

### HIGH RISK

**R1: Extreme rate values from short-duration flows**
- Flows with very short durations (e.g., 1.88e-5 seconds) produce `packets_per_second` of 106,184 and `bytes_per_second` of 5,309,245.
- These extreme outliers can dominate StandardScaler and cause unpredictable model behavior on longer, more realistic flows.
- **Evidence:** `test_flows.csv` row 2: `packets_per_second=106184.91`, `bytes_per_second=5309245.57`
- **Recommendation:** Add a duration floor (e.g., min 1ms) and clip or log-transform rate features.

**R2: Metrics are hardcoded — not produced by the model**
- `/insights/metrics` returns `{"accuracy": 98.08, "precision": 98.00, ...}` as literal Python values.
- `/insights/confusion` returns a hardcoded matrix `[[24,1],[0,27]]`.
- If the model is retrained with different data, the dashboard will still show the old numbers.
- **Impact:** Research integrity concern — the dashboard cannot be trusted to show current model performance.
- **Recommendation:** Compute and persist metrics at training time; load them dynamically at runtime.

**R3: Very small dataset (115 + 52 samples)**
- With 115 training samples and highly uniform probe traffic, the model learns port-pattern shortcuts rather than true intrusion behavior.
- The 98% accuracy is likely an artifact of the controlled, repetitive probe traffic pattern rather than generalizable detection capability.
- **Impact:** Results cannot be generalized beyond the specific controlled test environment.
- **Recommendation:** This is a known limitation, not a bug. Must be clearly documented. Consider augmenting with synthetic flows.

**R4: Missing scapy in requirements.txt**
- The live capture functionality in `url_kdd.py` requires Scapy, but it is not listed in `requirements.txt`.
- Any fresh installation will fail at runtime when `/capture` is called.
- **Recommendation:** Add `scapy>=2.5.0` to `requirements.txt`.

### MEDIUM RISK

**R5: Alert ID collision potential**
- Alert IDs use `len(alerts_data) + 1`. If alerts are removed from `alerts.json` externally and the backend restarts, IDs will collide.
- **Recommendation:** Use `uuid4()` for alert IDs.

**R6: Settings not persisted**
- The settings dict is in-memory. Every Flask restart resets all settings to defaults.
- **Recommendation:** Persist settings to `data/settings.json`.

**R7: Prediction history grows unboundedly**
- `prediction_history.json` has no size cap or rotation. Long-running deployments will accumulate data indefinitely.
- **Recommendation:** Add a configurable history size limit or archive old entries.

**R8: Label case inconsistency between train and test sets**
- `live_flows.csv` labels are lowercase ("normal", "probe").
- `test_flows.csv` labels are title-case ("Normal", "Probe").
- **Current mitigation:** `clean_dataset()` normalizes both to lowercase — the pipeline handles this correctly.
- **Risk:** Future data collection that bypasses this normalization could introduce silent mislabeling.
- **Recommendation:** Enforce lowercase labeling at the CSV writing stage in `save_flows_to_csv()`.

**R9: Confusion matrix labels on Insights page are wrong**
- The Insights page shows column headers "Predicted Probe" and "Predicted Malicious" but the matrix is Normal vs Probe.
- This is a UI bug that would confuse any reviewer of the research.

**R10: CORS open to all origins**
- `CORS(app)` with no origin restriction allows any web page to call the API.
- For a local demo this is acceptable, but should be locked down for any deployment.

### LOW RISK

**R11: scaler.pkl is a dead artifact**
- `scaler.pkl` was saved on 2026-09-14, before `model.pkl` was last updated on 2026-09-15.
- It is not referenced anywhere in the current codebase. It is likely from a previous pipeline iteration.
- **Recommendation:** Document and optionally remove it to avoid confusion.

**R12: Flask dev server in production mode**
- `app.run(debug=True, host='0.0.0.0', port=5000)` — debug mode exposes the Werkzeug debugger and should never be used in production.

**R13: TrafficChart and ThreatDistribution use mock data**
- Dashboard shows fabricated traffic and threat names (DDoS, Malware, Phishing, SQL Injection) that have nothing to do with the actual system.
- This is a significant issue for any research demonstration.

**R14: SVM and Neural Network shown in Settings dropdown but not implemented**
- The frontend Settings page offers "Support Vector Machine" and "Neural Network" as model options.
- The backend rejects any model selection other than "random-forest" with a 400 error.
- A user clicking SVM will see a confusing error.

---

## 15. Recommended Implementation Order

Based on the audit, this is the logical sequence to upgrade the project without breaking existing functionality:

### Phase 1: Stabilize Existing Foundation
- Fix `requirements.txt` (add scapy with version pin)
- Fix label normalization at write time in `save_flows_to_csv()`
- Fix alert ID generation (uuid4)
- Persist settings to JSON file
- Add prediction history size limit
- Fix Insights page confusion matrix labels (UI bug)
- Fix duration floor for rate calculation (prevent ÷0 and extreme values)

### Phase 2: Dynamic Metrics
- Move metrics computation into training script → save `metrics.json` alongside model artifacts
- Make `/insights/metrics` and `/insights/confusion` load from `metrics.json`
- Add `/model/info` endpoint (version, features, training date, metrics)
- Expose per-class metrics dynamically

### Phase 3: Add SVM + Neural Network + Hybrid Model
- Implement SVM (sklearn SVC with probability=True)
- Implement Neural Network (sklearn MLPClassifier or torch MLP)
- Implement ensemble/hybrid (soft voting or weighted)
- Update training script to train, evaluate, and save all four models
- Update `/settings` to accept and route between active model
- Generate experiment comparison table

### Phase 4: Dataset & Research Documentation
- Write `DATASET_DOCUMENTATION.md`
- Write `DATASET_CHANGELOG.md`
- Add dataset validation script (schema check, distribution check)
- Add `EXPERIMENTS.md` template

### Phase 5: Traffic Simulator Enhancement
- Extend `generate_local_probe_traffic()` into a proper simulator module
- Add synthetic flow generation for DoS/normal using statistical distributions
- Wire simulator to feature schema for reproducible experiment inputs

### Phase 6: Backend Improvements
- Add structured logging (Python `logging` module with JSON formatter)
- Add `/health` endpoint with model status, file paths, version
- Add detection latency measurement (timestamp before/after inference)
- Add `/metrics` endpoint (Prometheus-compatible text format)
- Persist settings to disk
- Add input sanitization and rate limiting (Flask-Limiter)
- Restrict CORS to known origins

### Phase 7: Fix Frontend Dashboard
- Connect `TrafficChart` to real data from `/monitor/history`
- Connect `ThreatDistribution` to real alert data
- Fix Insights confusion matrix labels
- Add detection latency display to Insights
- Add throughput metric to Dashboard
- Fix Settings model dropdown to reflect actual available models

### Phase 8: Streaming Layer (Redis Streams or simple queue)
- Introduce an internal event queue between capture and inference
- Add event timestamps + correlation IDs
- This can be done with Python `queue.Queue` for local demo
- Document as Redis Streams compatible for cloud deployment

### Phase 9: Containerization
- Write `Dockerfile` for backend
- Write `Dockerfile` for frontend
- Write `docker-compose.yml` tying services together
- Add health checks to both containers
- Move all config to environment variables

### Phase 10: Kubernetes Readiness
- Write Kubernetes Deployment, Service, ConfigMap, Secret template
- Write HorizontalPodAutoscaler manifest
- Document local testing with minikube or kind

### Phase 11: Experiments & Research Validation
- Run full experiment suite: RF vs SVM vs NN vs Hybrid
- Record all metrics without fabrication
- Generate `EXPERIMENTS.md` with real numbers
- Generate `FINAL_RESULTS.md`

### Phase 12: Tests
- Write pytest unit tests: model loading, prediction, feature validation
- Write integration test: /predict endpoint
- Write smoke test: full pipeline from feature input to alert
- Add test runner to CI/CD

---

*End of PROJECT_AUDIT.md*
