import os
import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)
from sklearn.model_selection import train_test_split


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

DATA_PATH = os.path.join(DATA_DIR, "live_flows.csv")

MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
PREPROCESSOR_PATH = os.path.join(BASE_DIR, "preprocessor.pkl")


# ============================================================
# CANONICAL LIVE FEATURES
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
# LOAD DATASET
# ============================================================

print("==============================================")
print("        LIVE NETWORK IDS TRAINING")
print("==============================================")

print(f"\n📂 Dataset: {DATA_PATH}")

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"\n❌ Dataset not found:\n{DATA_PATH}\n\n"
        "We have not created live_flows.csv yet.\n"
        "Do NOT use NSL-KDD for this new 27-feature model."
    )


df = pd.read_csv(DATA_PATH)

print(f"📊 Total samples: {len(df)}")


# ============================================================
# VALIDATE DATASET
# ============================================================

required_columns = LIVE_FEATURE_COLUMNS + ["label"]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        "\n❌ Dataset is missing required columns:\n"
        + "\n".join(f"   - {column}" for column in missing_columns)
    )


# Remove rows with missing labels
df = df.dropna(subset=["label"]).copy()


# Normalize labels
df["label"] = df["label"].astype(str).str.strip().str.lower()


print("\n🏷️ Label distribution:")
print(df["label"].value_counts())


# ============================================================
# FEATURES / LABEL
# ============================================================

X = df[LIVE_FEATURE_COLUMNS].copy()
y = df["label"].copy()


# ============================================================
# DATA TYPE CLEANUP
# ============================================================

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

X["protocol"] = X["protocol"].astype(str).str.lower()


# Remove invalid rows
valid_rows = X[numeric_columns].notna().all(axis=1)

X = X.loc[valid_rows].copy()
y = y.loc[valid_rows].copy()


print(f"\n✅ Valid samples after cleaning: {len(X)}")


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


print(f"🧪 Training samples: {len(X_train)}")
print(f"🔬 Testing samples:  {len(X_test)}")


# ============================================================
# PREPROCESSING
# ============================================================

categorical_columns = [
    "protocol"
]

numeric_columns = [
    column
    for column in LIVE_FEATURE_COLUMNS
    if column not in categorical_columns
]


preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            StandardScaler(),
            numeric_columns
        ),
        (
            "categorical",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
            categorical_columns
        )
    ]
)


# ============================================================
# MODEL
# ============================================================

model = RandomForestClassifier(
    n_estimators=300,
    random_state=42,
    class_weight="balanced",
    n_jobs=-1
)


pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)


# ============================================================
# TRAIN
# ============================================================

print("\n🚀 Training Random Forest...")

pipeline.fit(
    X_train,
    y_train
)


print("✅ Training completed.")


# ============================================================
# EVALUATION
# ============================================================

print("\n==============================================")
print("                EVALUATION")
print("==============================================")

predictions = pipeline.predict(X_test)


accuracy = accuracy_score(
    y_test,
    predictions
)

print(f"\nAccuracy: {accuracy:.4f}")


print("\nClassification Report:")
print(
    classification_report(
        y_test,
        predictions,
        zero_division=0
    )
)


print("\nConfusion Matrix:")

labels = sorted(y.unique())

cm = confusion_matrix(
    y_test,
    predictions,
    labels=labels
)

print("\nLabels:")
print(labels)

print("\nMatrix:")
print(cm)


# ============================================================
# SAVE MODEL
# ============================================================

joblib.dump(
    pipeline,
    MODEL_PATH
)

# Save the fitted preprocessor separately as well.
joblib.dump(
    preprocessor,
    PREPROCESSOR_PATH
)


print("\n==============================================")
print("             MODEL SAVED")
print("==============================================")

print(f"💾 Model:        {MODEL_PATH}")
print(f"💾 Preprocessor: {PREPROCESSOR_PATH}")

print("\n✅ Live IDS training pipeline is ready.")