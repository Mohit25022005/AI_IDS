# DATASET DOCUMENTATION

**Project:** Cloud-RT-IDS  
**Document version:** 1.0  
**Date:** 2026-09-23  
**Schema version:** v2

---

## 1. Dataset Origin

The current dataset is **not** a download of the original NSL-KDD dataset.  
It is a purpose-built dataset of **live, directly-captured network flows** collected
on the development machine using Scapy on the Windows Npcap loopback interface
(`\Device\NPF_Loopback`).

The NSL-KDD files (`KDDTrain+.txt`, `KDDTest+.txt`) are retained in
`backend/data/` as **historical reference material only**. They are not loaded by
any part of the current ML pipeline.

---

## 2. Feature Schema — Version 2

The schema contains **27 features** derived from a bidirectional network flow.  
All features are computed from raw packets captured per flow; no external enrichment
is applied.

| # | Feature | Type | Unit | Description |
|---|---|---|---|---|
| 1 | `duration` | float | seconds | Flow duration (floored at 0.001 s to prevent rate explosion) |
| 2 | `source_port` | int | — | Source TCP/UDP port |
| 3 | `destination_port` | int | — | Destination TCP/UDP port |
| 4 | `forward_packets` | int | count | Packets travelling src → dst |
| 5 | `backward_packets` | int | count | Packets travelling dst → src |
| 6 | `forward_bytes` | int | bytes | Bytes travelling src → dst |
| 7 | `backward_bytes` | int | bytes | Bytes travelling dst → src |
| 8 | `total_packets` | int | count | forward_packets + backward_packets |
| 9 | `total_bytes` | int | bytes | forward_bytes + backward_bytes |
| 10 | `packets_per_second` | float | pkt/s | total_packets / duration |
| 11 | `bytes_per_second` | float | B/s | total_bytes / duration |
| 12 | `mean_packet_size` | float | bytes | total_bytes / total_packets |
| 13 | `min_packet_size` | float | bytes | Minimum observed packet length |
| 14 | `max_packet_size` | float | bytes | Maximum observed packet length |
| 15 | `packet_size_std` | float | bytes | Std dev of packet lengths |
| 16 | `syn_count` | int | count | SYN-only flag packets (SYN=1, ACK=0) |
| 17 | `ack_count` | int | count | Packets with ACK flag set |
| 18 | `fin_count` | int | count | Packets with FIN flag set |
| 19 | `rst_count` | int | count | Packets with RST flag set |
| 20 | `psh_count` | int | count | Packets with PSH flag set |
| 21 | `forward_packet_ratio` | float | 0–1 | forward_packets / total_packets |
| 22 | `backward_packet_ratio` | float | 0–1 | backward_packets / total_packets |
| 23 | `forward_byte_ratio` | float | 0–1 | forward_bytes / total_bytes |
| 24 | `backward_byte_ratio` | float | 0–1 | backward_bytes / total_bytes |
| 25 | `syn_ratio` | float | 0–1 | syn_count / total_packets |
| 26 | `rst_ratio` | float | 0–1 | rst_count / total_packets |
| 27 | `protocol` | str | — | "tcp" \| "udp" \| "other" |

**Target column:** `label`  
**Allowed label values:** `normal`, `probe`  
*(Labels are normalised to lowercase at write time in `url_kdd.py`.)*

---

## 3. Label Taxonomy

| Label | Meaning |
|---|---|
| `normal` | Legitimate background or application traffic captured on the loopback interface |
| `probe` | Controlled port-scan traffic directed at `127.0.0.1`, ports 8000–8049 |

No other classes are currently present in the collected dataset.  
The synthetic simulator (`backend/simulator.py`) can generate additional classes
(`dos`, `r2l`, `u2r`) for model testing, but those are **not** part of the
ground-truth collected dataset.

---

## 4. Dataset Files

| File | Role | Samples | Notes |
|---|---|---|---|
| `backend/data/live_flows.csv` | Training data | ~115 rows | Labeled; cleaned by `clean_dataset.py` |
| `backend/data/test_flows.csv` | Independent test set | ~52 rows | Labeled; **never used during training** |
| `backend/data/live_flows_unlabeled.csv` | Archived unlabeled captures | varies | Separated by `clean_dataset.py`; not used in ML |
| `backend/data/KDDTrain+.txt` | Legacy reference | 125,973 rows | NSL-KDD format; **not used** |
| `backend/data/KDDTest+.txt` | Legacy reference | 22,544 rows | NSL-KDD format; **not used** |

