# JOURNAL TRACEABILITY MATRIX

**Project:** AI-Powered Intrusion Detection System (AI IDS)
**Research Reference:** "Cloud-Based Real-Time Intrusion Detection System Using Artificial Intelligence"
**Architecture Name:** Cloud-RT-IDS
**Traceability Date:** 2026-09-23
**Basis:** Complete audit of existing repository (see PROJECT_AUDIT.md)

---

## How to Read This Document

- **Status: ✅ Implemented** — Requirement is present and functional in the existing codebase.
- **Status: ⚠️ Partial** — A related component exists but it is incomplete, incorrect, or not research-quality.
- **Status: ❌ Missing** — No implementation exists. Must be built from scratch.
- **Status: 🔒 Hardcoded** — The value or behavior is present in the UI/API but is not actually produced by the running system (fabricated output). This is a research integrity issue.
- **Gap** column describes the delta between what exists and what is needed.
- **Implementation** column describes the planned action to close the gap.

---

## Requirement Matrix

### 1. Real-Time Telemetry Ingestion

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Network traffic ingestion at flow level | `POST /capture` triggers Scapy sniff on loopback interface; `capture_flows()` in `url_kdd.py` | ⚠️ Partial | Capture is synchronous HTTP-triggered, not continuous; captures only Windows loopback (`\Device\NPF_Loopback`), not real network adapters; no telemetry agent or continuous ingestion loop | Phase 6: Add continuous background capture thread with configurable interface; add `/capture/start` and `/capture/stop` endpoints; add interface selection config |
| Timestamped event ingestion | Packets timestamped by Scapy (`packet.time`); predictions timestamped with `datetime.now()` | ⚠️ Partial | No end-to-end event correlation ID; ingestion timestamp and inference timestamp are not both recorded to measure pipeline latency | Phase 6: Add `event_id` (uuid4) generated at ingestion; record `ingestion_ts`, `inference_ts`, `alert_ts` for each event |
| Source/destination IP metadata | `src_ip`, `dst_ip`, `src_port`, `dst_port` captured per flow and stored in alerts and history | ✅ Implemented | Minor: manual `/predict` stores "N/A" for IPs since they come from user input, not live capture | Phase 1: Document this behavior; acceptable limitation for manual mode |
| Protocol identification | `protocol` field (tcp/udp/other) captured from packet layer | ✅ Implemented | Only TCP/UDP supported; ICMP and other protocols filtered out | Acceptable for current scope; document as known limitation |

---

### 2. Streaming Layer

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Event streaming (Kafka or Redis Streams) | Not present | ❌ Missing | No message queue of any kind; frontend polls REST every 3–5 seconds | Phase 8: Implement internal Python `queue.Queue` as a drop-in streaming layer; design as Redis Streams compatible for future cloud deployment; add producer (ingestion → queue) and consumer (queue → inference) |
| Producer component | Not present | ❌ Missing | No producer pattern; capture and inference are tightly coupled in a single function | Phase 8: Decouple capture from inference using producer/consumer; `capture_flows()` puts events on queue; inference worker consumes from queue |
| Consumer component | Not present | ❌ Missing | No consumer pattern | Phase 8: Implement inference consumer worker thread |
| Message serialization | Not present | ❌ Missing | Feature dicts are Python objects in memory, not serialized messages | Phase 8: Serialize flow feature dicts to JSON with schema version + event_id + timestamps |
| Dead-letter handling | Not present | ❌ Missing | Malformed flows silently dropped | Phase 8: Route failed inference events to a dead-letter log file |
| Consumer health monitoring | Not present | ❌ Missing | No worker health status | Phase 6: Expose consumer queue depth and worker status in `/health` endpoint |
| Event/correlation IDs | Not present | ❌ Missing | No way to trace a flow event through the system | Phase 8: Generate `event_id` at capture time; propagate through inference, alert, and storage |

---

