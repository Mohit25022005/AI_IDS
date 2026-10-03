"""
Tests for feature schema validation and preprocessing utilities.
"""
import pytest
from utils.preprocessing import (
    LIVE_FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    CATEGORICAL_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    validate_feature_dict,
    validate_dataframe_schema,
)


class TestSchemaConstants:
    def test_total_feature_count(self):
        assert len(LIVE_FEATURE_COLUMNS) == 27

    def test_protocol_is_categorical(self):
        assert "protocol" in CATEGORICAL_COLUMNS
        assert "protocol" not in NUMERIC_COLUMNS

    def test_numeric_count(self):
        assert len(NUMERIC_COLUMNS) == 26

    def test_schema_version_set(self):
        assert FEATURE_SCHEMA_VERSION == "v2"

    def test_no_duplicate_columns(self):
        assert len(LIVE_FEATURE_COLUMNS) == len(set(LIVE_FEATURE_COLUMNS))

    def test_column_order_stable(self):
        # First and last columns must be stable — training depends on order
        assert LIVE_FEATURE_COLUMNS[0]  == "duration"
        assert LIVE_FEATURE_COLUMNS[-1] == "protocol"


class TestValidateFeatureDict:
    def test_valid_features_returns_no_errors(self, normal_features):
        errors = validate_feature_dict(normal_features)
        assert errors == []

    def test_missing_feature_detected(self, normal_features):
        bad = {k: v for k, v in normal_features.items() if k != "duration"}
        errors = validate_feature_dict(bad)
        assert any("duration" in e for e in errors)

    def test_extra_feature_detected(self, normal_features):
        bad = {**normal_features, "unknown_column": 99}
        errors = validate_feature_dict(bad)
        assert any("unknown_column" in e for e in errors)

    def test_non_numeric_value_detected(self, normal_features):
        bad = {**normal_features, "duration": "not_a_number"}
        errors = validate_feature_dict(bad)
        assert any("duration" in e for e in errors)

    def test_invalid_protocol_detected(self, normal_features):
        bad = {**normal_features, "protocol": "icmp"}
        errors = validate_feature_dict(bad)
        assert any("protocol" in e for e in errors)

    def test_valid_protocols(self, normal_features):
        for proto in ("tcp", "udp", "other"):
            feat = {**normal_features, "protocol": proto}
            assert validate_feature_dict(feat) == []

    def test_uppercase_protocol_rejected(self, normal_features):
        bad = {**normal_features, "protocol": "TCP"}
        errors = validate_feature_dict(bad)
        assert any("protocol" in e for e in errors)


class TestValidateDataframeSchema:
    def test_valid_dataframe(self, normal_features):
        import pandas as pd
        df = pd.DataFrame([normal_features])
        errors = validate_dataframe_schema(df)
        assert errors == []

    def test_missing_column_detected(self, normal_features):
        import pandas as pd
        bad = {k: v for k, v in normal_features.items() if k != "syn_count"}
        df = pd.DataFrame([bad])
        errors = validate_dataframe_schema(df)
        assert any("syn_count" in e for e in errors)

    def test_label_column_allowed(self, normal_features):
        import pandas as pd
        feat_with_label = {**normal_features, "label": "normal"}
        df = pd.DataFrame([feat_with_label])
        errors = validate_dataframe_schema(df)
        assert errors == []
