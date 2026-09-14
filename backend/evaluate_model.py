import os
import joblib
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "model",
    "model.pkl"
)

TEST_PATH = os.path.join(
    BASE_DIR,
    "data",
    "test_flows.csv"
)


# ============================================================
# FEATURES
# ============================================================

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
    "protocol"
]


# ============================================================
# LOAD MODEL
# ============================================================

print("==============================================")
print("          INDEPENDENT MODEL EVALUATION")
print("==============================================")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Model not found:\n{MODEL_PATH}"
    )

if not os.path.exists(TEST_PATH):
    raise FileNotFoundError(
        f"Test dataset not found:\n{TEST_PATH}"
    )

print(f"\n🤖 Model: {MODEL_PATH}")
print(f"🧪 Test data: {TEST_PATH}")

model = joblib.load(MODEL_PATH)

df = pd.read_csv(TEST_PATH)

print(f"\n📊 Test samples: {len(df)}")


# ============================================================
# VALIDATE TEST DATA
# ============================================================

required_columns = LIVE_FEATURE_COLUMNS + ["label"]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        "\n❌ Missing columns:\n"
        + "\n".join(
            f"   - {column}"
            for column in missing_columns
        )
    )


print("\n🏷️ Test label distribution:")
print(df["label"].value_counts())


# ============================================================
# PREPARE FEATURES
# ============================================================

X = df[LIVE_FEATURE_COLUMNS].copy()

y = (
    df["label"]
    .astype(str)
    .str.strip()
    .str.lower()
)


numeric_columns = [
    column
    for column in LIVE_FEATURE_COLUMNS
    if column != "protocol"
]


for column in numeric_columns:
    X[column] = pd.to_numeric(
        X[column],
        errors="coerce"
    )


X["protocol"] = (
    X["protocol"]
    .astype(str)
    .str.lower()
)


valid_rows = (
    X[numeric_columns]
    .notna()
    .all(axis=1)
)

X = X.loc[valid_rows].copy()
y = y.loc[valid_rows].copy()


print(
    f"\n✅ Valid test samples: {len(X)}"
)


# ============================================================
# PREDICTION
# ============================================================

print("\n🚀 Running predictions...")

predictions = model.predict(X)


# ============================================================
# EVALUATION
# ============================================================

accuracy = accuracy_score(
    y,
    predictions
)

print("\n==============================================")
print("                 RESULTS")
print("==============================================")

print(
    f"\nAccuracy: {accuracy:.4f}"
)

print("\nClassification Report:")

print(
    classification_report(
        y,
        predictions,
        zero_division=0
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

labels = sorted(y.unique())

cm = confusion_matrix(
    y,
    predictions,
    labels=labels
)

print("\nConfusion Matrix:")

print("\nLabels:")
print(labels)

print("\nMatrix:")
print(cm)


print("\n==============================================")
print("              EVALUATION COMPLETE")
print("==============================================")