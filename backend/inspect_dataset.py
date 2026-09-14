import os
import pandas as pd


DATA_PATH = os.path.join(
    "data",
    "live_flows.csv"
)

print("==============================================")
print("          LIVE IDS DATASET INSPECTION")
print("==============================================")

df = pd.read_csv(DATA_PATH)

print(f"\nTotal samples: {len(df)}")

print("\nLabel distribution:")
print(df["label"].value_counts())


# ------------------------------------------------
# Basic statistics for every numeric feature
# ------------------------------------------------

numeric_columns = [
    column
    for column in df.columns
    if column not in ["protocol", "label"]
]

print("\n==============================================")
print("          NUMERIC FEATURE STATISTICS")
print("==============================================")

print(
    df.groupby("label")[numeric_columns]
    .agg(["mean", "median"])
    .round(3)
    .to_string()
)


# ------------------------------------------------
# Protocol distribution by class
# ------------------------------------------------

print("\n==============================================")
print("             PROTOCOL DISTRIBUTION")
print("==============================================")

print(
    pd.crosstab(
        df["label"],
        df["protocol"]
    )
)


# ------------------------------------------------
# Port statistics
# ------------------------------------------------

print("\n==============================================")
print("               PORT STATISTICS")
print("==============================================")

for label in df["label"].unique():

    subset = df[df["label"] == label]

    print(f"\n--- {label} ---")

    print(
        "Source ports:",
        subset["source_port"]
        .value_counts()
        .head(10)
        .to_dict()
    )

    print(
        "Destination ports:",
        subset["destination_port"]
        .value_counts()
        .head(10)
        .to_dict()
    )


# ------------------------------------------------
# Check for constant features
# ------------------------------------------------

print("\n==============================================")
print("             CONSTANT FEATURES")
print("==============================================")

constant_features = []

for column in numeric_columns:

    if df[column].nunique() <= 1:
        constant_features.append(column)

if constant_features:
    for column in constant_features:
        print(f"- {column}")
else:
    print("None")


# ------------------------------------------------
# Check missing values
# ------------------------------------------------

print("\n==============================================")
print("               MISSING VALUES")
print("==============================================")

missing = df.isna().sum()

missing = missing[missing > 0]

if len(missing) == 0:
    print("None")
else:
    print(missing)


print("\n==============================================")
print("                  COMPLETE")
print("==============================================")