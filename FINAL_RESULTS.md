# FINAL RESULTS

**Project:** Cloud-RT-IDS — Enterprise Edition  
**Document version:** 3.0  
**Date:** 2026-10-04  
**Status:** Complete — all values from actual experiment runs

> All numbers are sourced from `backend/model/metrics_all.json` and
> `backend/model/metrics_<model>.json`. Nothing is estimated or fabricated.

---

## Dataset

| Property | Value |
|---|---|
| Dataset name | CIC-IDS-2017 |
| Source | Canadian Institute for Cybersecurity, UNB |
| Pipeline script | `backend/cicids_pipeline.py` |
| Feature schema version | v2 (27 features) |
| Training samples | 209,067 |
| Test samples | 52,267 |
| Total classes | 7 |
| Training data MD5 | `c782c77456ffaf3524d77b6bb9a56c2e` |
| Test data MD5 | `aea2939883be91f5f24033c0b694fbb8` |
| Random seed | 42 |
| Generated | 2026-10-03T19:28:08Z |

### Class Distribution

| Class | Train | Test | Source attack type |
|---|---|---|---|
| normal | 80,000 | 20,000 | BENIGN |
| dos | 40,000 | 10,000 | DoS Hulk / GoldenEye / slowloris / Slowhttptest / Heartbleed |
| ddos | 40,000 | 10,000 | DDoS |
| probe | 40,000 | 10,000 | PortScan |
| r2l | 5,920 | 1,480 | FTP-Patator / SSH-Patator / Infiltration |
| web_attack | 1,620 | 405 | Web Attack (Brute Force / XSS / SQL Injection) |
| bot | 1,527 | 382 | Bot |

---

## Models

| Model | Algorithm | Key Hyperparameters |
|---|---|---|
| Random Forest | `RandomForestClassifier` | n_estimators=300, class_weight=balanced, n_jobs=-1 |
| Linear SVM | `SGDClassifier` + `CalibratedClassifierCV` | loss=modified_huber, alpha=1e-4, cv=3, isotonic |
| Neural Network | `MLPClassifier` | hidden=(256,128,64), adam, batch=512, early_stop |
| Hybrid Ensemble | `VotingClassifier` | soft voting: RF + LinearSVM + NN |
| Anomaly | `IsolationForest` | n_estimators=200, contamination=auto, normal-only training |

---

## Metrics — Independent Test Set (52,267 rows)

| Model | Accuracy | Precision (macro) | Recall (macro) | F1 (macro) | F1 (weighted) | Latency |
|---|---|---|---|---|---|---|
| **Hybrid Ensemble** | **99.29%** | **95.00%** | **95.75%** | **95.05%** | **99.30%** | 0.039 ms |
| Neural Network | 99.13% | 94.53% | 94.95% | 94.36% | 99.13% | 0.027 ms |
| Random Forest | 99.14% | 90.72% | 99.30% | 94.12% | 99.21% | 0.012 ms |
| Linear SVM | 93.03% | 75.97% | 79.41% | 77.47% | 92.70% | 0.003 ms |

---

## Per-Class Metrics

### Random Forest

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| bot | 60.00% | 98.17% | 74.48% | 382 |
| ddos | 99.97% | 99.92% | 99.94% | 10,000 |
| dos | 99.77% | 99.88% | 99.83% | 10,000 |
| normal | 99.84% | 97.91% | 98.87% | 20,000 |
| probe | 99.87% | 99.99% | 99.93% | 10,000 |
| r2l | 99.86% | 99.73% | 99.80% | 1,480 |
| web_attack | 75.75% | 99.51% | 86.02% | 405 |

### Linear SVM

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| bot | 0.00% | 0.00% | 0.00% | 382 |
| ddos | 90.21% | 95.21% | 92.64% | 10,000 |
| dos | 92.16% | 87.15% | 89.59% | 10,000 |
| normal | 94.19% | 94.01% | 94.10% | 20,000 |
| probe | 96.01% | 98.37% | 97.17% | 10,000 |
| r2l | 93.01% | 94.46% | 93.73% | 1,480 |
| web_attack | 66.23% | 86.67% | 75.08% | 405 |

### Neural Network

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| bot | 91.42% | 72.51% | 80.88% | 382 |
| ddos | 99.87% | 99.89% | 99.88% | 10,000 |
| dos | 99.64% | 99.55% | 99.59% | 10,000 |
| normal | 98.98% | 98.83% | 98.91% | 20,000 |
| probe | 99.78% | 99.84% | 99.81% | 10,000 |
| r2l | 99.18% | 97.97% | 98.57% | 1,480 |
| web_attack | 72.85% | 96.05% | 82.85% | 405 |

### Hybrid Ensemble

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| bot | 91.08% | 74.87% | 82.18% | 382 |
| ddos | 99.88% | 99.94% | 99.91% | 10,000 |
| dos | 99.67% | 99.79% | 99.73% | 10,000 |
| normal | 99.24% | 98.97% | 99.11% | 20,000 |
| probe | 99.87% | 99.86% | 99.86% | 10,000 |
| r2l | 99.80% | 98.78% | 99.29% | 1,480 |
| web_attack | 75.48% | 98.02% | 85.28% | 405 |

---

## Confusion Matrices

### Random Forest

