"""
Cloud-RT-IDS  ·  CIC-IDS-2017 Data Pipeline
=============================================
Reads all 8 CIC-IDS-2017 CSVs, maps their 79 CICFlowMeter columns to the
project's 27-feature schema, normalises labels into 7 clean classes, handles
all known data quality issues in the dataset, balances class distribution,
then writes:
    data/live_flows.csv   — training split  (80 %)
    data/test_flows.csv   — test split      (20 %, stratified, held-out)

Classes produced
----------------
  normal     ← BENIGN
  dos        ← DoS Hulk / GoldenEye / slowloris / Slowhttptest / Heartbleed
  ddos       ← DDoS
  probe      ← PortScan
  r2l        ← FTP-Patator / SSH-Patator / Infiltration
  bot        ← Bot
  web_attack ← Web Attack (Brute Force / XSS / Sql Injection)

Run from the backend/ directory:
    python cicids_pipeline.py

Options
    --samples-per-class N   max rows per class  (default 50000)
    --normal-samples N      max normal rows      (default 100000)
    --seed N                random seed          (default 42)
    --dry-run               print stats, don't write files
"""

import os
import sys
import argparse
import hashlib
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
CIC_DIR     = os.path.join(BASE_DIR, "..", "MachineLearningCSV", "MachineLearningCVE")
TRAIN_OUT   = os.path.join(DATA_DIR, "live_flows.csv")
TEST_OUT    = os.path.join(DATA_DIR, "test_flows.csv")

CIC_FILES = [
    "Monday-WorkingHours.pcap_ISCX.csv",
    "Tuesday-WorkingHours.pcap_ISCX.csv",
    "Wednesday-workingHours.pcap_ISCX.csv",
    "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
    "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
    "Friday-WorkingHours-Morning.pcap_ISCX.csv",
    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
]

# ── CIC-IDS-2017 column → our feature name ───────────────────────────
# CIC columns have leading spaces — strip on load
CIC_TO_OURS = {
    "Flow Duration":                  "duration",
    "Destination Port":               "destination_port",
    "Total Fwd Packets":              "forward_packets",
    "Total Backward Packets":         "backward_packets",
    "Total Length of Fwd Packets":    "forward_bytes",
    "Total Length of Bwd Packets":    "backward_bytes",
    "Flow Packets/s":                 "packets_per_second",
    "Flow Bytes/s":                   "bytes_per_second",
    "Packet Length Mean":             "mean_packet_size",
    "Min Packet Length":              "min_packet_size",
    "Max Packet Length":              "max_packet_size",
    "Packet Length Std":              "packet_size_std",
    "SYN Flag Count":                 "syn_count",
    "ACK Flag Count":                 "ack_count",
    "FIN Flag Count":                 "fin_count",
    "RST Flag Count":                 "rst_count",
    "PSH Flag Count":                 "psh_count",
    "Label":                          "label",
}

# Features that must be derived (not present directly in CIC)
DERIVED_FEATURES = [
    "source_port",           # not in CIC → 0
    "total_packets",         # fwd + bwd
    "total_bytes",           # fwd_bytes + bwd_bytes
    "forward_packet_ratio",  # fwd / total
    "backward_packet_ratio", # bwd / total
    "forward_byte_ratio",    # fwd_bytes / total_bytes
    "backward_byte_ratio",   # bwd_bytes / total_bytes
    "syn_ratio",             # syn / total_packets
    "rst_ratio",             # rst / total_packets
    "protocol",              # not in CIC → "tcp"
]

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
    "label",
]

# ── Label normalisation map ───────────────────────────────────────────
LABEL_MAP = {
    "BENIGN":                    "normal",
    "DoS Hulk":                  "dos",
    "DoS GoldenEye":             "dos",
    "DoS slowloris":             "dos",
    "DoS Slowhttptest":          "dos",
    "Heartbleed":                "dos",      # exploit causing DoS effect
    "DDoS":                      "ddos",
    "PortScan":                  "probe",
    "FTP-Patator":               "r2l",
    "SSH-Patator":               "r2l",
    "Infiltration":              "r2l",
    "Bot":                       "bot",
    "Web Attack \x96 Brute Force":  "web_attack",
    "Web Attack \x96 XSS":          "web_attack",
    "Web Attack \x96 Sql Injection": "web_attack",
    # variants with different encodings
    "Web Attack – Brute Force":  "web_attack",
    "Web Attack – XSS":          "web_attack",
    "Web Attack – Sql Injection":"web_attack",
}


