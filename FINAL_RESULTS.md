# FINAL RESULTS

**Project:** Cloud-RT-IDS  
**Document version:** 1.0  
**Date:** 2026-09-23  
**Status:** Template — populate by running `train_model.py` and recording actual values

> **Research Integrity Notice**  
> Every table in this document must be filled with values obtained from
> actual experimental runs.  The placeholder `—` must not be replaced with
> fabricated or copied numbers.  Use `backend/model/metrics_all.json`
> as the authoritative source after training.

---

## Dataset

| Property | Value |
|---|---|
| Original dataset | NSL-KDD (retained as reference only — not used) |
| Active dataset | Custom 27-feature live network flow dataset |
| Feature schema version | v2 |
| Collection method | Scapy live capture on Windows NPF_Loopback |
| Training file | `backend/data/live_flows.csv` |
| Test file | `backend/data/test_flows.csv` |
| Training samples | *from metrics_all.json: n_train_samples* |
| Test samples | *from metrics_all.json: n_test_samples* |
| Number of features | 27 |
| Target classes | normal, probe |
| Training class distribution | *from metrics_all.json: class_distribution_train* |
| Test class distribution | *from metrics_all.json: class_distribution_test* |
| Training dataset MD5 | *from metrics_all.json: train_dataset_md5* |
| Test dataset MD5 | *from metrics_all.json: test_dataset_md5* |
| Random seed | 42 |

---

## Models

| Model | Algorithm | Key Hyperparameters |
|---|---|---|
| Random Forest | `RandomForestClassifier` | n_estimators=300, class_weight=balanced |
| SVM | `SVC` | kernel=rbf, C=10.0, gamma=scale, probability=True |
| Neural Network | `MLPClassifier` | hidden=(128,64,32), adam, early_stopping=True |
| Hybrid | `VotingClassifier` | soft voting over [RF, SVM, NN] |

---

## Metrics — Independent Test Set

> Source: `backend/model/metrics_all.json` → `model_comparison`  
> All values measured on `test_flows.csv` which was **never used during training**.

| Model | Accuracy | Precision (macro) | Recall (macro) | F1 (macro) | F1 (weighted) | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|---|---|
| Random Forest | — | — | — | — | — | — | — |
| SVM | — | — | — | — | — | — | — |
| Neural Network | — | — | — | — | — | — | — |
| Hybrid Ensemble | — | — | — | — | — | — | — |

### Per-class Metrics — Random Forest

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | — | — | — | — |
| probe | — | — | — | — |

### Per-class Metrics — SVM

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | — | — | — | — |
| probe | — | — | — | — |

### Per-class Metrics — Neural Network

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | — | — | — | — |
| probe | — | — | — | — |

### Per-class Metrics — Hybrid

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | — | — | — | — |
| probe | — | — | — | — |

---

## Confusion Matrices

> Populate from `backend/model/metrics_<name>.json` →
> `independent_test.confusion_matrix`

### Random Forest

```
                  Predicted Normal   Predicted Probe
Actual Normal          —                  —
Actual Probe           —                  —
```

### SVM

```
                  Predicted Normal   Predicted Probe
Actual Normal          —                  —
Actual Probe           —                  —
```

### Neural Network

```
                  Predicted Normal   Predicted Probe
Actual Normal          —                  —
Actual Probe           —                  —
```

### Hybrid Ensemble

```
                  Predicted Normal   Predicted Probe
Actual Normal          —                  —
Actual Probe           —                  —
```

---

## Latency

| Model | Training Time (s) | Inference Latency (ms/sample) |
|---|---|---|
| Random Forest | — | — |
| SVM | — | — |
| Neural Network | — | — |
| Hybrid Ensemble | — | — |

| Percentile | Value (ms) |
|---|---|
| Average | — |
| p50 | — |
| p95 | — |
| p99 | — |

> Source: `backend/model/metrics_<name>.json` →
> `test_inference_latency_ms_per_sample`  
> and live values from `GET /insights/latency`