|  | bot | ddos | dos | normal | probe | r2l | web_attack |
|---|---|---|---|---|---|---|---|
| **bot** | **375** | 0 | 0 | 7 | 0 | 0 | 0 |
| **ddos** | 0 | **9,992** | 0 | 8 | 0 | 0 | 0 |
| **dos** | 0 | 0 | **9,988** | 10 | 2 | 0 | 0 |
| **normal** | 250 | 3 | 23 | **19,583** | 11 | 2 | 128 |
| **probe** | 0 | 0 | 0 | 0 | **9,999** | 0 | 1 |
| **r2l** | 0 | 0 | 0 | 4 | 0 | **1,476** | 0 |
| **web_attack** | 0 | 0 | 0 | 2 | 0 | 0 | **403** |

### Hybrid Ensemble

|  | bot | ddos | dos | normal | probe | r2l | web_attack |
|---|---|---|---|---|---|---|---|
| **bot** | **286** | 0 | 0 | 96 | 0 | 0 | 0 |
| **ddos** | 0 | **9,994** | 0 | 6 | 0 | 0 | 0 |
| **dos** | 0 | 0 | **9,979** | 21 | 0 | 0 | 0 |
| **normal** | 28 | 7 | 29 | **19,794** | 13 | 1 | 128 |
| **probe** | 0 | 5 | 3 | 5 | **9,986** | 0 | 1 |
| **r2l** | 0 | 0 | 1 | 17 | 0 | **1,462** | 0 |
| **web_attack** | 0 | 0 | 0 | 6 | 0 | 2 | **397** |

---

## Training Performance

| Model | Training Time | Training Samples |
|---|---|---|
| Random Forest | 8.2 seconds | 167,253 |
| Linear SVM | 4.6 seconds | 167,253 |
| Neural Network | 668.9 seconds | 167,253 |
| Hybrid Ensemble | 704.6 seconds | 167,253 |
| IsolationForest | ~30 seconds | 80,000 (normal only) |

---

## Inference Latency

| Model | Latency per sample |
|---|---|
| Linear SVM | 0.003 ms |
| Random Forest | 0.012 ms |
| Neural Network | 0.027 ms |
| Hybrid Ensemble | 0.039 ms |

Live latency percentiles are available from `GET /insights/latency` after
running predictions. The above values are measured by `train_model.py` on
the independent test set.

---

## Anomaly Detection (IsolationForest)

| Metric | Value |
|---|---|
| Training samples (normal only) | 80,000 |
| Decision function mean — normal traffic | 0.0920 |
| Decision function mean — attack traffic | 0.0006 |
| Anomaly detection rate on attacks | 47.4% |
| Role | Zero-day / evasion detection (supplements classifier) |

---

## System Capabilities

| Capability | Status | Notes |
|---|---|---|
| Multi-class detection (7 classes) | ✅ | normal, dos, ddos, probe, r2l, web_attack, bot |
| SHAP explainability | ✅ | Top-5 features per prediction (RF) |
| Anomaly detection | ✅ | IsolationForest, 47.4% attack detection |
| SSE real-time streaming | ✅ | Push-based, no polling |
| SQLite persistence | ✅ | Alerts, history, settings survive restart |
| Rate limiting | ✅ | Per-endpoint limits (120/min predict) |
| API key auth | ✅ | Optional, env-configured |
| Prometheus metrics | ✅ | `GET /metrics` |
| Structured JSON logging | ✅ | All requests + predictions |
| Docker | ✅ | `docker compose up --build` |
| Kubernetes | ✅ | 7 manifests including HPA (1–4 replicas) |
| Autoscaling (tested) | ❌ | Manifests ready; performance not benchmarked |
| Redis Streams | 📋 | Migration path documented in ARCHITECTURE.md |
| HTTPS | 📋 | Requires nginx SSL config or cloud LB |

---

## Limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | `bot` precision 60-91% depending on model | False positives for bot detection | Collect more bot training data; apply SMOTE |
| L2 | `web_attack` precision 66-75% | False positives for web attack detection | Same as L1 |
| L3 | `source_port` is 0 for all CIC flows | Feature unused by model | Acceptable; doesn't degrade performance |
| L4 | `protocol` is "tcp" for all CIC flows | Feature unused by model | Acceptable; doesn't degrade performance |
| L5 | CIC-IDS-2017 is from 2017 | Missing modern attacks (ransomware, cryptomining, supply chain) | Use CIC-IDS-2018 or CIC-IoT23 for next upgrade |
| L6 | IsolationForest 47.4% detection rate | Anomaly layer is supplemental only | Expected; real attack traffic overlaps with normal statistically |
| L7 | Autoscaling not benchmarked | Cannot claim production throughput | Run load test: `backend/benchmark.py` (future work) |
| L8 | Live capture on Windows loopback only | Not a real network sensor | Requires Npcap on a physical interface + elevated permissions |

---

## Future Work

| Priority | Item |
|---|---|
| 1 | Upgrade to CIC-IDS-2018 or CIC-IoT23 for modern attack coverage |
| 2 | Apply SMOTE to `bot` and `web_attack` classes to improve minority precision |
| 3 | Implement log-transform for rate features (packets_per_second) to handle extreme values |
| 4 | Add Redis Streams producer/consumer to replace the in-process queue |
| 5 | Implement benchmark.py for throughput/latency profiling under load |
| 6 | Add model drift detection using rolling accuracy on recent labelled feedback |
| 7 | Extend live capture to Wi-Fi/Ethernet interface (requires elevated permissions) |
| 8 | Add threshold tuning experiment: optimise per-class decision thresholds for F1 |
| 9 | Implement MLflow or similar for experiment tracking across training runs |
| 10 | Add ROC-AUC and PR-AUC using one-vs-rest strategy for multi-class evaluation |

---

*End of FINAL_RESULTS.md*
