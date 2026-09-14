import os
import pandas as pd


DATA_PATH = os.path.join(
    "data",
    "live_flows.csv"
)

print("==============================================")
print("          CLEANING LIVE IDS DATASET")
print("==============================================")

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"Dataset not found: {DATA_PATH}"
    )

df = pd.read_csv(DATA_PATH)

print(f"\nOriginal samples: {len(df)}")

print("\nOriginal label distribution:")
print(df["label"].value_counts(dropna=False))


# ------------------------------------------------
# Identify the ports used by our controlled probe
# experiment.
# ------------------------------------------------

probe_ports = set(
    range(8000, 8050)
)


# ------------------------------------------------
# Keep all non-Probe samples.
# For Probe samples, keep ONLY flows that actually
# involve one of the intentionally probed ports.
# ------------------------------------------------

is_probe = (
    df["label"]
    .astype(str)
    .str.strip()
    .str.lower()
    == "probe"
)

source_port = pd.to_numeric(
    df["source_port"],
    errors="coerce"
)

destination_port = pd.to_numeric(
    df["destination_port"],
    errors="coerce"
)

verified_probe = (
    source_port.isin(probe_ports)
    | destination_port.isin(probe_ports)
)

keep_rows = (
    ~is_probe
    | verified_probe
)

clean_df = df.loc[keep_rows].copy()


# ------------------------------------------------
# Overwrite the dataset with the cleaned version.
# ------------------------------------------------

# ------------------------------------------------
# Remove unlabeled samples from the training
# dataset.
#
# Unlabeled traffic is NOT automatically normal.
# We preserve the original cleaned capture as a
# separate file for future analysis.
# ------------------------------------------------

ARCHIVE_PATH = os.path.join(
    "data",
    "live_flows_unlabeled.csv"
)

unlabeled_rows = clean_df[
    clean_df["label"].isna()
    | (
        clean_df["label"]
        .astype(str)
        .str.strip()
        == ""
    )
].copy()

labeled_df = clean_df[
    ~(
        clean_df["label"].isna()
        | (
            clean_df["label"]
            .astype(str)
            .str.strip()
            == ""
        )
    )
].copy()


# Preserve unlabeled traffic separately.
if not unlabeled_rows.empty:
    unlabeled_rows.to_csv(
        ARCHIVE_PATH,
        index=False
    )


# The main dataset now contains ONLY samples with
# verified ground-truth labels.
labeled_df.to_csv(
    DATA_PATH,
    index=False
)

clean_df = labeled_df

removed = len(df) - len(clean_df)

print("\n==============================================")
print("              CLEANUP COMPLETE")
print("==============================================")

print(f"\nOriginal samples: {len(df)}")
print(f"Removed samples:  {removed}")
print(f"Remaining samples: {len(clean_df)}")

print("\nClean label distribution:")
print(clean_df["label"].value_counts(dropna=False))

print("\nVerified Probe samples:")
print(
    (
        clean_df["label"]
        .astype(str)
        .str.strip()
        .str.lower()
        == "probe"
    ).sum()
)

print("\n✅ Dataset cleaned successfully.")