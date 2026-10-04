"""
Cloud-RT-IDS Training Script
=============================
Trains four models on the 27-feature CIC-IDS-2017 dataset:
  1. Random Forest
  2. Support Vector Machine
  3. Neural Network (MLP)
  4. Hybrid Ensemble (soft voting: RF + SVM + NN)

Dataset: CIC-IDS-2017 (real network traffic, 7 classes)
  Classes: normal, dos, ddos, probe, r2l, bot, web_attack

For every model the script:
  - Trains on the full labelled training set (after 80/20 validation split)
  - Evaluates on the held-out validation set
  - Evaluates on the independent test set
  - Saves the sklearn Pipeline artifact (.pkl)
  - Saves a structured metrics JSON file (metrics_<name>.json)

A summary metrics_all.json is also written for the backend API.
"""

import os
import json
import hashlib
import random
import time
import warnings
import numpy as np
import pandas as pd

from datetime import datetime

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import SGDClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)
from sklearn.model_selection import train_test_split
import joblib

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------------
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ------------------------------------------------------------------
# Feature schema  (version-tagged — bump when the schema changes)
# ------------------------------------------------------------------
FEATURE_SCHEMA_VERSION = "v2"

LIVE_FEATURE_COLUMNS = [
    "duration",
    "source_port",
    "destination_port",
    "forward_packets",
    "backward_packets",
    "forward_bytes",
    "backward_bytes",
    "total_packets",
    "total_bytes",
    "packets_per_second",
    "bytes_per_second",
    "mean_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_std",
    "syn_count",
    "ack_count",
    "fin_count",
    "rst_count",
    "psh_count",
    "forward_packet_ratio",
    "backward_packet_ratio",
    "forward_byte_ratio",
    "backward_byte_ratio",
    "syn_ratio",
    "rst_ratio",
    "protocol",
]

CATEGORICAL_COLUMNS = ["protocol"]
NUMERIC_COLUMNS = [c for c in LIVE_FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

TRAIN_DATA_PATH = os.path.join(DATA_DIR, "live_flows.csv")
INDEPENDENT_TEST_PATH = os.path.join(DATA_DIR, "test_flows.csv")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def file_md5(path: str) -> str:
    """Return MD5 hex digest of a file for reproducibility tracking."""
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_dataset(df: pd.DataFrame, name: str):
    """
    Normalise labels, coerce numerics, drop invalid rows.
    Returns (X, y) DataFrames.
    """
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(str).str.strip().str.lower()

    X = df[LIVE_FEATURE_COLUMNS].copy()
    y = df["label"].copy()

    for col in NUMERIC_COLUMNS:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    X["protocol"] = X["protocol"].astype(str).str.strip().str.lower()

    valid = X[NUMERIC_COLUMNS].notna().all(axis=1)
    X = X.loc[valid].copy()
    y = y.loc[valid].copy()

    print(f"\n✅ {name}: {len(X)} valid samples")
    print(f"   Label distribution:\n{y.value_counts().to_string()}")
    return X, y


def build_preprocessor():
    """Return a fresh, unfitted ColumnTransformer."""
    return ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_COLUMNS),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ]
    )


def compute_metrics(y_true, y_pred, y_proba, classes, split_name: str) -> dict:
    """
    Compute a comprehensive metrics dict for a single split.
    y_proba: shape (n_samples, n_classes) — used for ROC-AUC / PR-AUC on binary tasks.
    """
    acc = float(accuracy_score(y_true, y_pred))
    prec_macro = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    rec_macro = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    f1_macro = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    f1_weighted = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    report_dict = classification_report(
        y_true, y_pred, output_dict=True, zero_division=0
    )

    per_class = {
        cls: {
            "precision": round(float(report_dict[cls]["precision"]), 4),
            "recall": round(float(report_dict[cls]["recall"]), 4),
            "f1": round(float(report_dict[cls]["f1-score"]), 4),
            "support": int(report_dict[cls]["support"]),
        }
        for cls in classes
        if cls in report_dict
    }

    cm = confusion_matrix(y_true, y_pred, labels=classes).tolist()

    # ROC-AUC / PR-AUC only meaningful for binary or with OvR
    roc_auc = None
    pr_auc = None
    if len(classes) == 2 and y_proba is not None:
        try:
            roc_auc = round(float(roc_auc_score(y_true, y_proba[:, 1])), 4)
            pr_auc = round(float(average_precision_score(y_true, y_proba[:, 1],
                                                          pos_label=classes[1])), 4)
        except Exception:
            pass

    return {
        "split": split_name,
        "n_samples": int(len(y_true)),
        "accuracy": round(acc, 4),
        "precision_macro": round(prec_macro, 4),
        "recall_macro": round(rec_macro, 4),
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "per_class": per_class,
        "confusion_matrix": cm,
        "confusion_matrix_labels": classes,
    }