### 3. Feature Engineering

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Flow-level feature extraction | `build_feature_vector()` in `url_kdd.py` computes 27 features from `NetworkFlow` dataclass | ✅ Implemented | Feature schema is custom (not NSL-KDD); preserved as research contribution | No change to feature schema; document in DATASET_DOCUMENTATION.md |
| Feature validation at inference time | `/predict` endpoint validates all 27 features by name, type, and protocol enum | ✅ Implemented | No schema version tracking; no validation that the feature order matches the saved model | Phase 2: Add feature schema version to `metrics.json`; validate at model load time |
| Categorical encoding | `OneHotEncoder(handle_unknown="ignore")` for `protocol` column inside the pipeline | ✅ Implemented | No explicit handling documented for unknown protocol values during inference | Phase 1: Document `handle_unknown="ignore"` behavior; test with unknown protocol value |
| Numerical scaling | `StandardScaler` for 26 numeric features inside the pipeline | ✅ Implemented | Extreme rate values (packets_per_second up to 106,184; bytes_per_second up to 5,309,245) from short-duration flows may distort scaler statistics | Phase 1: Add duration floor (min 1ms) in `build_feature_vector()`; consider log-transform or clipping for rate features |
| Consistent train/inference preprocessing | Preprocessing embedded in sklearn `Pipeline` — same transformations applied at training and inference | ✅ Implemented | No data leakage risk from this design; scaler is fit only on training data | No change needed; document this as a correct design choice in DATASET_DOCUMENTATION.md |
| Feature importance / explainability | Not exposed | ❌ Missing | Random Forest provides `.feature_importances_` but it is never extracted or exposed | Phase 3: Extract and save feature importances at training time; expose via `/model/info` or `/predict/explain` |

---

### 4. ML Inference

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Real-time inference on incoming flows | `pipeline.predict()` and `pipeline.predict_proba()` called per flow in `/capture` and `/predict` | ✅ Implemented | Inference is synchronous within HTTP request; no async inference worker; no latency measurement | Phase 2: Record inference latency (`time.perf_counter()`) per prediction; expose in response and `/health` |
| Confidence score | `float(np.max(model.predict_proba(features_df)))` returned per prediction | ✅ Implemented | Confidence is the max class probability; not calibrated; no uncertainty quantification | Acceptable for current scope; document |
| Batch inference | Not supported | ❌ Missing | Only single-flow inference via `/predict`; `/capture` processes flows in a sequential loop but is not a true batch endpoint | Phase 2: Add `POST /predict/batch` accepting a list of feature dicts |
| Inference latency measurement | Not measured | ❌ Missing | No timing around the `pipeline.predict()` call | Phase 2: Add `perf_counter` timing; store latency with each prediction record; expose p50/p95/p99 in `/metrics` |
| Model version awareness | Not present | ❌ Missing | The loaded model has no version metadata; `/model/reload` does not report which version was loaded | Phase 3: Add `model_version` and `trained_at` fields to saved `metrics.json`; expose via `/model/info` |

---

### 5. Random Forest

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Random Forest classifier | `RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced", n_jobs=-1)` inside sklearn Pipeline | ✅ Implemented | Hyperparameters not documented or justified; no hyperparameter search performed | Phase 3: Document hyperparameter choices in EXPERIMENTS.md; optionally run basic grid search |
| Trained on project dataset | Trained on `live_flows.csv` (115 samples, normal + probe) | ✅ Implemented | Dataset is very small and highly controlled; performance numbers are not generalizable | Document clearly as a known limitation |
| Feature importance output | Not exposed | ❌ Missing | `.feature_importances_` available from fitted RF but never saved or returned | Phase 3: Save to `metrics.json` at training time; expose via API |
| Class imbalance handling | `class_weight="balanced"` parameter | ⚠️ Partial | Only one technique applied; no SMOTE, no threshold tuning; dataset has unknown exact class balance | Phase 3: Log class distribution at training time; evaluate whether additional balancing improves minority recall |

---

### 6. Support Vector Machine (SVM)

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| SVM classifier | Not implemented | ❌ Missing | Settings dropdown shows "SVM" option but backend rejects it with 400 error | Phase 3: Implement `sklearn.svm.SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=42)` inside the same preprocessing pipeline |
| SVM training and evaluation | Not implemented | ❌ Missing | No training script section for SVM | Phase 3: Add SVM training block to `train_model.py`; save as `model_svm.pkl` |
| SVM comparison metrics | Not present | ❌ Missing | No experiment table comparing RF vs SVM | Phase 3: After training SVM, compute all metrics; write to `metrics_svm.json`; include in EXPERIMENTS.md |
| SVM inference endpoint | Not implemented | ❌ Missing | | Phase 3: Route `/predict` to active model based on `settings["ml_model"]`; support "random-forest", "svm", "neural-network", "hybrid" |

