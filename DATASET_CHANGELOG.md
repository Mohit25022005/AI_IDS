# DATASET CHANGELOG

**Project:** Cloud-RT-IDS  
**Document version:** 1.0  
**Date:** 2026-09-23

This document traces every deliberate modification from the original NSL-KDD
dataset to the current project dataset.  Each change is treated as a research
contribution and must not be silently reverted.

---

## Baseline: Original NSL-KDD

The original NSL-KDD dataset (Tavallaee et al., 2009) is an improved version of
the KDD Cup 1999 dataset.

| Property | Value |
|---|---|
| Training samples | 125,973 |
| Test samples | 22,544 |
| Features | 41 (connection-level) |
| Label taxonomy | 1 normal + 22 attack subtypes (grouped into: normal, DoS, Probe, R2L, U2R) |
| Collection method | Simulated network traffic (DARPA 1998/1999) |
| Collection environment | Controlled lab |
| Protocol encoding | Categorical: tcp, udp, icmp |
| Service field | Yes (http, ftp, smtp, …) |
| Flag field | Yes (SF, REJ, RSTO, S0, …) |
| Bytes | src_bytes, dst_bytes only |
| Statistical features | 2-second window counts (count, srv_count, etc.) |
| Difficulty score | Yes (per-sample difficulty rating) |

---

## Change 1 — Complete Feature Schema Replacement

**Type:** Breaking change — incompatible with NSL-KDD 41-feature schema  
**Date introduced:** Initial project development  
**Affects:** All training, inference, preprocessing, and API code

### What changed

The 41-feature NSL-KDD connection-level feature set was replaced with a
27-feature live network flow statistical feature set.

### Why

NSL-KDD features require a 2-second window aggregation, a service lookup table,
and a KDD-specific connection-state flag vocabulary — none of which are available
from raw packet capture without a full IDS sensor implementation.

The 27-feature schema is directly computable from raw packets with zero external
dependencies, making the system genuinely deployable for live capture.

### How

`url_kdd.py` defines a `NetworkFlow` dataclass populated by Scapy's `sniff()`.
`build_feature_vector()` computes all 27 features from the accumulated flow state.

### Feature-by-feature mapping

| NSL-KDD Feature | Replacement / Status |
|---|---|
| duration | ✅ Kept as `duration` (with 1 ms floor) |
| protocol_type | ✅ Kept as `protocol` (tcp/udp/other) |
| service | ❌ Removed — requires port→service lookup; not reliably inferrable |
| flag | ❌ Removed — replaced by individual TCP flag counts (syn_count, ack_count, fin_count, rst_count, psh_count) |
| src_bytes | ✅ Replaced by `forward_bytes` + `backward_bytes` (directional) |
| dst_bytes | ✅ Rolled into `backward_bytes` |
| land | ❌ Removed — irrelevant for loopback testing |
| wrong_fragment | ❌ Removed — requires deep packet inspection |
| urgent | ❌ Removed — URG flag not tracked |
| hot | ❌ Removed — requires semantic analysis of commands |
| num_failed_logins | ❌ Removed — requires application-layer parsing |
| logged_in | ❌ Removed — application-layer signal |
| num_compromised | ❌ Removed — application-layer signal |
| root_shell | ❌ Removed — application-layer signal |
| su_attempted | ❌ Removed — application-layer signal |
| num_root | ❌ Removed — application-layer signal |
| num_file_creations | ❌ Removed — application-layer signal |
| num_shells | ❌ Removed — application-layer signal |
| num_access_files | ❌ Removed — application-layer signal |
| num_outbound_cmds | ❌ Removed — always 0 in NSL-KDD |
| is_host_login | ❌ Removed — always 0 in NSL-KDD |
| is_guest_login | ❌ Removed — application-layer signal |
| count | ✅ Partially replaced by `total_packets` |
| srv_count | ❌ Removed — requires 2-second window aggregation |
| serror_rate | ❌ Removed — requires window aggregation |
| srv_serror_rate | ❌ Removed — requires window aggregation |
| rerror_rate | ❌ Removed — requires window aggregation |
| srv_rerror_rate | ❌ Removed — requires window aggregation |
| same_srv_rate | ❌ Removed — requires window aggregation |
| diff_srv_rate | ❌ Removed — requires window aggregation |
| srv_diff_host_rate | ❌ Removed — requires window aggregation |
| dst_host_count | ❌ Removed — requires connection history table |
| dst_host_srv_count | ❌ Removed — requires connection history table |
| dst_host_same_srv_rate | ❌ Removed — requires connection history table |
| dst_host_diff_srv_rate | ❌ Removed — requires connection history table |
| dst_host_same_src_port_rate | ❌ Removed — requires connection history table |
| dst_host_srv_diff_host_rate | ❌ Removed — requires connection history table |
| dst_host_serror_rate | ❌ Removed — requires connection history table |
| dst_host_srv_serror_rate | ❌ Removed — requires connection history table |
| dst_host_rerror_rate | ❌ Removed — requires connection history table |
| dst_host_srv_rerror_rate | ❌ Removed — requires connection history table |

**New features added (not in NSL-KDD):**

