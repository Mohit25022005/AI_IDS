"""
Tests for the synthetic traffic simulator.
"""
import pytest
import sys
import os

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from simulator import generate_synthetic_flows, describe_classes, SUPPORTED_CLASSES, LIVE_FEATURE_COLUMNS


class TestSimulatorClasses:
    def test_all_supported_classes_described(self):
        descs = describe_classes()
        for cls in SUPPORTED_CLASSES:
            assert cls in descs

    @pytest.mark.parametrize("cls", list(SUPPORTED_CLASSES))
    def test_generate_returns_correct_count(self, cls):
        flows = generate_synthetic_flows(cls, count=5, seed=42)
        assert len(flows) == 5

    @pytest.mark.parametrize("cls", list(SUPPORTED_CLASSES))
    def test_generated_flow_has_all_features(self, cls):
        flows = generate_synthetic_flows(cls, count=1, seed=42)
        assert len(flows) == 1
        flow = flows[0]
        for col in LIVE_FEATURE_COLUMNS:
            assert col in flow, f"Missing feature '{col}' for class '{cls}'"

    @pytest.mark.parametrize("cls", list(SUPPORTED_CLASSES))
    def test_protocol_is_valid(self, cls):
        flows = generate_synthetic_flows(cls, count=10, seed=42)
        for f in flows:
            assert f["protocol"] in ("tcp", "udp", "other")

    @pytest.mark.parametrize("cls", list(SUPPORTED_CLASSES))
    def test_numeric_features_are_numbers(self, cls):
        flows = generate_synthetic_flows(cls, count=5, seed=42)
        numeric_cols = [c for c in LIVE_FEATURE_COLUMNS if c != "protocol"]
        for f in flows:
            for col in numeric_cols:
                assert isinstance(f[col], (int, float)), \
                    f"Feature '{col}' is not numeric for class '{cls}': {f[col]}"

    def test_unknown_class_raises(self):
        with pytest.raises(ValueError, match="Unknown class"):
            generate_synthetic_flows("unknown_class_xyz", count=1)

    def test_count_clamped_at_500(self):
        flows = generate_synthetic_flows("normal", count=9999, seed=42)
        assert len(flows) == 500

    def test_count_clamped_at_1(self):
        flows = generate_synthetic_flows("normal", count=0, seed=42)
        assert len(flows) == 1

    def test_reproducibility_with_seed(self):
        a = generate_synthetic_flows("probe", count=5, seed=99)
        b = generate_synthetic_flows("probe", count=5, seed=99)
        for fa, fb in zip(a, b):
            assert fa == fb

    @pytest.mark.parametrize("cls", list(SUPPORTED_CLASSES))
    def test_duration_above_floor(self, cls):
        flows = generate_synthetic_flows(cls, count=20, seed=42)
        for f in flows:
            assert f["duration"] >= 0.001, \
                f"Duration below 1ms floor for class '{cls}': {f['duration']}"

    @pytest.mark.parametrize("cls", list(SUPPORTED_CLASSES))
    def test_ratios_in_range(self, cls):
        flows = generate_synthetic_flows(cls, count=10, seed=42)
        ratio_cols = [
            "forward_packet_ratio", "backward_packet_ratio",
            "forward_byte_ratio", "backward_byte_ratio",
            "syn_ratio", "rst_ratio",
        ]
        for f in flows:
            for col in ratio_cols:
                assert 0.0 <= f[col] <= 1.0, \
                    f"Ratio '{col}' out of [0,1] for class '{cls}': {f[col]}"