---

### 7. Neural Network

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Neural Network classifier | Not implemented | ❌ Missing | Settings dropdown shows "Neural Network" but backend rejects it | Phase 3: Implement `sklearn.neural_network.MLPClassifier` with reasonable architecture (e.g., hidden_layer_sizes=(64, 32), max_iter=500, random_state=42) |
| Neural Network training and evaluation | Not implemented | ❌ Missing | | Phase 3: Add NN training block to `train_model.py`; save as `model_nn.pkl` |
| Neural Network comparison metrics | Not present | ❌ Missing | | Phase 3: Compute all metrics; write to `metrics_nn.json` |
| Neural Network inference endpoint | Not implemented | ❌ Missing | | Phase 3: Route via active model setting (same as SVM above) |

---

### 8. Ensemble / Hybrid Detection

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Hybrid model combining RF + SVM + NN | Not implemented | ❌ Missing | No ensemble logic exists | Phase 3: Implement soft-voting ensemble using `sklearn.ensemble.VotingClassifier` (or manual weighted averaging of `predict_proba` from each model) |
| Ensemble decision strategy | Not defined | ❌ Missing | | Phase 3: Use soft voting (average of class probabilities) as default; document choice; compare against majority voting in EXPERIMENTS.md |
| Ensemble training | Not implemented | ❌ Missing | | Phase 3: Train ensemble after all three base models are trained; save as `model_hybrid.pkl` |
| Ensemble confidence score | Not implemented | ❌ Missing | | Phase 3: Return max averaged probability as confidence; include per-model votes in response |
| Per-model contribution to ensemble | Not present | ❌ Missing | | Phase 3: Optionally expose per-model prediction alongside ensemble result in `/predict` response |

---

### 9. Alert Generation

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Alert on non-normal predictions | `alerts_data.append(...)` when `prediction != "normal"` and `confidence >= threshold` | ✅ Implemented | Alert only triggered on non-normal with confidence check; no alert deduplication; no suppression window | Phase 7: Add alert deduplication (same src/dst/type within 60s = suppressed or updated) |
| Alert severity levels | `get_alert_severity(confidence)`: critical ≥90%, high ≥75%, medium otherwise | ⚠️ Partial | Severity based solely on confidence — ignores attack type; journal recommends attack-type-aware severity (e.g., probe=LOW, DoS=HIGH, U2R=CRITICAL) | Phase 7: Add attack-type severity lookup table; combine with confidence for final severity |
| Risk score | Not present | ❌ Missing | No numeric risk score per alert | Phase 7: Implement risk score formula: e.g., `risk_score = confidence * severity_weight * frequency_factor` |
| Alert unique ID | Sequential integer: `len(alerts_data) + 1` | ⚠️ Partial | Collision risk if `alerts.json` is modified; non-unique after restart with modified file | Phase 1: Replace with `str(uuid.uuid4())` |
| Alert correlation ID (event_id) | Not present | ❌ Missing | No way to link an alert back to the original captured flow event | Phase 8: Propagate `event_id` from capture → prediction → alert |
| Alert status lifecycle | `active` → `reviewed` │ `false-positive` via `PATCH /alerts/<id>` | ✅ Implemented | No `resolved` status; no escalation; no auto-expiry | Acceptable for current scope |
| Alert persistence | `alerts.json` file on disk | ✅ Implemented | Not queryable; no filtering; growing file; no archival | Phase 6: Add archive rotation (move alerts older than N days to `alerts_archive.json`) |
| Source/destination capture | IP and port captured from live flow metadata | ✅ Implemented | Manual `/predict` stores "N/A" for IPs — acceptable known limitation | Document |

---