| New Feature | Rationale |
|---|---|
| `forward_packets` | Directional asymmetry is a strong intrusion signal |
| `backward_packets` | As above |
| `total_bytes` | Absolute volume |
| `packets_per_second` | Rate-based detection of flooding |
| `bytes_per_second` | Rate-based detection of data exfiltration |
| `mean_packet_size` | Packet size profiling |
| `min_packet_size` | Detects SYN-only probes (small fixed-size) |
| `max_packet_size` | Detects large-payload attacks |
| `packet_size_std` | Variance in packet sizes distinguishes traffic types |
| `syn_count` | Raw SYN count (probe/DoS signal) |
| `ack_count` | Established-connection signal |
| `fin_count` | Orderly teardown count |
| `rst_count` | Forced teardown (port-closed signal for probing) |
| `psh_count` | Data-push signal |
| `forward_packet_ratio` | Directional symmetry ratio |
| `backward_packet_ratio` | As above |
| `forward_byte_ratio` | Byte-level directional asymmetry |
| `backward_byte_ratio` | As above |
| `syn_ratio` | Proportion of flow that is SYN |
| `rst_ratio` | Proportion of flow that is RST |

**Expected impact:** Features are directly computable from packets without
external dependencies. The tradeoff is loss of historical/window features that
NSL-KDD provides but that require a stateful sensor. The new features are better
suited to real-time single-flow classification.

**Actual impact:** Measured independently on `test_flows.csv` — see
`backend/model/metrics_all.json` after running `train_model.py`.

**Risks:** Removing window-based statistical features reduces ability to detect
slow attacks (e.g., slow HTTP DoS). Current schema is optimised for
port-scan/probe detection.

---

## Change 2 — Label Taxonomy Reduction

**Type:** Scoping decision  
**Date introduced:** Initial project development

### What changed

NSL-KDD contains 5 high-level classes (normal, DoS, Probe, R2L, U2R) across
22 specific attack subtypes. The current dataset uses **binary** labels:
`normal` and `probe`.

### Why

The live capture environment (Windows loopback) makes it difficult to safely
generate real DoS, R2L, or U2R traffic. The controlled port-scan experiment
provides clean Probe ground truth without requiring network access to external
systems.

### Expected impact

Simplifies the classification problem. Accuracy on the binary task is expected
to be high given the distinctive port-scan pattern. Multi-class performance
cannot be assessed until additional labeled traffic is collected.

### Risks

The high reported accuracy (~98%) is likely inflated by the controlled,
repetitive nature of the Probe traffic. Results should not be generalised.

---

## Change 3 — Collection Method

**Type:** Fundamental architectural change

### What changed

NSL-KDD was collected in a simulated lab environment (DARPA 1998/1999) using
a full network segment with diverse attack tooling. The current dataset is
collected **live** on the developer machine's loopback interface.

### Why

Live capture demonstrates a deployable IDS pipeline that can run on real traffic,
rather than replicating results on an aging benchmark dataset.

### Risks

- Loopback traffic lacks realistic network diversity
- Probe patterns are uniform (same port range, same timing)
- Dataset size is orders of magnitude smaller than NSL-KDD

---

## Change 4 — Dataset Size Reduction

**Type:** Practical limitation

| Metric | NSL-KDD | Current |
|---|---|---|
| Training samples | 125,973 | ~115 |
| Test samples | 22,544 | ~52 |
| Ratio | 1× | 0.09% of NSL-KDD |

### Why

Collection requires manual sessions. The project demonstrates the pipeline
architecture rather than claiming production-scale evaluation.

### Expected impact

Small datasets produce unstable metric estimates. The reported metrics must be
interpreted with this limitation clearly stated.

---

## Change 5 — Duration Floor (v2 schema fix)

**Type:** Bug fix / preprocessing improvement  
**Introduced:** Phase 1 of research upgrade (2026-09-23)

### What changed

A minimum duration of **0.001 seconds (1 ms)** is now enforced in
`url_kdd.py:flow_to_features()` and `calculate_flow_statistics()`.

### Why

Several captured probe flows had durations of 19–38 µs, producing
`packets_per_second` values of 50,000–106,000 and `bytes_per_second` values
exceeding 5,000,000. These outliers distorted the StandardScaler and created
unrealistic feature values.

### Before

```
duration = max(flow.end_time - flow.start_time, 0.0)
# Could produce: packets_per_second = 2 / 0.0000188 = 106,382
```

### After

```
duration = max(flow.end_time - flow.start_time, 0.001)
# Caps: packets_per_second = 2 / 0.001 = 2,000 (max for 2-packet flow)
```

### Expected impact

Reduces extreme rate values; improves StandardScaler quality. Slightly
underestimates true rates for very fast flows but prevents numeric instability.

**⚠️ This change affects computed features. Re-run `train_model.py` after this
change to update model artifacts with the corrected feature distribution.**

---

## Change 6 — Label Normalisation at Write Time

**Type:** Data integrity fix  
**Introduced:** Phase 1 of research upgrade (2026-09-23)

### What changed

`save_flows_to_csv()` in `url_kdd.py` now enforces lowercase labels before
writing to CSV.

### Why

`test_flows.csv` contained title-case labels ("Normal", "Probe") while
`live_flows.csv` contained lowercase labels ("normal", "probe"). The training
script normalised both sets at load time, but the inconsistency was a hidden
dependency that could cause silent bugs if the normalisation was ever bypassed.

### Impact

No model retraining required — the normalisation at the training stage already
handled this. Future captured data will be consistently lowercase at the source.

---

## Summary Table

| Change | Type | Introduced | Re-train Required |
|---|---|---|---|
| 1 — Feature schema replacement (41 → 27) | Architecture | Initial | N/A (original decision) |
| 2 — Label taxonomy reduction (22 → 2) | Scoping | Initial | N/A (original decision) |
| 3 — Live loopback collection | Architecture | Initial | N/A (original decision) |
| 4 — Small dataset size | Practical | Initial | N/A (collection constraint) |
| 5 — Duration floor 1 ms | Bug fix | 2026-09-23 | ✅ Yes |
| 6 — Lowercase labels at write time | Integrity fix | 2026-09-23 | No |

---

*End of DATASET_CHANGELOG.md*
