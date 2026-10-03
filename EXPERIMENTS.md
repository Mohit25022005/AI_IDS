# EXPERIMENTS

**Project:** Cloud-RT-IDS  
**Document version:** 1.0  
**Date:** 2026-09-23  
**Status:** Template — populate with actual values after running `train_model.py`

---

## How to Run Experiments

```bash
# 1. Activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Train all four models + save metrics
python backend/model/train_model.py

# 4. Results are saved to:
#    backend/model/metrics_all.json          — comparison table
#    backend/model/metrics_random_forest.json
#    backend/model/metrics_svm.json
#    backend/model/metrics_neural_network.json
#    backend/model/metrics_hybrid.json
#    experiments/baseline/<timestamp>/       — archived run

# 5. View per-class and confusion matrix for any model:
python -c "
import json
with open('backend/model/metrics_random_forest.json') as f:
    m = json.load(f)
print(json.dumps(m['independent_test'], indent=2))
"
```

---

## Experiment E1 — Baseline (Random Forest, Original Dataset)

**Purpose:** Establish the baseline performance of the single RF model
on the current live-flow dataset before adding SVM / NN / Hybrid.

**Dataset:** `live_flows.csv` + `test_flows.csv` (see `metrics_all.json`)

| Property | Value |
|---|---|
| Feature schema version | v2 |
| Random seed | 42 |
| Training samples | *run train_model.py to populate* |
| Test samples | *run train_model.py to populate* |
| Classes | normal, probe |
| Training timestamp | *auto-recorded* |
| Dataset MD5 (train) | *auto-recorded* |
| Dataset MD5 (test) | *auto-recorded* |

### E1 Results

> Replace the placeholder rows below with values from
> `backend/model/metrics_random_forest.json` → `independent_test`.

| Metric | Value |
|---|---|
| Accuracy | — |
| Precision (macro) | — |
| Recall (macro) | — |
| F1 (macro) | — |
| F1 (weighted) | — |
| ROC-AUC | — |
| PR-AUC | — |
| Inference latency (ms/sample) | — |
| Training time (s) | — |

#### Per-class metrics

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | — | — | — | — |
| probe  | — | — | — | — |

#### Confusion Matrix

```
                  Predicted Normal   Predicted Probe
Actual Normal          —                  —
Actual Probe           —                  —
```

---

## Experiment E2 — SVM

**Purpose:** Compare SVM (RBF kernel) against RF baseline on identical
train/test split.

| Property | Value |
|---|---|
| Kernel | rbf |
| C | 10.0 |
| gamma | scale |
| class_weight | balanced |
| Random seed | 42 |

### E2 Results

| Metric | Value |
|---|---|
| Accuracy | — |
| Precision (macro) | — |
| Recall (macro) | — |
| F1 (macro) | — |
| ROC-AUC | — |
| Inference latency (ms/sample) | — |

---

## Experiment E3 — Neural Network (MLP)

**Purpose:** Compare MLP against RF and SVM baselines.

| Property | Value |
|---|---|
| Architecture | 128 → 64 → 32 |
| Activation | ReLU |
| Solver | Adam |
| alpha (L2) | 1e-4 |
| Early stopping | Yes |
| Random seed | 42 |

### E3 Results

| Metric | Value |
|---|---|
| Accuracy | — |
| Precision (macro) | — |
| Recall (macro) | — |
| F1 (macro) | — |
| ROC-AUC | — |
| Inference latency (ms/sample) | — |

---

## Experiment E4 — Hybrid Ensemble (Soft Voting: RF + SVM + NN)

**Purpose:** Determine whether ensemble improves over any single model.

| Property | Value |
|---|---|
| Strategy | Soft voting (average class probabilities) |
| Estimators | RF (300 trees) + SVM (rbf) + MLP (128-64-32) |
| Random seed | 42 |

### E4 Results

| Metric | Value |
|---|---|
| Accuracy | — |
| Precision (macro) | — |
| Recall (macro) | — |
| F1 (macro) | — |
| ROC-AUC | — |
| Inference latency (ms/sample) | — |

---

## Experiment Comparison Table (E1–E4)

> Populate after running `train_model.py`.
> Values are from the **independent test set** only.
> Do NOT populate from validation set metrics.