### 10. Persistent Storage

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Persistent event storage | `prediction_history.json` — survives restart | ⚠️ Partial | JSON file, not queryable; grows unboundedly; no schema validation on load | Phase 6: Add history size limit (configurable, default 10,000 records); add archival |
| Persistent alert storage | `alerts.json` — survives restart | ⚠️ Partial | JSON file; alert IDs can collide; no indexing; no pagination from API | Phase 6: Fix IDs; add pagination to `/alerts?page=1&limit=50` |
| Relational database | Not present | ❌ Missing | No SQL database of any kind | Phase 6: For the research scope, SQLite via `sqlite3` or `sqlalchemy` is sufficient and zero-dependency; full PostgreSQL is optional for cloud deployment |
| Model versions table | Not present | ❌ Missing | No record of which model was trained when, with what data | Phase 3: Save `model_metadata.json` alongside each trained model: version, algorithm, training_dataset_hash, training_timestamp, feature_schema_version, hyperparameters, metrics |
| Metrics table | Not present | ❌ Missing | Metrics are hardcoded in `app.py` | Phase 2: Save metrics to `metrics.json` at training time; load dynamically at runtime |
| Settings persistence | In-memory dict; lost on restart | ⚠️ Partial | Every restart resets to defaults | Phase 1: Save/load settings from `data/settings.json` |

---

### 11. Dashboard

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Total events KPI | `flowsAnalyzed` from `/monitor/history` | ✅ Implemented | Correct and live | No change needed |
| Normal events KPI | `normalFlows` from `/monitor/history` | ✅ Implemented | Correct and live | No change needed |
| Attack events KPI | `probeDetections` from `/monitor/history` | ⚠️ Partial | Only counts "probe"; if more attack classes added, this will miss them | Phase 7: Make attack count generic: all non-normal predictions |
| Attack rate KPI | Not displayed | ❌ Missing | No percentage metric showing attack vs total | Phase 7: Add attack_rate to `/monitor/history` response; display in Dashboard |
| Active alerts KPI | Active alert count from `/alerts` | ✅ Implemented | Correct and live | No change needed |
| System status KPI | "Safe" / "Under Attack" derived from active alerts | ✅ Implemented | Binary only; no severity-weighted status | Acceptable |
| Average detection latency KPI | Not displayed | ❌ Missing | Latency not measured anywhere | Phase 2 + Phase 7: Measure and display |
| Traffic over time chart | `TrafficChart.tsx` | 🔒 Hardcoded | Uses hardcoded mock data — completely fabricated numbers; not connected to any backend data | Phase 7: Connect to rolling window of prediction timestamps from history |
| Attack type distribution chart | `ThreatDistribution.tsx` | 🔒 Hardcoded | Shows DDoS, Malware, Phishing, SQL Injection — none of these exist in the actual system | Phase 7: Connect to real alert data grouped by prediction class and severity |
| Confusion matrix display | `Insights.tsx` — matrix loaded from `/insights/confusion` | 🔒 Hardcoded | Matrix values come from hardcoded `app.py` strings, not the actual model; column header says "Predicted Malicious" which is wrong | Phase 2 + Phase 7: Load from `metrics.json`; fix column labels |
| Model performance metrics display | `Insights.tsx` — metrics loaded from `/insights/metrics` | 🔒 Hardcoded | Values are hardcoded in `app.py`, not dynamically computed | Phase 2: Load from `metrics.json` |
| Detection latency display | Not present | ❌ Missing | | Phase 7: Add latency trend chart to Insights page |
| Model comparison display | Not present | ❌ Missing | Only one model; no comparison view | Phase 3 + Phase 7: Add model comparison table to Insights page |
| Real-time updates without full page refresh | Dashboard polls every 3s; Monitor polls every 5s | ⚠️ Partial | Polling is functional but inefficient; should use WebSocket or SSE for true real-time | Phase 8: Add Server-Sent Events (SSE) endpoint for real-time push; polling can remain as fallback |
| Filtering / search | Not present | ❌ Missing | No filtering on alerts or history by time, type, severity | Phase 7: Add query params to `/alerts` and `/monitor/history`: `?severity=high`, `?prediction=probe`, `?from=`, `?to=` |
| Alert details view | Alerts.tsx shows all fields inline | ✅ Implemented | No expandable detail view; no drill-down | Acceptable for current scope |

---