def normalise_label(raw: str) -> str:
    """Map a raw CIC label to our clean class name."""
    raw = str(raw).strip()
    if raw in LABEL_MAP:
        return LABEL_MAP[raw]
    # Fuzzy fallbacks
    rl = raw.lower()
    if "benign" in rl:              return "normal"
    if "dos" in rl or "hulk" in rl: return "dos"
    if "ddos" in rl:                return "ddos"
    if "scan" in rl or "probe" in rl: return "probe"
    if "patator" in rl or "infiltr" in rl: return "r2l"
    if "bot" in rl:                 return "bot"
    if "web" in rl or "brute" in rl or "xss" in rl or "sql" in rl: return "web_attack"
    return None   # unknown → drop


def load_and_map_csv(path: str) -> pd.DataFrame:
    """Load one CIC CSV, rename columns, derive features, return mapped DataFrame."""
    # CIC CSVs have leading/trailing spaces in column names
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    df.columns = df.columns.str.strip()

    # ── Rename direct-map columns ─────────────────────────────────────
    rename = {k: v for k, v in CIC_TO_OURS.items() if k in df.columns}
    df = df.rename(columns=rename)

    # ── Normalise label ───────────────────────────────────────────────
    df["label"] = df["label"].apply(normalise_label)
    df = df[df["label"].notna()].copy()

    # ── Convert all numeric cols to float, coerce errors ─────────────
    numeric_cols = [c for c in df.columns if c not in ("label",)]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Replace inf / -inf with NaN then drop ────────────────────────
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # ── Derive missing features ───────────────────────────────────────
    df["source_port"]           = 0           # not available in CIC
    df["protocol"]              = "tcp"       # CIC is predominantly TCP

    df["total_packets"]         = df["forward_packets"] + df["backward_packets"]
    df["total_bytes"]           = df["forward_bytes"]   + df["backward_bytes"]

    # Guard against division by zero
    total_pkts = df["total_packets"].replace(0, np.nan)
    total_byt  = df["total_bytes"].replace(0, np.nan)

    df["forward_packet_ratio"]  = df["forward_packets"]  / total_pkts
    df["backward_packet_ratio"] = df["backward_packets"] / total_pkts
    df["forward_byte_ratio"]    = df["forward_bytes"]    / total_byt
    df["backward_byte_ratio"]   = df["backward_bytes"]   / total_byt
    df["syn_ratio"]             = df["syn_count"]        / total_pkts
    df["rst_ratio"]             = df["rst_count"]        / total_pkts

    # Fill ratio NaNs with 0.5 (symmetric fallback)
    for col in ["forward_packet_ratio", "backward_packet_ratio",
                "forward_byte_ratio",   "backward_byte_ratio",
                "syn_ratio",            "rst_ratio"]:
        df[col] = df[col].fillna(0.0)

    # ── Duration: CIC stores microseconds → convert to seconds ────────
    # Values > 1e6 are almost certainly in microseconds
    if "duration" in df.columns:
        df["duration"] = df["duration"] / 1_000_000.0

    # ── Select only our 27 features + label ───────────────────────────
    missing_cols = [c for c in LIVE_FEATURE_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"  ⚠ Missing columns filled with 0: {missing_cols}")
        for c in missing_cols:
            df[c] = 0

    df = df[LIVE_FEATURE_COLUMNS].copy()

    # ── Final NaN drop (after all derivations) ────────────────────────
    before = len(df)
    numeric_features = [c for c in LIVE_FEATURE_COLUMNS if c not in ("protocol", "label")]
    df = df.dropna(subset=numeric_features)
    dropped = before - len(df)
    if dropped:
        print(f"  ↳ Dropped {dropped:,} rows with NaN after derivation")

    return df