def train_and_evaluate(
    name: str,
    estimator,
    X_train, y_train,
    X_val, y_val,
    X_test, y_test,
    classes: list,
    hyperparams: dict,
    train_hash: str,
    test_hash: str,
) -> dict:
    """
    Fit estimator on (X_train, y_train), evaluate on val and test.
    Returns the complete metrics dict and saves model + metrics JSON.
    """
    print(f"\n{'='*50}")
    print(f"  Training: {name}")
    print(f"{'='*50}")

    t0 = time.perf_counter()
    estimator.fit(X_train, y_train)
    training_time_s = round(time.perf_counter() - t0, 3)
    print(f"  Training time: {training_time_s}s")

    # --- validation ---
    t1 = time.perf_counter()
    val_pred = estimator.predict(X_val)
    val_proba = estimator.predict_proba(X_val) if hasattr(estimator, "predict_proba") else None
    val_latency_ms = round((time.perf_counter() - t1) / len(X_val) * 1000, 4)
    val_metrics = compute_metrics(y_val, val_pred, val_proba, classes, "validation")
    print(f"  Validation  accuracy={val_metrics['accuracy']:.4f}  "
          f"macro-F1={val_metrics['f1_macro']:.4f}")

    # --- refit on full training set ---
    estimator.fit(X_train, y_train)   # already fit on split; refit on full

    # --- independent test ---
    t2 = time.perf_counter()
    test_pred = estimator.predict(X_test)
    test_proba = estimator.predict_proba(X_test) if hasattr(estimator, "predict_proba") else None
    test_latency_ms = round((time.perf_counter() - t2) / len(X_test) * 1000, 4)
    test_metrics = compute_metrics(y_test, test_pred, test_proba, classes, "independent_test")
    print(f"  Test        accuracy={test_metrics['accuracy']:.4f}  "
          f"macro-F1={test_metrics['f1_macro']:.4f}")

    # --- feature importances (RF only) ---
    feature_importances = None
    try:
        step = estimator.named_steps.get("model")
        if step is None:
            # VotingClassifier
            for est_name, est in estimator.named_steps.get("model", estimator).estimators:
                if hasattr(est, "feature_importances_"):
                    feature_importances = est.feature_importances_.tolist()
                    break
        elif hasattr(step, "feature_importances_"):
            feature_importances = step.feature_importances_.tolist()
    except Exception:
        pass

    metrics_doc = {
        "model_name": name,
        "algorithm": name,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_columns": LIVE_FEATURE_COLUMNS,
        "n_features": len(LIVE_FEATURE_COLUMNS),
        "classes": classes,
        "hyperparameters": hyperparams,
        "random_seed": RANDOM_SEED,
        "training_timestamp": datetime.utcnow().isoformat() + "Z",
        "training_time_seconds": training_time_s,
        "n_train_samples": int(len(X_train)),
        "n_val_samples": int(len(X_val)),
        "n_test_samples": int(len(X_test)),
        "train_dataset_md5": train_hash,
        "test_dataset_md5": test_hash,
        "val_inference_latency_ms_per_sample": val_latency_ms,
        "test_inference_latency_ms_per_sample": test_latency_ms,
        "validation": val_metrics,
        "independent_test": test_metrics,
        "feature_importances": feature_importances,
    }

    # --- save model ---
    safe_name = name.lower().replace(" ", "_")
    model_path = os.path.join(BASE_DIR, f"model_{safe_name}.pkl")
    metrics_path = os.path.join(BASE_DIR, f"metrics_{safe_name}.json")

    joblib.dump(estimator, model_path)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics_doc, fh, indent=2)

    print(f"  💾 Model:   {model_path}")
    print(f"  💾 Metrics: {metrics_path}")

    return metrics_doc


