"""
Cloud-RT-IDS  ·  Synthetic Traffic Simulator
=============================================
Generates synthetic network flow feature vectors that approximate the
statistical characteristics of different traffic classes.

These are NOT real captured flows — they are produced by sampling from
distributions fitted to the project's live_flows.csv dataset, supplemented
by domain knowledge for classes not yet collected (DoS, R2L, U2R).

All generated flows are clearly tagged as "synthetic" in API responses.

Classes supported
-----------------
  normal   - Legitimate background application traffic
  probe    - Port-scan / service enumeration
  dos      - Denial-of-service (high-rate flooding)
  r2l      - Remote-to-local (small asymmetric flows, data exfiltration)
  u2r      - User-to-root (low-volume privilege escalation)

Usage
-----
  from simulator import generate_synthetic_flows
  flows = generate_synthetic_flows("dos", count=10)
  # returns list of 27-feature dicts matching LIVE_FEATURE_COLUMNS
"""

import random
import numpy as np
from typing import List, Dict, Any

# ------------------------------------------------------------------
# Feature schema  (must match LIVE_FEATURE_COLUMNS in app.py)
# ------------------------------------------------------------------
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

SUPPORTED_CLASSES = {"normal", "probe", "dos", "ddos", "r2l", "bot", "web_attack"}