### 12. Monitoring / Observability

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Structured logging | Not present | ❌ Missing | No `logging` module used anywhere; Flask default stderr output only | Phase 6: Configure Python `logging` with JSON formatter; log all requests, predictions, errors, alerts |
| Request logging | Not present | ❌ Missing | | Phase 6: Add `@app.before_request` / `@app.after_request` hooks for structured request/response logging |
| Inference latency logging | Not present | ❌ Missing | | Phase 2: Record and log `inference_latency_ms` per prediction |
| Error tracking | Minimal try/except | ⚠️ Partial | Exceptions caught and returned as 500 JSON but never logged to file or monitoring system | Phase 6: Log all exceptions with stack trace |
| Prometheus-compatible metrics | Not present | ❌ Missing | No `/metrics` endpoint | Phase 6: Add `GET /metrics` in Prometheus text format: request_count, prediction_count_by_class, alert_count_by_severity, inference_latency_histogram, queue_depth |
| Queue depth monitoring | Not applicable (no queue) | ❌ Missing | Will be relevant after Phase 8 streaming implementation | Phase 8: Expose queue depth in `/health` and `/metrics` |
| Model performance over time | Not tracked | ❌ Missing | No drift detection, no rolling accuracy | Future work; not required for current phase |
| Health endpoint | `GET /` returns `{"message": "Intrusion Detection API Running!"}` | ⚠️ Partial | Not structured health; does not check model loaded status, disk space, or component liveness | Phase 6: Add `GET /health` returning: `model_loaded`, `model_version`, `history_count`, `alert_count`, `queue_depth`, `uptime_seconds` |

---

### 13. Containerization

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Backend Dockerfile | Not present | ❌ Missing | | Phase 9: Write `docker/Dockerfile.backend` based on `python:3.11-slim`; install requirements; expose port 5000 |
| Frontend Dockerfile | Not present | ❌ Missing | | Phase 9: Write `docker/Dockerfile.frontend` using `node:20-alpine` for build; `nginx:alpine` for serving |
| docker-compose.yml | Not present | ❌ Missing | | Phase 9: Write `docker-compose.yml` with services: backend, frontend; shared network; volume mounts for data and models |
| Environment-based configuration | Not present | ❌ Missing | All config hardcoded in source (port 5000, file paths, thresholds) | Phase 9: Move all config to environment variables with `.env.example` |
| Health checks in containers | Not present | ❌ Missing | | Phase 9: Add `HEALTHCHECK` to Dockerfiles using `/health` endpoint |
| Graceful shutdown | Not present | ❌ Missing | Flask runs with `debug=True`; no signal handling | Phase 9: Add `signal.signal(SIGTERM, ...)` handler; use gunicorn for production mode |
| Structured logs from containers | Not present | ❌ Missing | | Phase 6 prerequisite: structured logging must exist before containerization |

---

### 14. Kubernetes Readiness

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Kubernetes Deployment manifest | Not present | ❌ Missing | | Phase 10: Write `k8s/deployment-backend.yaml`, `k8s/deployment-frontend.yaml` |
| Kubernetes Service manifest | Not present | ❌ Missing | | Phase 10: Write `k8s/service-backend.yaml` (ClusterIP), `k8s/service-frontend.yaml` (LoadBalancer/NodePort) |
| ConfigMap | Not present | ❌ Missing | | Phase 10: Write `k8s/configmap.yaml` for non-secret config (port, log level, threshold defaults) |
| Secret template | Not present | ❌ Missing | | Phase 10: Write `k8s/secret.template.yaml` with placeholder values and instructions |
| HorizontalPodAutoscaler | Not present | ❌ Missing | | Phase 10: Write `k8s/hpa-backend.yaml`: scale inference service 1→N replicas on CPU threshold |
| Liveness probe | Not present | ❌ Missing | | Phase 10: Configure `livenessProbe` using `GET /health` in Deployment manifests |
| Readiness probe | Not present | ❌ Missing | | Phase 10: Configure `readinessProbe` using `GET /health` in Deployment manifests |

---

### 15. Horizontal Scaling

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Multiple inference replicas | Not supported | ❌ Missing | Single monolith; no stateless inference service | Phase 9–10: Separate inference into a stateless path; session state (history, alerts) must be in shared storage (file or DB) not in-memory |
| Shared storage between replicas | Not applicable | ❌ Missing | Currently all state is in-memory or local files — incompatible with multi-replica deployment | Phase 9: Move to file-based storage (already partially done); Phase 10: document SQLite/PostgreSQL path for true multi-replica |
| Load balancing | Not applicable | ❌ Missing | | Phase 10: Kubernetes Service provides load balancing automatically with multiple replicas |
| Autoscaling documentation | Not present | ❌ Missing | | Phase 10: Document 1→N replica scaling behavior; note that actual autoscaling performance was not benchmarked on local hardware |

---