# ==================================================================
# MAIN
# ==================================================================

print("\n" + "="*60)
print("     CLOUD-RT-IDS  ·  MULTI-MODEL TRAINING")
print("="*60)
print(f"  Feature schema version : {FEATURE_SCHEMA_VERSION}")
print(f"  Random seed            : {RANDOM_SEED}")
print(f"  Training data          : {TRAIN_DATA_PATH}")
print(f"  Independent test data  : {INDEPENDENT_TEST_PATH}")

# ------------------------------------------------------------------
# Load & validate
# ------------------------------------------------------------------
if not os.path.exists(TRAIN_DATA_PATH):
    raise FileNotFoundError(f"\n❌ Training dataset not found:\n{TRAIN_DATA_PATH}")
if not os.path.exists(INDEPENDENT_TEST_PATH):
    raise FileNotFoundError(
        f"\n❌ Independent test dataset not found:\n{INDEPENDENT_TEST_PATH}\n"
        "Create test_flows.csv with a separate capture session."
    )

train_hash = file_md5(TRAIN_DATA_PATH)
test_hash = file_md5(INDEPENDENT_TEST_PATH)
print(f"\n  Training data MD5   : {train_hash}")
print(f"  Independent test MD5: {test_hash}")

train_df = pd.read_csv(TRAIN_DATA_PATH)
test_df = pd.read_csv(INDEPENDENT_TEST_PATH)

X_full, y_full = clean_dataset(train_df, "Training dataset")
X_independent, y_independent = clean_dataset(test_df, "Independent test dataset")

# Class validation
training_classes = set(y_full.unique())
test_classes = set(y_independent.unique())
all_classes = sorted(training_classes | test_classes)

if not test_classes.issubset(training_classes):
    unknown = test_classes - training_classes
    raise ValueError(
        f"\n❌ Test labels not in training set: {unknown}"
    )
if len(training_classes) < 2:
    raise ValueError("\n❌ Need at least two classes.")

# ------------------------------------------------------------------
# Train / Validation split  (80/20, stratified, fixed seed)
# ------------------------------------------------------------------
X_train, X_val, y_train, y_val = train_test_split(
    X_full, y_full,
    test_size=0.20,
    random_state=RANDOM_SEED,
    stratify=y_full,
)
print(f"\n  Train samples      : {len(X_train)}")
print(f"  Validation samples : {len(X_val)}")
print(f"  Independent test   : {len(X_independent)}")
print(f"  Classes            : {all_classes}")

# ------------------------------------------------------------------
# Class distribution for documentation
# ------------------------------------------------------------------
class_distribution_train = y_full.value_counts().to_dict()
class_distribution_test = y_independent.value_counts().to_dict()

# ------------------------------------------------------------------
# Build the four models
# ------------------------------------------------------------------

# 1) Random Forest  -----------------------------------------------
rf_estimator = Pipeline([
    ("preprocessor", build_preprocessor()),
    ("model", RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )),
])
rf_params = {
    "n_estimators": 300,
    "max_depth": None,
    "class_weight": "balanced",
    "random_state": RANDOM_SEED,
}

