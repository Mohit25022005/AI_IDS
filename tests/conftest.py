"""
Pytest configuration and shared fixtures for Cloud-RT-IDS tests.
"""
import sys
import os
import pytest

# Make backend importable without installing it as a package
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))


# ── Minimal valid feature dict ────────────────────────────────────
VALID_NORMAL_FEATURES = {
    "duration":               1.5,
    "source_port":            54321,
    "destination_port":       80,
    "forward_packets":        10,
    "backward_packets":       8,
    "forward_bytes":          8000,
    "backward_bytes":         3200,
    "total_packets":          18,
    "total_bytes":            11200,
    "packets_per_second":     12.0,
    "bytes_per_second":       7466.67,
    "mean_packet_size":       622.22,
    "min_packet_size":        40.0,
    "max_packet_size":        1500.0,
    "packet_size_std":        420.0,
    "syn_count":              1,
    "ack_count":              15,
    "fin_count":              1,
    "rst_count":              0,
    "psh_count":              3,
    "forward_packet_ratio":   0.556,
    "backward_packet_ratio":  0.444,
    "forward_byte_ratio":     0.714,
    "backward_byte_ratio":    0.286,
    "syn_ratio":              0.056,
    "rst_ratio":              0.0,
    "protocol":               "tcp",
}

VALID_PROBE_FEATURES = {
    "duration":               0.05,
    "source_port":            50000,
    "destination_port":       8000,
    "forward_packets":        1,
    "backward_packets":       1,
    "forward_bytes":          56,
    "backward_bytes":         44,
    "total_packets":          2,
    "total_bytes":            100,
    "packets_per_second":     40.0,
    "bytes_per_second":       2000.0,
    "mean_packet_size":       50.0,
    "min_packet_size":        44.0,
    "max_packet_size":        56.0,
    "packet_size_std":        6.0,
    "syn_count":              1,
    "ack_count":              1,
    "fin_count":              0,
    "rst_count":              1,
    "psh_count":              0,
    "forward_packet_ratio":   0.5,
    "backward_packet_ratio":  0.5,
    "forward_byte_ratio":     0.56,
    "backward_byte_ratio":    0.44,
    "syn_ratio":              0.5,
    "rst_ratio":              0.5,
    "protocol":               "tcp",
}


@pytest.fixture(scope="session")
def normal_features():
    return VALID_NORMAL_FEATURES.copy()


@pytest.fixture(scope="session")
def probe_features():
    return VALID_PROBE_FEATURES.copy()