### 16. Security

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| API authentication | Not present | ❌ Missing | All endpoints open with no auth | Phase 6: Add API key authentication via `X-API-Key` header; validate against env variable |
| Role-based authorization | Not present | ❌ Missing | | Deferred — API key is sufficient for single-user research prototype |
| Environment variables for secrets | Not present | ❌ Missing | No secrets currently, but no framework either | Phase 9: Add `python-dotenv`; move all config to `.env`; add `.env.example` |
| No hardcoded credentials | ✅ No credentials hardcoded currently | ✅ Implemented | No passwords or keys in source code at this time | Maintain — ensure this stays true as auth is added |
| Input validation | `/predict` validates feature types and protocol enum; `/settings` validates types and ranges | ✅ Implemented | No max-length checks on string inputs; no protection against deeply nested JSON bombs | Phase 6: Add `Content-Length` limit via `MAX_CONTENT_LENGTH`; validate protocol string length |
| Rate limiting | Not present | ❌ Missing | `/capture` can be called rapidly, triggering Scapy capture loops | Phase 6: Add `Flask-Limiter`: limit `/capture` to 1 request per 10s; limit `/predict` to 60/minute |
| CORS restriction | `CORS(app)` — open to all origins | ⚠️ Partial | Allows any website to call the API | Phase 6: Restrict CORS to `localhost` origins for local demo; configurable via env variable |
| Audit logs | Not present | ❌ Missing | No record of who called what endpoint | Phase 6: Structured request logging covers this for single-user prototype |
| HTTPS | HTTP only | ❌ Missing | | Phase 9: Document nginx/SSL termination in Docker; note that HTTPS is environment-specific |
| Capture safety restriction | `generate_local_probe_traffic()` restricted to `127.0.0.1` | ✅ Implemented | Safety check is in place; would need stronger isolation in multi-user deployment | No change needed for local prototype |

---

### 17. Model Evaluation

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Accuracy | Computed in `train_model.py`; hardcoded in `app.py` | 🔒 Hardcoded | Not dynamically served | Phase 2: Save to `metrics.json`; load dynamically |
| Precision (macro) | Computed in `train_model.py`; hardcoded in `app.py` | 🔒 Hardcoded | | Phase 2: Same |
| Recall (macro) | Computed in `train_model.py`; hardcoded in `app.py` | 🔒 Hardcoded | | Phase 2: Same |
| F1-score (macro) | Computed in `train_model.py`; hardcoded in `app.py` | 🔒 Hardcoded | | Phase 2: Same |
| Weighted F1 | Computed in classification_report but not saved separately | ⚠️ Partial | Not extracted and saved | Phase 2: Extract `weighted avg` row from classification report; save to `metrics.json` |
| Per-class precision/recall/F1 | Computed in `classification_report()` but not saved or exposed | ⚠️ Partial | Not accessible via API; only printed to stdout during training | Phase 2: Parse classification report dict; save per-class metrics to `metrics.json` |
| Confusion matrix | Computed in `train_model.py`; hardcoded in `app.py` | 🔒 Hardcoded | Matrix served from hardcoded Python list, not from saved artifact | Phase 2: Save confusion matrix to `metrics.json`; load dynamically |
| ROC-AUC | Not computed | ❌ Missing | | Phase 3: Add `roc_auc_score` for binary case; include in `metrics.json` |
| PR-AUC | Not computed | ❌ Missing | | Phase 3: Add `average_precision_score`; include in `metrics.json` |
| Independent test set evaluation | `test_flows.csv` (52 samples) used as held-out set | ✅ Implemented | Small and controlled test set; not from an independent traffic scenario | Document limitation clearly |
| Validation set evaluation | 80/20 stratified split used during training | ✅ Implemented | Validation results printed to stdout but not saved | Phase 2: Save validation metrics alongside independent test metrics in `metrics.json` |
| Model comparison table | Not present | ❌ Missing | Only RF exists | Phase 3: After implementing SVM + NN + Hybrid, generate comparison table in EXPERIMENTS.md |

---

