# DATASET CHANGELOG

**Project:** Cloud-RT-IDS  
**Document version:** 3.0  
**Date:** 2026-10-04

This document traces every deliberate change to the dataset since the project began.

---

## Version History

| Version | Date | Description | Rows (train) | Classes |
|---|---|---|---|---|
| v0 — NSL-KDD prototype | 2026-09 | Original NSL-KDD 41-feature prototype | 125,973 | 5 (normal + 4 attack types) |
| v1 — Live-flow binary | 2026-09 | Custom 27-feature Scapy capture on loopback | 55 | 2 (normal, probe) |
| v2 — Live-flow augmented | 2026-09 | Synthetic augmentation added dos/r2l/u2r | 565 | 5 |
| **v3 — CIC-IDS-2017** | **2026-10** | **Real network traffic, 2.83M rows** | **209,067** | **7** |

---

## Change 1 — NSL-KDD to Live-Flow Schema

**Type:** Breaking — complete feature schema replacement  
**Version:** v0 → v1

### What changed
Replaced the NSL-KDD 41-feature connection-level schema with a custom
27-feature bidirectional flow schema computed directly from raw packets.

### Why
NSL-KDD features (service field, 2-second window statistics, flag vocabulary)
cannot be computed from raw Scapy packet captures without a full IDS sensor.
The 27-feature schema is computable in real-time from any network interface.

### Impact
- Broke compatibility with NSL-KDD benchmark comparisons (intentional)
- Enabled genuine live capture capability
- Reduced class taxonomy to binary (normal/probe) due to capture constraints

---

## Change 2 — Synthetic Augmentation of Attack Classes

**Type:** Dataset expansion  
**Version:** v1 → v2  
**Script:** `backend/augment_dataset.py`

### What changed
Added 450 synthetic rows for three attack classes not collectable via
localhost loopback: `dos` (200 train/90 test), `r2l` (150/65), `u2r` (100/45).

### Why
The binary normal/probe model could not demonstrate multi-class detection.
Synthetic flows bridged the gap while real data was unavailable.

### Risk
Synthetic flows are generated from statistical profiles, not real traffic.
Model trained on synthetic attacks may not generalise to real attacks.
This was documented as a known limitation and treated as temporary.

### Resolution
Superseded by Change 3 (CIC-IDS-2017 real data).

---

## Change 3 — CIC-IDS-2017 Real Network Traffic

**Type:** Major upgrade — complete dataset replacement  
**Version:** v2 → v3  
**Date:** 2026-10-04  
**Script:** `backend/cicids_pipeline.py`

### What changed

| Dimension | Before (v2) | After (v3) |
|---|---|---|
| Data source | Synthetic (simulator.py) + 55 live Scapy flows | CIC-IDS-2017 real network captures |
| Training rows | 565 | 209,067 |
| Test rows | 252 | 52,267 |
| Classes | 5 (normal, probe, dos, r2l, u2r) | 7 (normal, dos, ddos, probe, r2l, web_attack, bot) |
| Class balance | Synthetic counts (100-200 per class) | Real distribution, capped at 50k/class |
| Data quality | No NaN/Inf (synthetic) | 551,562 rows cleaned from raw CIC source |
| Protocol values | tcp/udp/other (real) | tcp (all CIC flows) |
| source_port values | Real Scapy ports | 0 (not available in CIC) |

### Why
- Synthetic data produced unrealistically high accuracy (~99%) that didn't reflect real detection capability
- CIC-IDS-2017 is the most widely used real network intrusion benchmark
- 2.83M real flows enable statistically stable model evaluation
- 14 CIC attack subtypes collapse into 7 meaningful classes aligned with the project's taxonomy

### How
1. Downloaded `MachineLearningCSV.zip` from [UNB CIC-IDS-2017](https://www.unb.ca/cic/datasets/ids-2017.html)
2. Extracted 8 daily CSVs to `MachineLearningCSV/MachineLearningCVE/`
3. Ran `cicids_pipeline.py` — maps 79 CIC columns to 27 schema features, cleans data, balances classes, stratified 80/20 split
4. Removed all stale synthetic data and model artifacts
5. Retrained all 4 classifiers + IsolationForest anomaly model

### Expected impact
Model generalises to real network traffic patterns rather than synthetic distributions.
Per-class performance now reflects genuine detection difficulty.

### Actual impact (measured)

| Class | Before (synthetic) RF F1 | After (CIC) RF F1 |
|---|---|---|
| normal | 88.89% | 98.87% |
| probe | 94.74% | 99.93% |
| dos | 100% (synthetic) | 99.83% (real) |
| r2l | 100% (synthetic) | 99.80% (real) |
| bot | N/A | 74.48% (new class, small) |
| web_attack | N/A | 86.02% (new class, small) |
| ddos | N/A | 99.94% (new class) |

### Risks
- `bot` and `web_attack` have low training samples (1.5k–1.6k) → lower precision
- `source_port` and `protocol` carry no signal in CIC data (both set to constants)
- CIC-IDS-2017 is from 2017 — doesn't include modern attack techniques

---

## Change 4 — Linear SVM Replacing RBF SVM

**Type:** Algorithm change for scalability  
**Date:** 2026-10-04

### What changed
`SVC(kernel="rbf")` was replaced with `SGDClassifier(loss="modified_huber")`
wrapped in `CalibratedClassifierCV` to get probability outputs.

### Why
RBF SVM has O(n²) training complexity. At 167k training rows it would have
taken hours or days. SGD linear SVM trains in under 5 seconds.

### Impact
- Training time: hours → 4.6 seconds
- Test accuracy: ~99.6% (synthetic) → 93.03% (real, 7 classes)
- The lower accuracy on real data reflects genuine difficulty, not a regression

---

## Change 5 — IsolationForest on Real Normal Traffic

**Type:** Enhancement  
**Date:** 2026-10-04

### What changed
Retrained the IsolationForest anomaly model on 80,000 real normal flows
(previously trained on 55 synthetic normal flows).

### Before
- Normal training samples: 55 synthetic
- Anomaly detection rate on attacks: 100% (inflated — synthetic attacks are perfectly separated)

### After
- Normal training samples: 80,000 real
- Anomaly detection rate on attacks: 47.4%
- The 47.4% rate is honest — real attack traffic often has similar statistical
  properties to normal traffic (that's what makes intrusion detection hard)

---

## Stale Files Removed

The following files were removed as part of the v3 upgrade:

| File | Reason |
|---|---|
| `backend/data/KDDTrain+.txt` | NSL-KDD no longer used |
| `backend/data/KDDTest+.txt` | NSL-KDD no longer used |
| `backend/data/live_flows_unlabeled.csv` | Superseded |
| `backend/data/alerts.json` | Replaced by SQLite `ids.db` |
| `backend/data/prediction_history.json` | Replaced by SQLite `ids.db` |
| `backend/data/settings.json` | Replaced by SQLite `ids.db` |
| `backend/model/scaler.pkl` | Legacy artifact, baked into Pipeline |
| `backend/model/preprocessor.pkl` | Legacy artifact, baked into Pipeline |
| All `model_*.pkl` (old) | Retrained on CIC data |
| All `metrics_*.json` (old) | Regenerated from CIC training |

---

*End of DATASET_CHANGELOG.md*