---

## 5. Class Distribution

Exact counts depend on the current state of `live_flows.csv` and
`test_flows.csv`. Run the following to inspect:

```bash
python backend/inspect_dataset.py
```

Or check `backend/model/metrics_all.json` after training, which records:
```json
"class_distribution_train": { "normal": N, "probe": M },
"class_distribution_test":  { "normal": N, "probe": M }
```

**Known imbalance note:** the training set is small (~115 samples) and the
probe samples come from a single repetitive capture session. The Random Forest
uses `class_weight="balanced"` to compensate.

---

## 6. Preprocessing Pipeline

All preprocessing is **embedded inside the scikit-learn `Pipeline` object** saved
as `model_<name>.pkl`. The same transformations are applied identically at
training time and inference time — there is no risk of train/test leakage from
this design.

```
Input DataFrame (27 features)
          │
          ▼
ColumnTransformer
  ├── StandardScaler       → 26 numeric features
  └── OneHotEncoder        → 1 categorical feature (protocol)
      (handle_unknown="ignore")
          │
          ▼
ML Estimator (RF / SVM / MLP / VotingClassifier)
```

**Scaler fit:** fitted on the training split only (`X_train`).  
The fitted preprocessor is part of the pipeline — it is never re-fit on
validation or test data.

---

## 7. Train / Test Methodology

1. Load `live_flows.csv` (training) and `test_flows.csv` (independent test).
2. Normalize labels to lowercase; drop rows with NaN labels or non-numeric features.
3. Validate that all test labels exist in the training label set.
4. Stratified 80/20 split of training data for validation:
   - `X_train` / `y_train` — 80 % for fitting
   - `X_val` / `y_val` — 20 % for validation metrics
5. Fit all four pipelines on `X_train`.
6. **Refit** each pipeline on the full training set (`X_full`) for the final artifact.
7. Evaluate on `X_independent` / `y_independent` — this is the primary reported metric.

**The independent test set is never used during fitting or hyperparameter selection.**

---

## 8. Reproducibility

All experiments use:
- `random_state=42` in all estimators and `train_test_split`
- `numpy.random.seed(42)` and `random.seed(42)` at script start
- Dataset MD5 hashes recorded in `metrics_all.json`
- Feature schema version tag `v2` embedded in all metrics files

To reproduce from scratch:
```bash
# 1 – ensure live_flows.csv and test_flows.csv are in backend/data/
# 2 – activate venv and install dependencies
pip install -r backend/requirements.txt
# 3 – train all models
python backend/model/train_model.py
# 4 – verify metrics
cat backend/model/metrics_all.json
```

---

## 9. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Very small training set (~115 samples) | High variance in metrics; numbers are not statistically stable | Collect more diverse traffic sessions |
| Probe traffic is highly uniform (single port-scan pattern) | Model may learn port-number shortcuts rather than behaviour | Vary port ranges, timing, and packet sizes in future captures |
| Short-duration flows produce extreme rate values | Can distort StandardScaler statistics | Duration floored at 1 ms; consider log-transform in future schema v3 |
| Loopback-only capture | Not equivalent to real network monitoring | Extend to Wi-Fi / Ethernet adapter in future work |
| Binary classification only | Cannot detect DoS, R2L, U2R in live capture | Requires physical or virtual adversarial traffic generation |
| Test set is also loopback-based | Independent test may share similar distribution to training | Use genuinely separate capture sessions on different days |

---

## 10. Data Collection Workflow

```
Live traffic / controlled probe
          │
          ▼
Scapy sniff on \Device\NPF_Loopback
          │
          ▼
capture_flows()  →  [NetworkFlow, …]
          │
          ▼
build_feature_vector(flow)  →  27-feature dict
          │
          ▼
save_flows_to_csv(flows, label="normal"|"probe")
          │
          ▼
live_flows.csv  (appended, header written once)
          │
          ▼
clean_dataset.py  (removes unlabeled; verifies probe ports)
          │
          ▼
Cleaned live_flows.csv  +  live_flows_unlabeled.csv (archived)
          │
          ▼
train_model.py  →  model artifacts + metrics JSONs
```

---

*End of DATASET_DOCUMENTATION.md*