### 18. Detection Latency

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| ML inference latency measurement | Not measured | ❌ Missing | No timing around `pipeline.predict()` | Phase 2: Wrap prediction in `time.perf_counter()` calls; return `inference_latency_ms` in predict response; store per-prediction |
| End-to-end pipeline latency | Not measured | ❌ Missing | No timestamps for ingestion → inference → alert → storage | Phase 8: Record timestamps at each pipeline stage; compute end-to-end latency per event |
| Latency reported in milliseconds | Not reported | ❌ Missing | | Phase 2: Report latency in ms; expose average in `/insights/metrics` and `/health` |
| p50 / p95 / p99 latency | Not computed | ❌ Missing | | Phase 11: Compute percentile latencies from stored per-prediction latency values; expose via `/metrics` |
| Comparison to journal baseline (0.061s) | Not available | ❌ Missing | Journal reports 0.061s average detection latency on their hardware; cannot compare without measuring ours | Phase 11: Report actual measured latency; note hardware difference; do not claim to reproduce journal latency |

---

### 19. Class Imbalance Handling

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Awareness of class imbalance | `class_weight="balanced"` in RandomForestClassifier | ⚠️ Partial | Balancing applied but not documented or analyzed; actual class distribution of training data not logged | Phase 2: Log exact class distribution at training time; save to `metrics.json` |
| Stratified train/test split | `train_test_split(..., stratify=y_full)` | ✅ Implemented | Correctly stratified | No change needed |
| SMOTE or oversampling | Not implemented | ❌ Missing | Not applied; would require `imbalanced-learn` dependency | Phase 3: Evaluate whether SMOTE improves minority recall given the very small dataset; if helpful, add `imbalanced-learn>=0.11` to requirements |
| Threshold tuning | Not implemented | ❌ Missing | Default 0.5 probability threshold used implicitly by `predict()` | Phase 3: Evaluate threshold tuning on validation set; find optimal threshold for F1 or recall; document |
| Oversampling documentation | Not present | ❌ Missing | | Phase 4: Document class distribution and any balancing decisions in DATASET_DOCUMENTATION.md |
| Impact analysis | Not present | ❌ Missing | No ablation comparing balanced vs. unbalanced training | Phase 11: Run ablation: with vs. without `class_weight="balanced"`; record results |

---

### 20. Minority Attack Class Evaluation

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Per-class evaluation of minority attacks | Classification report computed during training (stdout only) | ⚠️ Partial | Only "probe" is a minority/attack class currently; per-class metrics not saved or exposed | Phase 2: Save per-class metrics to `metrics.json`; expose via API |
| Minority class recall specifically | Not tracked | ❌ Missing | | Phase 2: Track `probe_recall`, `probe_precision`, `probe_f1` as first-class metrics |
| Analysis of false negatives on attacks | Not present | ❌ Missing | Confusion matrix shows false negatives but they are hardcoded | Phase 2: Dynamic confusion matrix; compute false negative rate per class |
| Multi-class minority analysis | Not applicable | ❌ Missing | Binary only; DoS/R2L/U2R not present in dataset | Phase 5: Synthetic simulator can generate multi-class examples for evaluation; document that live multi-class data is unavailable |
| Journal baseline comparison for minority classes | Research paper reports 75.77% F1 on their dataset | N/A | Cannot compare directly — different dataset, different feature schema, different classes | Document clearly that direct metric comparison is not valid; present own metrics honestly |

---

### 21. Reproducibility

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Fixed random seed | `random_state=42` in RF and `train_test_split` | ✅ Implemented | Seeds not set globally (numpy, Python random not seeded) | Phase 3: Add `np.random.seed(42)` and `random.seed(42)` at top of training script |
| Dataset hash / version | Not present | ❌ Missing | No way to verify the dataset used for a given model artifact | Phase 2: Compute `md5` or `sha256` of training and test CSVs at training time; save to `metrics.json` |
| Preprocessing version | Not tracked | ❌ Missing | Feature schema is defined as a hardcoded list in multiple files with no version | Phase 2: Add `FEATURE_SCHEMA_VERSION = "v1"` constant; include in `metrics.json` |
| Reproducible experiment pipeline | `train_model.py` can be re-run to reproduce training | ⚠️ Partial | No `experiments/` directory; no structured output per run; no timestamped run artifacts | Phase 4: Create `experiments/` directory structure; save each run to `experiments/YYYY-MM-DD_HH-MM-SS/` |
| Exact requirements pinning | `requirements.txt` has no version pins (`flask`, not `flask==3.0.3`) | ⚠️ Partial | Unpinned dependencies can cause silent regressions | Phase 1: Pin all dependency versions in `requirements.txt` |
| README with exact reproduction steps | `README.md` exists with installation and run instructions | ✅ Implemented | Missing: Docker run instructions; experiment run instructions; dataset collection instructions | Phase 12: Update README.md with complete reproduction guide |

