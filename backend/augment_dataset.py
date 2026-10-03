"""
Cloud-RT-IDS  ·  Dataset Augmentation Script
=============================================
Appends synthetic dos / r2l / u2r flows to:
  - data/live_flows.csv   (training set)
  - data/test_flows.csv   (independent test set)

Uses the same simulator.py profiles already used by the API, so
training and inference distributions are consistent.

Counts chosen to keep the dataset reasonably balanced while giving
each new class enough samples for reliable stratified splits:
  - dos  : 200 train / 90 test
  - r2l  : 150 train / 65 test
  - u2r  : 100 train / 45 test

Run from the backend/ directory:
    python augment_dataset.py
or with --dry-run to preview counts without writing.
"""

import argparse
import os
import sys
import pandas as pd

# Make sure we can import simulator from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulator import generate_synthetic_flows, LIVE_FEATURE_COLUMNS

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TRAIN_PATH = os.path.join(DATA_DIR, "live_flows.csv")
TEST_PATH  = os.path.join(DATA_DIR, "test_flows.csv")

# ---------------------------------------------------------------------------
# How many synthetic rows to inject per class per split
# ---------------------------------------------------------------------------
AUGMENT_COUNTS = {
    "dos": {"train": 200, "test": 90},
    "r2l": {"train": 150, "test": 65},
    "u2r": {"train": 100, "test": 45},
}

# Fixed seeds so results are reproducible
SEEDS = {
    "dos": {"train": 101, "test": 102},
    "r2l": {"train": 201, "test": 202},
    "u2r": {"train": 301, "test": 302},
}


def build_rows(attack_class: str, count: int, seed: int) -> pd.DataFrame:
    """Generate `count` synthetic flows and return as a labelled DataFrame."""
    flows = generate_synthetic_flows(attack_class, count=count, seed=seed)
    df = pd.DataFrame(flows, columns=LIVE_FEATURE_COLUMNS)
    df["label"] = attack_class
    return df


def augment_file(path: str, split: str, dry_run: bool = False) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")

    existing = pd.read_csv(path)
    print(f"\n{'─'*55}")
    print(f"  {split.upper()} → {path}")
    print(f"  Existing rows: {len(existing)}")
    print(f"  Existing labels:\n{existing['label'].value_counts().to_string()}")

    new_frames = []
    for cls, counts in AUGMENT_COUNTS.items():
        n = counts[split]
        seed = SEEDS[cls][split]
        chunk = build_rows(cls, n, seed)
        new_frames.append(chunk)
        print(f"  + {n:>4} synthetic '{cls}' rows (seed={seed})")

    combined = pd.concat([existing] + new_frames, ignore_index=True)
    print(f"\n  Total rows after augmentation: {len(combined)}")
    print(f"  Final label distribution:\n{combined['label'].value_counts().to_string()}")

    if not dry_run:
        combined.to_csv(path, index=False)
        print(f"  ✅ Written to {path}")
    else:
        print(f"  [DRY RUN] No file written.")


def main():
    parser = argparse.ArgumentParser(
        description="Augment IDS datasets with synthetic dos/r2l/u2r flows."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing files."
    )
    args = parser.parse_args()

    print("\n" + "="*55)
    print("  CLOUD-RT-IDS  ·  DATASET AUGMENTATION")
    print("="*55)

    augment_file(TRAIN_PATH, "train", dry_run=args.dry_run)
    augment_file(TEST_PATH,  "test",  dry_run=args.dry_run)

    if not args.dry_run:
        print("\n✅ Augmentation complete. Run train_model.py to retrain.")
    else:
        print("\n[DRY RUN] No files were modified.")


if __name__ == "__main__":
    main()