| Model | Accuracy | Precision | Recall | F1 Macro | ROC-AUC | Latency (ms) | Training (s) |
|---|---|---|---|---|---|---|---|
| Random Forest | — | — | — | — | — | — | — |
| SVM | — | — | — | — | — | — | — |
| Neural Network | — | — | — | — | — | — | — |
| Hybrid Ensemble | — | — | — | — | — | — | — |
| **Journal baseline** | 77.31% | 96.63% | — | 75.77% | — | 61 ms | — |

**⚠️ Direct comparison with the journal baseline is NOT valid:**
- The journal used the original NSL-KDD 41-feature schema
- This project uses a custom 27-feature live-flow schema
- The journal had 125,973 training samples; this project has ~115
- Different feature distributions, collection environments, and class
  taxonomies make numeric comparison meaningless
- The journal figures are included only as a contextual reference

---

## Experiment E5 — Ablation: Class Weighting

**Purpose:** Measure impact of `class_weight="balanced"` on minority-class
(probe) recall.

| Condition | RF Config |
|---|---|
| E5-A | class_weight=None (default uniform) |
| E5-B | class_weight="balanced" |

### E5 Results

| Condition | Overall Acc | Probe Recall | Probe F1 |
|---|---|---|---|
| E5-A (uniform) | — | — | — |
| E5-B (balanced) | — | — | — |

**Instructions:**
Edit `train_model.py`, set `class_weight=None` for the RF, retrain, record
results in E5-A. Restore `class_weight="balanced"`, retrain, record E5-B.

---

## Experiment E6 — Ablation: Duration Floor

**Purpose:** Measure impact of the 1 ms duration floor on extreme rate values
and downstream model performance.

| Condition | Duration floor |
|---|---|
| E6-A | No floor (`max(duration, 0.0)`) — original behaviour |
| E6-B | 1 ms floor (`max(duration, 0.001)`) — current implementation |

### E6 Results

| Condition | Max pps observed | Max Bps observed | RF Accuracy | RF Probe Recall |
|---|---|---|---|---|
| E6-A (no floor) | — | — | — | — |
| E6-B (1 ms floor) | — | — | — | — |

---

## Experiment E7 — Latency Benchmark

**Purpose:** Measure end-to-end inference latency at different request rates.

**Method:** Use `test_smoke.py` or a benchmark script calling `POST /predict`
in a loop. Record `latency_ms` from each response.

| Load (events/s) | Avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Notes |
|---|---|---|---|---|---|
| 10 | — | — | — | — | |
| 50 | — | — | — | — | |
| 100 | — | — | — | — | |
| 500 | — | — | — | — | May require concurrent requests |

**Benchmark script:**
```bash
python backend/benchmark.py --rps 100 --duration 30
```
*(benchmark.py to be created in Phase 11)*

---

## Experiment E8 — Synthetic Traffic Evaluation

**Purpose:** Evaluate model on synthetic flows from `simulator.py` to
understand behaviour on unseen classes (DoS, R2L, U2R).

**Caveat:** Synthetic flows are generated from statistical profiles, not
real traffic. Results show model behaviour on the simulator's distributions,
not on real attack traffic.

| Synthetic Class | Model | Predicted Class | % Correct |
|---|---|---|---|
| dos | Random Forest | — | — |
| dos | Hybrid | — | — |
| r2l | Random Forest | — | — |
| r2l | Hybrid | — | — |
| u2r | Random Forest | — | — |
| u2r | Hybrid | — | — |

**Run with:**
```bash
# Start backend
python backend/app.py

# Simulate and check predictions
curl -X POST http://127.0.0.1:5000/simulate \
  -H "Content-Type: application/json" \
  -d '{"class": "dos", "count": 50}'
```

---

## Notes on Research Integrity

1. All metrics in this document must come from **actual experiment runs**.
2. Do not copy numbers from the journal paper into these tables.
3. Mark every result with the training timestamp and dataset MD5 from
   `metrics_all.json` so it can be reproduced.
4. The small dataset size (~115 training, ~52 test) means metrics have high
   variance. Report this limitation alongside every result.
5. The 98%+ accuracy seen in the controlled test should be noted as a result
   of highly uniform probe traffic, not generalised detection capability.

---

*End of EXPERIMENTS.md*