---

### 22. Experimental Comparison

| Journal Requirement | Existing Project | Status | Gap | Implementation |
|---|---|---|---|---|
| Baseline experiment | `train_model.py` produces one set of results | ⚠️ Partial | Results not saved to structured output; printed to stdout only | Phase 2: Save results to `experiments/baseline/metrics.json` |
| RF vs. SVM vs. NN vs. Hybrid comparison | Not present | ❌ Missing | Only RF implemented | Phase 3: Implement all models; Phase 11: Run full comparison |
| Experiment table (paper-quality) | Not present | ❌ Missing | | Phase 11: Generate comparison table in EXPERIMENTS.md with actual measured values |
| Ablation study | Not present | ❌ Missing | | Phase 11: At minimum: with vs. without class balancing; with vs. without rate feature clipping; single model vs. ensemble |
| No fabricated metrics | ❌ Currently violated | 🔒 Hardcoded | `/insights/metrics` and `/insights/confusion` return hardcoded values that may not reflect the currently loaded model | **Phase 2 is the highest priority fix** |
| Honest reporting of limitations | README.md documents key limitations | ✅ Implemented | PROJECT_AUDIT.md now also documents risks | Maintain — keep updating |

---

## Summary Scorecard

| Category | Journal Requirements | ✅ Implemented | ⚠️ Partial | 🔒 Hardcoded | ❌ Missing |
|---|---|---|---|---|---|
| Telemetry Ingestion | 4 | 2 | 2 | 0 | 0 |
| Streaming Layer | 7 | 0 | 0 | 0 | 7 |
| Feature Engineering | 5 | 3 | 2 | 0 | 0 |
| ML Inference | 5 | 2 | 0 | 0 | 3 |
| Random Forest | 4 | 2 | 2 | 0 | 0 |
| SVM | 4 | 0 | 0 | 0 | 4 |
| Neural Network | 4 | 0 | 0 | 0 | 4 |
| Ensemble / Hybrid | 5 | 0 | 0 | 0 | 5 |
| Alert Generation | 8 | 3 | 2 | 0 | 3 |
| Persistent Storage | 6 | 0 | 4 | 0 | 2 |
| Dashboard | 14 | 3 | 2 | 5 | 4 |
| Monitoring | 8 | 0 | 1 | 0 | 7 |
| Containerization | 7 | 0 | 0 | 0 | 7 |
| Kubernetes | 7 | 0 | 0 | 0 | 7 |
| Horizontal Scaling | 4 | 0 | 0 | 0 | 4 |
| Security | 9 | 3 | 2 | 0 | 4 |
| Model Evaluation | 13 | 2 | 3 | 5 | 3 |
| Detection Latency | 5 | 0 | 0 | 0 | 5 |
| Class Imbalance | 6 | 1 | 2 | 0 | 3 |
| Minority Class Eval | 5 | 0 | 1 | 0 | 4 |
| Reproducibility | 6 | 2 | 3 | 0 | 1 |
| Experimental Comparison | 6 | 1 | 1 | 1 | 3 |
| **TOTALS** | **142** | **24 (17%)** | **27 (19%)** | **11 (8%)** | **80 (56%)** |

---

## Critical Path (Must Fix Before Any Research Claims)

The following items are **research integrity issues** — they must be addressed before the project can be presented in any academic or professional context:

1. **Hardcoded metrics** — `/insights/metrics` and `/insights/confusion` return fabricated static values. Fix in Phase 2.
2. **Mock chart data** — `TrafficChart` and `ThreatDistribution` show completely fabricated data unrelated to the system. Fix in Phase 7.
3. **Wrong confusion matrix labels** — Insights page shows "Predicted Malicious" instead of "Predicted Probe". Fix in Phase 7.
4. **Missing scapy in requirements.txt** — The primary capture functionality silently fails on fresh install. Fix in Phase 1.
5. **SVM/NN in Settings dropdown but not implemented** — Creates false impression of capability. Fix in Phase 3 (implement) or Phase 1 (temporarily disable in UI).

---

*End of JOURNAL_TRACEABILITY.md*