---

## System Performance

| Metric | Value | Notes |
|---|---|---|
| Events/sec (single-threaded) | — | Run `python backend/benchmark.py` |
| p50 latency (ms) | — | From `/insights/latency` |
| p95 latency (ms) | — | From `/insights/latency` |
| p99 latency (ms) | — | From `/insights/latency` |
| Max history size | 10,000 events | Configurable via `IDS_MAX_HISTORY` |
| Alert storage | JSON file | Survives restart |
| Model reload time | — | Measured via `/model/reload` |

---

## Cloud Readiness

| Capability | Status | Notes |
|---|---|---|
| Docker (backend) | ✅ | `docker/Dockerfile.backend` |
| Docker (frontend) | ✅ | `docker/Dockerfile.frontend` (multi-stage) |
| docker-compose | ✅ | `docker-compose.yml` |
| Kubernetes Deployment | ✅ | `k8s/deployment-backend.yaml` |
| Kubernetes Service | ✅ | ClusterIP (backend) + NodePort (frontend) |
| HorizontalPodAutoscaler | ✅ | 1–4 replicas, CPU 70% threshold |
| Health endpoint | ✅ | `GET /health` |
| Prometheus metrics | ✅ | `GET /metrics` |
| Structured logging | ✅ | JSON format, all requests + predictions |
| Environment-based config | ✅ | `.env.example` provided |
| API authentication | ✅ | Optional `X-API-Key` via `IDS_API_KEY` |
| CORS restriction | ✅ | Configurable `IDS_CORS_ORIGINS` |
| Streaming (Kafka/Redis) | 📋 | Migration path documented in `ARCHITECTURE.md` |
| Autoscaling tested | ❌ | Not benchmarked on local hardware |
| HTTPS | 📋 | Documented; requires nginx SSL config |

---

## Limitations

The following limitations must be stated whenever results from this project
are discussed in a research context:

| # | Limitation | Impact |
|---|---|---|
| L1 | Training set is ~115 samples | Metrics have high variance; not statistically stable |
| L2 | Test set is ~52 samples | Insufficient for robust held-out evaluation |
| L3 | Probe traffic is highly uniform (one port-scan pattern) | Accuracy inflated; model may rely on port-number shortcuts |
| L4 | All data captured on loopback interface | Not equivalent to real network IDS monitoring |
| L5 | Binary classification only (normal/probe) | Cannot detect DoS, R2L, U2R in live traffic |
| L6 | No multi-class ground-truth live data | Synthetic simulator fills the gap but is not real traffic |
| L7 | Autoscaling not benchmarked | Cannot claim cloud performance without measurement |
| L8 | Detection latency not independently validated | Journal's 0.061 s baseline is on different hardware/dataset |
| L9 | Settings lost on restart prior to Phase 1 | Fixed: settings.json now persists |
| L10 | Metrics were hardcoded prior to Phase 2 | Fixed: all metrics now loaded from metrics_*.json |

---

## Future Work

| Priority | Item |
|---|---|
| 1 | Collect more diverse training data (multiple capture sessions, different times of day) |
| 2 | Extend probe capture to varied port ranges and timing patterns |
| 3 | Add DoS traffic generation (TCP SYN flood against local test server) for labeled data |
| 4 | Replace JSON file storage with SQLite for indexed querying |
| 5 | Add Redis Streams producer/consumer to decouple capture from inference |
| 6 | Implement log-transform for rate features (packets_per_second, bytes_per_second) |
| 7 | Add SMOTE evaluation on larger dataset once available |
| 8 | Add threshold tuning experiment on validation set |
| 9 | Implement benchmark.py for throughput and latency profiling |
| 10 | Evaluate on a second independent capture session (different day/conditions) |
| 11 | Extend to multi-class classification once DoS/R2L/U2R ground-truth data is collected |
| 12 | Add model drift detection using rolling accuracy on recent predictions |

---

*End of FINAL_RESULTS.md*