# 2) SVM (Linear, via SGDClassifier — scales to 200k rows)  --------
# RBF SVC would take hours on 200k samples.  SGD with hinge loss is
# mathematically equivalent to a linear SVM and trains in seconds.
# CalibratedClassifierCV wraps it so predict_proba() is available
# (needed for soft voting in the Hybrid model).
svm_estimator = Pipeline([
    ("preprocessor", build_preprocessor()),
    ("model", CalibratedClassifierCV(
        SGDClassifier(
            loss="modified_huber",   # smooth hinge — gives probabilities natively
            penalty="l2",
            alpha=1e-4,
            max_iter=1000,
            tol=1e-3,
            class_weight="balanced",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        cv=3,
        method="isotonic",
    )),
])
svm_params = {
    "algorithm":    "SGD (linear SVM, modified_huber loss)",
    "penalty":      "l2",
    "alpha":        1e-4,
    "max_iter":     1000,
    "class_weight": "balanced",
    "calibration":  "CalibratedClassifierCV(cv=3, isotonic)",
    "note":         "RBF SVC replaced with SGD for scalability (200k rows)",
}

# 3) Neural Network (MLP) — deeper for 7-class real data  ----------
nn_estimator = Pipeline([
    ("preprocessor", build_preprocessor()),
    ("model", MLPClassifier(
        hidden_layer_sizes=(256, 128, 64),
        activation="relu",
        solver="adam",
        alpha=1e-4,
        batch_size=512,
        max_iter=200,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=15,
        random_state=RANDOM_SEED,
    )),
])
nn_params = {
    "hidden_layer_sizes": [256, 128, 64],
    "activation": "relu",
    "solver": "adam",
    "alpha": 1e-4,
    "batch_size": 512,
    "max_iter": 200,
    "early_stopping": True,
    "random_state": RANDOM_SEED,
}

# ------------------------------------------------------------------
# Train base models first (required for VotingClassifier)
# ------------------------------------------------------------------
all_results = {}

rf_metrics = train_and_evaluate(
    "random_forest", rf_estimator,
    X_train, y_train, X_val, y_val, X_independent, y_independent,
    all_classes, rf_params, train_hash, test_hash,
)
all_results["random_forest"] = rf_metrics

svm_metrics = train_and_evaluate(
    "svm", svm_estimator,
    X_train, y_train, X_val, y_val, X_independent, y_independent,
    all_classes, svm_params, train_hash, test_hash,
)
all_results["svm"] = svm_metrics

nn_metrics = train_and_evaluate(
    "neural_network", nn_estimator,
    X_train, y_train, X_val, y_val, X_independent, y_independent,
    all_classes, nn_params, train_hash, test_hash,
)
all_results["neural_network"] = nn_metrics

# 4) Hybrid Ensemble (soft voting: RF + LinearSVM + NN)  -----------
hybrid_estimator = Pipeline([
    ("preprocessor", build_preprocessor()),
    ("model", VotingClassifier(
        estimators=[
            ("rf", RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=RANDOM_SEED,
                n_jobs=-1,
            )),
            ("svm", CalibratedClassifierCV(
                SGDClassifier(
                    loss="modified_huber",
                    penalty="l2",
                    alpha=1e-4,
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                    n_jobs=-1,
                ),
                cv=3,
                method="isotonic",
            )),
            ("nn", MLPClassifier(
                hidden_layer_sizes=(256, 128, 64),
                activation="relu",
                solver="adam",
                alpha=1e-4,
                batch_size=512,
                max_iter=200,
                early_stopping=True,
                validation_fraction=0.1,
                n_iter_no_change=15,
                random_state=RANDOM_SEED,
            )),
        ],
        voting="soft",
    )),
])
hybrid_params = {
    "voting": "soft",
    "estimators": ["random_forest", "linear_svm", "neural_network"],
    "strategy": "average_of_class_probabilities",
}

hybrid_metrics = train_and_evaluate(
    "hybrid", hybrid_estimator,
    X_train, y_train, X_val, y_val, X_independent, y_independent,
    all_classes, hybrid_params, train_hash, test_hash,
)
all_results["hybrid"] = hybrid_metrics

# ------------------------------------------------------------------
# Also save the default model as model.pkl (backward compat)
# The default is Random Forest; the backend picks the active model
# via settings, but model.pkl is kept so existing code still loads.
# ------------------------------------------------------------------
rf_final_path = os.path.join(BASE_DIR, "model.pkl")
joblib.dump(rf_estimator, rf_final_path)

rf_preprocessor_path = os.path.join(BASE_DIR, "preprocessor.pkl")
joblib.dump(rf_estimator.named_steps["preprocessor"], rf_preprocessor_path)

print(f"\n💾 Default model (RF) also saved as model.pkl")

