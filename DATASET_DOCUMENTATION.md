# DATASET DOCUMENTATION

**Project:** Cloud-RT-IDS  
**Document version:** 3.0  
**Date:** 2026-10-04  
**Schema version:** v2  

---

## 1. Dataset Origin

The active training dataset is derived from the **CIC-IDS-2017** benchmark
dataset, produced by the Canadian Institute for Cybersecurity at the
University of New Brunswick.

> Sharafaldin, I., Lashkari, A.H., and Ghorbani, A.A. (2018).
> "Toward Generating a New Intrusion Detection Dataset and Intrusion
> Traffic Characterization." *ICISSP 2018*.

The raw CIC-IDS-2017 CSVs were processed through `backend/cicids_pipeline.py`,
which maps 79 CICFlowMeter features to the project's 27-feature live-flow
schema, normalises labels, removes duplicates and NaN rows, and produces
a balanced, stratified train/test split.

**Previous dataset history** is documented in `DATASET_CHANGELOG.md`.

---

## 2. Dataset Files

| File | Role | Rows | MD5 |
|---|---|---|---|
| `backend/data/live_flows.csv` | Training set | 209,067 | `c782c77456ffaf3524d77b6bb9a56c2e` |
| `backend/data/test_flows.csv` | Independent test (held-out) | 52,267 | `aea2939883be91f5f24033c0b694fbb8` |
| `MachineLearningCSV/MachineLearningCVE/` | CIC-IDS-2017 raw source | 2,830,743 | — |

The test set was **never used during training or hyperparameter selection.**

---

## 3. Class Distribution

### Training set (209,067 rows)

| Class | Rows | % | CIC-IDS-2017 source |
|---|---|---|---|
| `normal` | 80,000 | 38.3% | BENIGN (sampled from 2,271,320) |
| `dos` | 40,000 | 19.1% | DoS Hulk / GoldenEye / slowloris / Slowhttptest / Heartbleed |
| `ddos` | 40,000 | 19.1% | DDoS (sampled from 128,025) |
| `probe` | 40,000 | 19.1% | PortScan (sampled from 158,804) |
| `r2l` | 5,920 | 2.8% | FTP-Patator / SSH-Patator / Infiltration (all kept) |
| `web_attack` | 1,620 | 0.8% | Web Attack — Brute Force / XSS / SQL Injection (all kept) |
| `bot` | 1,527 | 0.7% | Bot (all kept) |

### Independent test set (52,267 rows)

| Class | Rows | % |
|---|---|---|
| `normal` | 20,000 | 38.3% |
| `dos` | 10,000 | 19.1% |
| `ddos` | 10,000 | 19.1% |
| `probe` | 10,000 | 19.1% |
| `r2l` | 1,480 | 2.8% |
| `web_attack` | 405 | 0.8% |
| `bot` | 382 | 0.7% |

The train/test split is **stratified** — each class proportion is preserved.

---

## 4. Feature Schema — Version 2

27 features derived from a bidirectional network flow.

| # | Feature | Type | Unit | CIC-IDS-2017 Source | Notes |
|---|---|---|---|---|---|
| 1 | `duration` | float | seconds | `Flow Duration` ÷ 1,000,000 | CIC stores µs → converted to s |
| 2 | `source_port` | int | — | Not in CIC | Set to 0 for CIC data |
| 3 | `destination_port` | int | — | `Destination Port` | Direct map |
| 4 | `forward_packets` | int | count | `Total Fwd Packets` | Direct map |
| 5 | `backward_packets` | int | count | `Total Backward Packets` | Direct map |
| 6 | `forward_bytes` | int | bytes | `Total Length of Fwd Packets` | Direct map |
| 7 | `backward_bytes` | int | bytes | `Total Length of Bwd Packets` | Direct map |
| 8 | `total_packets` | int | count | Derived | fwd + bwd |
| 9 | `total_bytes` | int | bytes | Derived | fwd_bytes + bwd_bytes |
| 10 | `packets_per_second` | float | pkt/s | `Flow Packets/s` | Direct map |
| 11 | `bytes_per_second` | float | B/s | `Flow Bytes/s` | Direct map |
| 12 | `mean_packet_size` | float | bytes | `Packet Length Mean` | Direct map |
| 13 | `min_packet_size` | float | bytes | `Min Packet Length` | Direct map |
| 14 | `max_packet_size` | float | bytes | `Max Packet Length` | Direct map |
| 15 | `packet_size_std` | float | bytes | `Packet Length Std` | Direct map |
| 16 | `syn_count` | int | count | `SYN Flag Count` | Direct map |
| 17 | `ack_count` | int | count | `ACK Flag Count` | Direct map |
| 18 | `fin_count` | int | count | `FIN Flag Count` | Direct map |
| 19 | `rst_count` | int | count | `RST Flag Count` | Direct map |
| 20 | `psh_count` | int | count | `PSH Flag Count` | Direct map |
| 21 | `forward_packet_ratio` | float | 0–1 | Derived | fwd_pkts / total_pkts |
| 22 | `backward_packet_ratio` | float | 0–1 | Derived | bwd_pkts / total_pkts |
| 23 | `forward_byte_ratio` | float | 0–1 | Derived | fwd_bytes / total_bytes |
| 24 | `backward_byte_ratio` | float | 0–1 | Derived | bwd_bytes / total_bytes |
| 25 | `syn_ratio` | float | 0–1 | Derived | syn_count / total_pkts |
| 26 | `rst_ratio` | float | 0–1 | Derived | rst_count / total_pkts |
| 27 | `protocol` | str | — | Not in CIC | Set to `"tcp"` for CIC data |