# ------------------------------------------------------------------
# Per-class statistical profiles
# Each profile drives the sampling distributions.
# Values are approximate and based on network intrusion research +
# observed patterns in the project's live_flows.csv.
# ------------------------------------------------------------------
_PROFILES: Dict[str, Dict[str, Any]] = {

    "normal": {
        "description": "Legitimate background/application traffic",
        "duration_range":      (0.01, 5.0),
        "src_port_range":      (49152, 65535),   # ephemeral
        "dst_port_common":     [80, 443, 8080, 53, 22, 3306, 5432],
        "fwd_packets_range":   (2, 50),
        "fwd_bwd_ratio":       (0.4, 0.7),       # close to symmetric
        "packet_size_range":   (60, 1500),
        "syn_per_flow":        (0, 1),
        "ack_per_flow":        (1, 40),
        "fin_per_flow":        (0, 2),
        "rst_per_flow":        (0, 1),
        "psh_per_flow":        (0, 10),
        "protocols":           ["tcp", "udp"],
        "protocol_weights":    [0.70, 0.30],
    },

    "probe": {
        "description": "Port-scan / service enumeration (like controlled localhost probe)",
        "duration_range":      (0.001, 0.2),     # very short flows
        "src_port_range":      (49152, 65535),
        "dst_port_common":     list(range(8000, 8050)) + [22, 23, 25, 80, 443, 3389],
        "fwd_packets_range":   (1, 3),
        "fwd_bwd_ratio":       (0.4, 0.6),
        "packet_size_range":   (40, 80),          # small SYN/RST packets
        "syn_per_flow":        (1, 2),
        "ack_per_flow":        (0, 1),
        "fin_per_flow":        (0, 1),
        "rst_per_flow":        (1, 2),            # closed-port RST response
        "psh_per_flow":        (0, 0),
        "protocols":           ["tcp"],
        "protocol_weights":    [1.0],
    },

    "dos": {
        "description": "Denial-of-service flooding attack",
        "duration_range":      (0.001, 1.0),     # short high-rate bursts
        "src_port_range":      (1024, 65535),
        "dst_port_common":     [80, 443, 53, 22, 3389],
        "fwd_packets_range":   (50, 2000),        # high packet count
        "fwd_bwd_ratio":       (0.85, 1.0),       # highly asymmetric fwd
        "packet_size_range":   (40, 200),          # small spoofed packets
        "syn_per_flow":        (50, 2000),         # SYN flood
        "ack_per_flow":        (0, 5),
        "fin_per_flow":        (0, 2),
        "rst_per_flow":        (0, 5),
        "psh_per_flow":        (0, 0),
        "protocols":           ["tcp", "udp"],
        "protocol_weights":    [0.60, 0.40],
    },

    "r2l": {
        "description": "Remote-to-local — small asymmetric exfiltration flows",
        "duration_range":      (0.5, 30.0),      # sustained session
        "src_port_range":      (1024, 65535),
        "dst_port_common":     [21, 22, 23, 25, 80, 110, 143, 445],
        "fwd_packets_range":   (3, 20),
        "fwd_bwd_ratio":       (0.1, 0.35),      # much more backward traffic
        "packet_size_range":   (60, 600),
        "syn_per_flow":        (0, 1),
        "ack_per_flow":        (2, 20),
        "fin_per_flow":        (0, 2),
        "rst_per_flow":        (0, 1),
        "psh_per_flow":        (1, 15),
        "protocols":           ["tcp"],
        "protocol_weights":    [1.0],
    },

    "ddos": {
        "description": "Distributed Denial-of-Service — high-volume multi-source flood",
        "duration_range":      (0.001, 0.5),
        "src_port_range":      (1024, 65535),
        "dst_port_common":     [80, 443, 53],
        "fwd_packets_range":   (200, 5000),
        "fwd_bwd_ratio":       (0.95, 1.0),
        "packet_size_range":   (40, 120),
        "syn_per_flow":        (0, 5),
        "ack_per_flow":        (0, 2),
        "fin_per_flow":        (0, 1),
        "rst_per_flow":        (0, 3),
        "psh_per_flow":        (0, 0),
        "protocols":           ["tcp", "udp"],
        "protocol_weights":    [0.40, 0.60],
    },

    "bot": {
        "description": "Botnet C&C communication — periodic low-volume beaconing",
        "duration_range":      (0.5, 10.0),
        "src_port_range":      (1024, 65535),
        "dst_port_common":     [80, 443, 6667, 8080, 1080],
        "fwd_packets_range":   (3, 25),
        "fwd_bwd_ratio":       (0.45, 0.60),
        "packet_size_range":   (60, 400),
        "syn_per_flow":        (0, 1),
        "ack_per_flow":        (2, 24),
        "fin_per_flow":        (0, 2),
        "rst_per_flow":        (0, 1),
        "psh_per_flow":        (1, 12),
        "protocols":           ["tcp"],
        "protocol_weights":    [1.0],
    },

    "web_attack": {
        "description": "Web attacks — brute force, XSS, SQL injection",
        "duration_range":      (0.01, 5.0),
        "src_port_range":      (1024, 65535),
        "dst_port_common":     [80, 443, 8080, 8443],
        "fwd_packets_range":   (2, 30),
        "fwd_bwd_ratio":       (0.50, 0.75),
        "packet_size_range":   (200, 1400),
        "syn_per_flow":        (0, 1),
        "ack_per_flow":        (1, 29),
        "fin_per_flow":        (0, 2),
        "rst_per_flow":        (0, 1),
        "psh_per_flow":        (1, 20),
        "protocols":           ["tcp"],
        "protocol_weights":    [1.0],
    },
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _generate_one(traffic_class: str, rng: random.Random) -> Dict[str, Any]:
    """Generate a single synthetic flow feature vector for the given class."""
    p = _PROFILES[traffic_class]

    # --- Core dimensions ---
    protocol   = rng.choices(p["protocols"], weights=p["protocol_weights"])[0]
    duration   = round(_clamp(rng.uniform(*p["duration_range"]), 0.001, 3600.0), 6)
    src_port   = rng.randint(*p["src_port_range"])
    dst_port   = rng.choice(p["dst_port_common"])
    fwd_pkts   = rng.randint(*p["fwd_packets_range"])

    # Backward packets derived from fwd ratio
    fwd_ratio  = rng.uniform(*p["fwd_bwd_ratio"])
    bwd_pkts   = max(1, int(round(fwd_pkts * (1 - fwd_ratio) / fwd_ratio)))

    total_pkts = fwd_pkts + bwd_pkts

    # --- Packet sizes ---
    pkt_size_lo, pkt_size_hi = p["packet_size_range"]
    sizes = [rng.randint(pkt_size_lo, pkt_size_hi) for _ in range(total_pkts)]
    total_bytes = sum(sizes)
    fwd_bytes   = int(total_bytes * fwd_ratio)
    bwd_bytes   = total_bytes - fwd_bytes

    mean_pkt  = round(total_bytes / total_pkts, 3)
    min_pkt   = float(min(sizes))
    max_pkt   = float(max(sizes))
    std_pkt   = round(float(np.std(sizes)), 3) if len(sizes) > 1 else 0.0

    # --- Rates ---
    pps = round(total_pkts / duration, 3)
    bps = round(total_bytes / duration, 3)

    # --- TCP flags ---
    syn_cnt = rng.randint(*p["syn_per_flow"])
    ack_cnt = rng.randint(*p["ack_per_flow"])
    fin_cnt = rng.randint(*p["fin_per_flow"])
    rst_cnt = rng.randint(*p["rst_per_flow"])
    psh_cnt = rng.randint(*p["psh_per_flow"])

    # For UDP, zero out TCP flags
    if protocol != "tcp":
        syn_cnt = ack_cnt = fin_cnt = rst_cnt = psh_cnt = 0

    # Clamp individual flag counts so ratios stay within [0, 1].
    # syn_ratio = syn_cnt / total_pkts must be <= 1.
    syn_cnt = min(syn_cnt, total_pkts)
    ack_cnt = min(ack_cnt, total_pkts)
    fin_cnt = min(fin_cnt, total_pkts)
    rst_cnt = min(rst_cnt, total_pkts)
    psh_cnt = min(psh_cnt, total_pkts)

    # --- Ratios ---
    fwd_pkt_ratio = round(fwd_pkts / total_pkts, 4)
    bwd_pkt_ratio = round(1.0 - fwd_pkt_ratio, 4)
    fwd_byt_ratio = round(fwd_bytes / total_bytes, 4) if total_bytes > 0 else 0.5
    bwd_byt_ratio = round(1.0 - fwd_byt_ratio, 4)
    syn_ratio_val = round(syn_cnt / total_pkts, 4) if total_pkts > 0 else 0.0
    rst_ratio_val = round(rst_cnt / total_pkts, 4) if total_pkts > 0 else 0.0

    return {
        "duration":              duration,
        "source_port":           src_port,
        "destination_port":      dst_port,
        "forward_packets":       fwd_pkts,
        "backward_packets":      bwd_pkts,
        "forward_bytes":         fwd_bytes,
        "backward_bytes":        bwd_bytes,
        "total_packets":         total_pkts,
        "total_bytes":           total_bytes,
        "packets_per_second":    pps,
        "bytes_per_second":      bps,
        "mean_packet_size":      mean_pkt,
        "min_packet_size":       min_pkt,
        "max_packet_size":       max_pkt,
        "packet_size_std":       std_pkt,
        "syn_count":             syn_cnt,
        "ack_count":             ack_cnt,
        "fin_count":             fin_cnt,
        "rst_count":             rst_cnt,
        "psh_count":             psh_cnt,
        "forward_packet_ratio":  fwd_pkt_ratio,
        "backward_packet_ratio": bwd_pkt_ratio,
        "forward_byte_ratio":    fwd_byt_ratio,
        "backward_byte_ratio":   bwd_byt_ratio,
        "syn_ratio":             syn_ratio_val,
        "rst_ratio":             rst_ratio_val,
        "protocol":              protocol,
    }


def generate_synthetic_flows(
    traffic_class: str,
    count: int = 10,
    seed: int = None,
) -> List[Dict[str, Any]]:
    """
    Generate `count` synthetic flow feature vectors for `traffic_class`.

    Parameters
    ----------
    traffic_class : str
        One of: "normal", "probe", "dos", "r2l", "u2r"
    count : int
        Number of flows to generate (1–500)
    seed : int or None
        Optional random seed for reproducibility

    Returns
    -------
    list of dicts, each with the 27 keys matching LIVE_FEATURE_COLUMNS
    """
    cls = traffic_class.lower().strip()
    if cls not in SUPPORTED_CLASSES:
        raise ValueError(
            f"Unknown class '{cls}'. Supported: {sorted(SUPPORTED_CLASSES)}"
        )

    count = max(1, min(500, count))
    rng = random.Random(seed)
    np.random.seed(seed if seed is not None else 42)

    return [_generate_one(cls, rng) for _ in range(count)]


def describe_classes() -> Dict[str, str]:
    """Return a description of each supported traffic class."""
    return {cls: profile["description"] for cls, profile in _PROFILES.items()}


# ------------------------------------------------------------------
# CLI convenience
# ------------------------------------------------------------------
if __name__ == "__main__":
    import json

    for cls in SUPPORTED_CLASSES:
        flows = generate_synthetic_flows(cls, count=3, seed=42)
        print(f"\n{'='*60}")
        print(f"  CLASS: {cls.upper()}")
        print(f"{'='*60}")
        for i, f in enumerate(flows, 1):
            print(f"\n  Flow {i}:")
            for k, v in f.items():
                print(f"    {k:<30} = {v}")