# ------------------------------------------------------------------
# Save summary comparison file
# ------------------------------------------------------------------
comparison = []
for model_key, res in all_results.items():
    it = res["independent_test"]
    comparison.append({
        "model": model_key,
        "accuracy": it["accuracy"],
        "precision_macro": it["precision_macro"],
        "recall_macro": it["recall_macro"],
        "f1_macro": it["f1_macro"],
        "f1_weighted": it["f1_weighted"],
        "roc_auc": it["roc_auc"],
        "pr_auc": it["pr_auc"],
        "latency_ms_per_sample": res["test_inference_latency_ms_per_sample"],
        "training_time_s": res["training_time_seconds"],
    })

summary = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "feature_schema_version": FEATURE_SCHEMA_VERSION,
    "random_seed": RANDOM_SEED,
    "n_train_samples": int(len(X_full)),
    "n_test_samples": int(len(X_independent)),
    "classes": all_classes,
    "class_distribution_train": {k: int(v) for k, v in class_distribution_train.items()},
    "class_distribution_test": {k: int(v) for k, v in class_distribution_test.items()},
    "train_dataset_md5": train_hash,
    "test_dataset_md5": test_hash,
    "model_comparison": comparison,
    # Expose current independent-test metrics for the default (RF) model
    # so the backend's /insights/metrics endpoint can serve real numbers.
    "default_model": "random_forest",
    "current_metrics": all_results["random_forest"]["independent_test"],
}

summary_path = os.path.join(BASE_DIR, "metrics_all.json")
with open(summary_path, "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)

print(f"\n💾 Summary: {summary_path}")

# ------------------------------------------------------------------
# Experiments directory
# ------------------------------------------------------------------
exp_dir = os.path.join(os.path.dirname(BASE_DIR), "..", "experiments")
os.makedirs(os.path.join(exp_dir, "baseline"), exist_ok=True)
os.makedirs(os.path.join(exp_dir, "random_forest"), exist_ok=True)
os.makedirs(os.path.join(exp_dir, "svm"), exist_ok=True)
os.makedirs(os.path.join(exp_dir, "neural_network"), exist_ok=True)
os.makedirs(os.path.join(exp_dir, "hybrid"), exist_ok=True)
os.makedirs(os.path.join(exp_dir, "imbalance_experiments"), exist_ok=True)

run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
run_dir = os.path.join(exp_dir, "baseline", run_ts)
os.makedirs(run_dir, exist_ok=True)

with open(os.path.join(run_dir, "metrics_all.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)
with open(os.path.join(run_dir, "run_info.json"), "w", encoding="utf-8") as fh:
    json.dump({
        "run_timestamp": run_ts,
        "script": __file__,
        "train_data": TRAIN_DATA_PATH,
        "test_data": INDEPENDENT_TEST_PATH,
        "train_md5": train_hash,
        "test_md5": test_hash,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "random_seed": RANDOM_SEED,
        "classes": all_classes,
    }, fh, indent=2)

print(f"\n📁 Experiment saved to: {run_dir}")

# ------------------------------------------------------------------
# Final comparison table (stdout)
# ------------------------------------------------------------------
print("\n" + "="*70)
print("  MODEL COMPARISON  (Independent Test Set)")
print("="*70)
print(f"  {'Model':<20} {'Acc':>6} {'Prec':>6} {'Rec':>6} {'F1':>6} {'ROC':>6} {'Lat ms':>8}")
print("-"*70)
for row in comparison:
    roc = f"{row['roc_auc']:.4f}" if row["roc_auc"] is not None else "  N/A "
    print(
        f"  {row['model']:<20} "
        f"{row['accuracy']:>6.4f} "
        f"{row['precision_macro']:>6.4f} "
        f"{row['recall_macro']:>6.4f} "
        f"{row['f1_macro']:>6.4f} "
        f"{roc:>6} "
        f"{row['latency_ms_per_sample']:>8.4f}"
    )
print("="*70)

print("\n✅ Training complete.  All artifacts saved.")
print(
    "\n⚠️  REMINDER: The independent test set was NEVER used during training.\n"
    "   Its results are the primary held-out evaluation for this experiment.\n"
    "   The dataset is small and controlled — do not over-generalise results."
)