**Target column:** `label`  
**Allowed label values:** `normal`, `dos`, `ddos`, `probe`, `r2l`, `web_attack`, `bot`

---

## 5. CIC-IDS-2017 → Label Mapping

| Raw CIC label | Mapped label | Rationale |
|---|---|---|
| BENIGN | `normal` | Legitimate traffic |
| DoS Hulk | `dos` | Application-layer flooding |
| DoS GoldenEye | `dos` | HTTP keep-alive flooding |
| DoS slowloris | `dos` | Low-and-slow connection exhaustion |
| DoS Slowhttptest | `dos` | Slow HTTP POST flooding |
| Heartbleed | `dos` | OpenSSL exploit causing service crash |
| DDoS | `ddos` | Distributed flooding — distinct from single-source DoS |
| PortScan | `probe` | Service/host enumeration |
| FTP-Patator | `r2l` | Remote brute-force credential attack |
| SSH-Patator | `r2l` | Remote brute-force credential attack |
| Infiltration | `r2l` | Remote-to-local exploitation |
| Bot | `bot` | Botnet C&C beaconing |
| Web Attack – Brute Force | `web_attack` | HTTP form brute force |
| Web Attack – XSS | `web_attack` | Cross-site scripting injection |
| Web Attack – Sql Injection | `web_attack` | SQL injection |

---

## 6. Data Cleaning Steps

The CIC-IDS-2017 dataset has known quality issues. The pipeline applies:

1. **Infinity replacement** — `np.inf` and `-np.inf` replaced with `NaN`
2. **NaN row removal** — rows with NaN in any numeric feature are dropped
3. **Duplicate removal** — 549,968 exact duplicate flows removed
4. **Label normalisation** — mapped via `LABEL_MAP` in `cicids_pipeline.py`
5. **Duration unit conversion** — CIC stores microseconds; divided by 1,000,000
6. **Ratio derivation** — 6 ratio features computed; zero-division handled by filling 0.0
7. **Balanced sampling** — majority class capped to prevent model bias

After cleaning: **0 NaN rows, 0 Infinity values** in both train and test sets.

---

## 7. Preprocessing Pipeline

All preprocessing is embedded inside the scikit-learn `Pipeline` object.
The same transformations are applied identically at training and inference time.

```
Input DataFrame (27 features)
          │
          ▼
ColumnTransformer
  ├── StandardScaler       → 26 numeric features
  └── OneHotEncoder        → 1 categorical (protocol)
      handle_unknown="ignore"
          │
          ▼
ML Estimator (RF / LinearSVM / MLP / VotingClassifier)
```

The scaler is **fit on the training split only** (`X_train`).
It is never re-fit on validation or test data — no data leakage.

---

## 8. Train / Test Methodology

1. Load `live_flows.csv` (training) and `test_flows.csv` (independent test).
2. Normalise labels to lowercase, drop NaN labels and invalid numeric rows.
3. Validate all test labels are present in training set.
4. **Stratified 80/20 split** of training data for validation:
   - `X_train` / `y_train` — 80% for fitting
   - `X_val` / `y_val` — 20% for validation metrics
5. Fit all four pipelines on `X_train`, evaluate on `X_val`.
6. **Refit** each pipeline on `X_full` (full training set) for final artifact.
7. Evaluate on `X_independent` — this is the primary reported metric.

The independent test set (`test_flows.csv`) is **never used during fitting,
hyperparameter selection, or model comparison selection.**

---

## 9. Reproducibility

| Control | Value |
|---|---|
| Random seed | 42 (all estimators, `train_test_split`, pipeline seed) |
| `numpy.random.seed` | 42 |
| `random.seed` | 42 |
| Training data MD5 | `c782c77456ffaf3524d77b6bb9a56c2e` |
| Test data MD5 | `aea2939883be91f5f24033c0b694fbb8` |
| Feature schema version | v2 (stored in `metrics_all.json`) |
| Pipeline parameters | Stored in `metrics_<model>.json` → `hyperparameters` |

To reproduce from scratch:

```bash
python backend/cicids_pipeline.py          # ~5 min, 2.83M rows
python backend/model/train_model.py        # ~30 min
python backend/train_anomaly.py            # ~2 min
```

---

## 10. Known Limitations

| Limitation | Impact | Status |
|---|---|---|
| `source_port` is 0 for all CIC flows | Feature carries no signal for this dataset | Documented; model ignores it via tree splits |
| `protocol` is "tcp" for all CIC flows | Feature carries no signal for this dataset | Documented; model ignores it |
| `bot` class: only 1,527 training rows | Low precision (60%) — model confuses bot with normal | Collect more bot traffic or use SMOTE |
| `web_attack` class: only 1,620 training rows | Lower precision (75.75%) | Same mitigation as bot |
| CIC data is from 2017 | Doesn't include modern attack vectors (ransomware, cryptomining, etc.) | Use a more recent dataset for production |
| Duration in CIC sometimes zero | After µs→s conversion some flows have duration=0 | Floored to 0.001 s in pipeline |

---

*End of DATASET_DOCUMENTATION.md*
