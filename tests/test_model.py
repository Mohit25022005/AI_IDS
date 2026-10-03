"""
Tests for model loading and inference behaviour.
Skipped gracefully when model artifacts are not present
(i.e. before train_model.py has been run).
"""
import os
import pytest
import pandas as pd
import numpy as np

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
MODEL_PATH  = os.path.join(BACKEND_DIR, "model", "model_random_forest.pkl")
LEGACY_PATH = os.path.join(BACKEND_DIR, "model", "model.pkl")

# Use whichever artifact exists
_model_path = MODEL_PATH if os.path.exists(MODEL_PATH) else LEGACY_PATH
MODEL_AVAILABLE = os.path.exists(_model_path)

pytestmark = pytest.mark.skipif(
    not MODEL_AVAILABLE,
    reason="Model artifact not found — run backend/model/train_model.py first",
)


@pytest.fixture(scope="module")
def loaded_model():
    import joblib
    return joblib.load(_model_path)


@pytest.fixture(scope="module")
def feature_columns():
    from utils.preprocessing import LIVE_FEATURE_COLUMNS
    return LIVE_FEATURE_COLUMNS


class TestModelLoading:
    def test_model_loads(self, loaded_model):
        assert loaded_model is not None

    def test_model_has_predict(self, loaded_model):
        assert hasattr(loaded_model, "predict")

    def test_model_has_predict_proba(self, loaded_model):
        assert hasattr(loaded_model, "predict_proba")

    def test_model_has_preprocessor_step(self, loaded_model):
        # sklearn Pipeline should have named_steps
        assert hasattr(loaded_model, "named_steps")
        assert "preprocessor" in loaded_model.named_steps


class TestModelPrediction:
    def test_predict_normal_returns_string(self, loaded_model, feature_columns, normal_features):
        df = pd.DataFrame([normal_features], columns=feature_columns)
        pred = loaded_model.predict(df)
        assert len(pred) == 1
        assert isinstance(str(pred[0]), str)

    def test_predict_returns_known_class(self, loaded_model, feature_columns, normal_features):
        df = pd.DataFrame([normal_features], columns=feature_columns)
        pred = str(loaded_model.predict(df)[0]).lower()
        # Must be one of the classes the model was trained on
        assert pred in {"normal", "probe", "dos", "r2l", "u2r"}

    def test_predict_proba_sums_to_one(self, loaded_model, feature_columns, normal_features):
        df = pd.DataFrame([normal_features], columns=feature_columns)
        proba = loaded_model.predict_proba(df)
        assert proba.shape[0] == 1
        assert abs(proba[0].sum() - 1.0) < 1e-6

    def test_confidence_in_range(self, loaded_model, feature_columns, normal_features):
        df = pd.DataFrame([normal_features], columns=feature_columns)
        proba = loaded_model.predict_proba(df)
        conf = float(np.max(proba))
        assert 0.0 <= conf <= 1.0

    def test_batch_prediction(self, loaded_model, feature_columns, normal_features, probe_features):
        df = pd.DataFrame([normal_features, probe_features], columns=feature_columns)
        preds = loaded_model.predict(df)
        assert len(preds) == 2

    def test_unknown_protocol_handled(self, loaded_model, feature_columns, normal_features):
        """OneHotEncoder handle_unknown='ignore' should not raise."""
        bad = {**normal_features, "protocol": "icmp"}
        df = pd.DataFrame([bad], columns=feature_columns)
        pred = loaded_model.predict(df)
        assert len(pred) == 1

    def test_all_numeric_features_zero(self, loaded_model, feature_columns, normal_features):
        """All-zero numeric features should not raise."""
        zero = {k: (0 if k != "protocol" else "tcp") for k in feature_columns}
        df = pd.DataFrame([zero], columns=feature_columns)
        pred = loaded_model.predict(df)
        assert len(pred) == 1