def file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(args):
    print("\n" + "=" * 60)
    print("  CLOUD-RT-IDS  ·  CIC-IDS-2017 PIPELINE")
    print("=" * 60)
    print(f"  CIC source dir : {CIC_DIR}")
    print(f"  Output train   : {TRAIN_OUT}")
    print(f"  Output test    : {TEST_OUT}")
    print(f"  Max per-class  : {args.samples_per_class:,}")
    print(f"  Max normal     : {args.normal_samples:,}")
    print(f"  Random seed    : {args.seed}")

    # ── Load all CSVs ──────────────────────────────────────────────────
    frames = []
    for fname in CIC_FILES:
        path = os.path.join(CIC_DIR, fname)
        if not os.path.exists(path):
            print(f"\n  ⚠ NOT FOUND (skipping): {fname}")
            continue
        print(f"\n  Loading {fname} ...")
        try:
            df = load_and_map_csv(path)
            counts = df["label"].value_counts()
            for lbl, cnt in counts.items():
                print(f"    {lbl:<14}: {cnt:>8,}")
            print(f"    {'TOTAL':<14}: {len(df):>8,}")
            frames.append(df)
        except Exception as exc:
            print(f"  ✗ Error loading {fname}: {exc}")

    if not frames:
        raise RuntimeError("No CIC CSV files loaded — check CIC_DIR path")

    combined = pd.concat(frames, ignore_index=True)
    print(f"\n{'─'*60}")
    print(f"  Combined rows (before balancing): {len(combined):,}")
    print(f"  Label distribution:")
    for lbl, cnt in combined["label"].value_counts().items():
        print(f"    {lbl:<14}: {cnt:>10,}")

    # ── Remove duplicate flows ─────────────────────────────────────────
    before = len(combined)
    numeric_features = [c for c in LIVE_FEATURE_COLUMNS if c not in ("protocol", "label")]
    combined = combined.drop_duplicates(subset=numeric_features)
    print(f"\n  Duplicates removed: {before - len(combined):,}")

    # ── Balance classes ────────────────────────────────────────────────
    # Normal is 80 % of data — cap it; cap attacks to avoid RF just
    # memorising majority class
    rng = np.random.default_rng(args.seed)
    balanced_frames = []
    for cls, grp in combined.groupby("label"):
        cap = args.normal_samples if cls == "normal" else args.samples_per_class
        if len(grp) > cap:
            grp = grp.sample(n=cap, random_state=args.seed)
            print(f"  Sampled {cls:<14}: {cap:>8,}  (from {len(combined[combined['label']==cls]):,})")
        else:
            print(f"  Kept    {cls:<14}: {len(grp):>8,}  (all)")
        balanced_frames.append(grp)

    balanced = pd.concat(balanced_frames, ignore_index=True).sample(
        frac=1, random_state=args.seed
    )

    print(f"\n  Balanced total: {len(balanced):,}")
    print(f"  Final label distribution:")
    for lbl, cnt in balanced["label"].value_counts().items():
        pct = cnt / len(balanced) * 100
        print(f"    {lbl:<14}: {cnt:>8,}  ({pct:.1f}%)")

    # ── Validate numeric ranges ────────────────────────────────────────
    remaining_nan = balanced[numeric_features].isna().sum().sum()
    remaining_inf = np.isinf(balanced[numeric_features].values).sum()
    print(f"\n  Remaining NaN : {remaining_nan}")
    print(f"  Remaining Inf : {remaining_inf}")
    if remaining_nan > 0 or remaining_inf > 0:
        print("  → Dropping remaining bad rows ...")
        balanced = balanced.replace([np.inf, -np.inf], np.nan)
        balanced = balanced.dropna(subset=numeric_features)
        print(f"  Clean total   : {len(balanced):,}")

    # ── Stratified 80/20 split ─────────────────────────────────────────
    train_df, test_df = train_test_split(
        balanced,
        test_size=0.20,
        random_state=args.seed,
        stratify=balanced["label"],
    )

    print(f"\n  Train rows : {len(train_df):,}")
    print(f"  Test rows  : {len(test_df):,}")
    print(f"\n  Train label distribution:")
    for lbl, cnt in train_df["label"].value_counts().items():
        print(f"    {lbl:<14}: {cnt:>8,}")
    print(f"\n  Test label distribution:")
    for lbl, cnt in test_df["label"].value_counts().items():
        print(f"    {lbl:<14}: {cnt:>8,}")

    if args.dry_run:
        print("\n[DRY RUN] Files not written.")
        return

    # ── Write outputs ──────────────────────────────────────────────────
    os.makedirs(DATA_DIR, exist_ok=True)
    train_df.to_csv(TRAIN_OUT, index=False)
    test_df.to_csv(TEST_OUT, index=False)

    train_md5 = file_md5(TRAIN_OUT)
    test_md5  = file_md5(TEST_OUT)

    print(f"\n  ✅ Written: {TRAIN_OUT}")
    print(f"     MD5: {train_md5}")
    print(f"  ✅ Written: {TEST_OUT}")
    print(f"     MD5: {test_md5}")

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Classes  : {sorted(balanced['label'].unique().tolist())}")
    print(f"  Train    : {len(train_df):,} rows")
    print(f"  Test     : {len(test_df):,} rows")
    print(f"  Generated: {datetime.utcnow().isoformat()}Z")
    print("\n  Next: python model/train_model.py")
    print("        python train_anomaly.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CIC-IDS-2017 → 27-feature pipeline")
    parser.add_argument("--samples-per-class", type=int, default=50_000,
                        help="Max rows per attack class (default 50000)")
    parser.add_argument("--normal-samples", type=int, default=100_000,
                        help="Max normal rows (default 100000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default 42)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show stats without writing files")
    args = parser.parse_args()
    main(args)
