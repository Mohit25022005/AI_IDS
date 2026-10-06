"""
Cloud-RT-IDS  ·  Preprocessing utilities
==========================================
Shared feature-schema constants and validation helpers used by
train_model.py, app.py, and tests.

Keeping the canonical feature list in one place prevents drift
between training and inference.
"""

# ------------------------------------------------------------------
# Feature schema version
# ------------------------------------------------------------------
FEATURE_SCHEMA_VERSION = "v2"

# ------------------------------------------------------------------
# Canonical 27-feature list  (order matters — must match training)
# ------------------------------------------------------------------
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
VALID_PROTOCOLS = {"tcp", "udp", "other"}

# Minimum duration floor applied in url_kdd.py
DURATION_FLOOR_SECONDS = 0.001


def validate_feature_dict(features: dict) -> list:
    """
    Validate a single feature dict.
    Returns a list of error strings; empty list means valid.
    """
    errors = []

    missing = [f for f in LIVE_FEATURE_COLUMNS if f not in features]
    if missing:
        errors.append(f"Missing features: {missing}")

    extra = [f for f in features if f not in LIVE_FEATURE_COLUMNS]
    if extra:
        errors.append(f"Unknown features: {extra}")

    for feat in NUMERIC_COLUMNS:
        if feat in features:
            try:
                float(features[feat])
            except (TypeError, ValueError):
                errors.append(f"Feature '{feat}' must be numeric, got {type(features[feat])}")

    if "protocol" in features:
        raw_proto = str(features["protocol"]).strip()
        # Reject anything that isn't already lowercase — the API contract
        # requires lowercase values (tcp / udp / other).
        if raw_proto != raw_proto.lower() or raw_proto.lower() not in VALID_PROTOCOLS:
            errors.append(
                f"protocol must be one of {VALID_PROTOCOLS} (lowercase), got '{raw_proto}'"
            )

    return errors


def validate_dataframe_schema(df) -> list:
    """
    Validate a pandas DataFrame has the correct columns and types.
    Returns list of error strings.
    """
    import pandas as pd
    errors = []

    missing = [c for c in LIVE_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing columns: {missing}")

    extra = [c for c in df.columns if c not in LIVE_FEATURE_COLUMNS + ["label"]]
    if extra:
        errors.append(f"Unexpected columns: {extra}")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            coerced = pd.to_numeric(df[col], errors="coerce")
            n_invalid = coerced.isna().sum() - df[col].isna().sum()
            if n_invalid > 0:
                errors.append(f"Column '{col}' has {n_invalid} non-numeric values")

    return errors
