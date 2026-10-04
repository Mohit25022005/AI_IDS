"""
Cloud-RT-IDS  ·  IsolationForest Anomaly Model
================================================
Trains an IsolationForest on normal-only traffic so the IDS can flag
flows that are statistically unusual even if the classifier says "normal"
(zero-day / evasion detection).

The model is saved as model/model_anomaly.pkl.

Run from the backend/ directory:
    python train_anomaly.py
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "model")

TRAIN_PATH = os.path.join(DATA_DIR, "live_flows.csv")

LIVE_FEATURE_COLUMNS = [
    "duration", "source_port", "destination_port",
    "forward_packets", "backward_packets",
    "forward_bytes", "backward_bytes",
    "total_packets", "total_bytes",
    "packets_per_second", "bytes_per_second",
    "mean_packet_size", "min_packet_size", "max_packet_size", "packet_size_std",
    "syn_count", "ack_count", "fin_count", "rst_count", "psh_count",
    "forward_packet_ratio", "backward_packet_ratio",
    "forward_byte_ratio", "backward_byte_ratio",
    "syn_ratio", "rst_ratio",
    "protocol",
]
CATEGORICAL_COLUMNS = ["protocol"]
NUMERIC_COLUMNS     = [c for c in LIVE_FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]

print("\n" + "="*55)
print("  CLOUD-RT-IDS  ·  ANOMALY MODEL TRAINING")
print("="*55)

if not os.path.exists(TRAIN_PATH):
    raise FileNotFoundError(f"Training data not found: {TRAIN_PATH}")

df = pd.read_csv(TRAIN_PATH)
df["label"] = df["label"].astype(str).str.strip().str.lower()

# Train ONLY on normal traffic — the model learns what "normal" looks like
normal_df = df[df["label"] == "normal"].copy()
if len(normal_df) < 10:
    raise ValueError(f"Need at least 10 normal samples, found {len(normal_df)}")

print(f"\n  Normal samples for training: {len(normal_df)}")

X = normal_df[LIVE_FEATURE_COLUMNS].copy()
for col in NUMERIC_COLUMNS:
    X[col] = pd.to_numeric(X[col], errors="coerce")
X["protocol"] = X["protocol"].astype(str).str.strip().str.lower()
X = X.dropna()

print(f"  Valid samples after cleaning: {len(X)}")

# Build pipeline: same preprocessing as the classifier
preprocessor = ColumnTransformer(
    transformers=[
        ("numeric",      StandardScaler(),              NUMERIC_COLUMNS),
        ("categorical",  OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
    ]
)

# IsolationForest parameters
#   contamination="auto"  → let the model decide the threshold
#   n_estimators=200      → good balance of accuracy vs speed
#   max_samples="auto"    → auto-size based on dataset
anomaly_pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", IsolationForest(
        n_estimators=200,
        contamination="auto",
        max_samples="auto",
        random_state=42,
        n_jobs=-1,
    )),
])

print("\n  Training IsolationForest ...")
anomaly_pipeline.fit(X)
print("  ✅ Training complete")

# Quick sanity check: score the training data
scores = anomaly_pipeline.decision_function(X)
print(f"\n  Decision function on normal traffic:")
print(f"    mean  = {np.mean(scores):.4f}")
print(f"    std   = {np.std(scores):.4f}")
print(f"    min   = {np.min(scores):.4f}")
print(f"    max   = {np.max(scores):.4f}")

# Also score attack samples to verify separation
attack_df = df[df["label"] != "normal"].copy()
if not attack_df.empty:
    X_attack = attack_df[LIVE_FEATURE_COLUMNS].copy()
    for col in NUMERIC_COLUMNS:
        X_attack[col] = pd.to_numeric(X_attack[col], errors="coerce")
    X_attack["protocol"] = X_attack["protocol"].astype(str).str.strip().str.lower()
    X_attack = X_attack.dropna()

    attack_scores = anomaly_pipeline.decision_function(X_attack)
    print(f"\n  Decision function on attack traffic ({len(X_attack)} samples):")
    print(f"    mean  = {np.mean(attack_scores):.4f}")
    print(f"    std   = {np.std(attack_scores):.4f}")
    print(f"    min   = {np.min(attack_scores):.4f}")
    print(f"    max   = {np.max(attack_scores):.4f}")

    # Anomaly detection rate: attacks should score lower (more negative)
    detected = np.sum(attack_scores < 0)
    rate     = detected / len(attack_scores) * 100
    print(f"\n  Anomaly detection rate on attacks: {detected}/{len(X_attack)} = {rate:.1f}%")

# Save
out_path = os.path.join(MODEL_DIR, "model_anomaly.pkl")
joblib.dump(anomaly_pipeline, out_path)
print(f"\n  💾 Saved: {out_path}")

# Save metadata
meta = {
    "trained_at":       datetime.utcnow().isoformat() + "Z",
    "algorithm":        "IsolationForest",
    "n_estimators":     200,
    "contamination":    "auto",
    "n_train_samples":  int(len(X)),
    "feature_columns":  LIVE_FEATURE_COLUMNS,
    "note":             "Trained on normal traffic only. Lower decision_function score = more anomalous.",
}
meta_path = os.path.join(MODEL_DIR, "metrics_anomaly.json")
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, indent=2)
print(f"  💾 Metadata: {meta_path}")

print("\n✅ Anomaly model ready. Restart app.py to load it.")
