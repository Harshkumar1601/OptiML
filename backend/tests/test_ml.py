"""
tests/test_ml.py — Unit and integration tests for Phase 5 (ML Engine).

Tests:
  - Feature extraction accuracy and 15-element feature vector formatting
  - Dataset generation file structure and label presence
  - Model training, metrics file, and low test Hamming loss (< 0.05)
  - Predictor load & inference interface
  - Pass recommendation explanations
  - Closed-loop integration: ML model recommendations -> Optimizer execution -> Measured results
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    FEATURE_NAMES,
    OPTIMIZATION_PASSES,
    PASS_APPLICATION_ORDER,
    DATASET_PATH,
    MODEL_PATH,
    METRICS_PATH,
    TEST_PROGRAMS_DIR,
)
from compiler.parser import parse
from compiler.semantic_analyzer import analyze
from compiler.ir_generator import generate
from compiler.optimizer import apply
from ml.feature_extractor import extract_features, get_feature_vector
from ml.generate_dataset import LABEL_NAMES
from ml.model import predict_passes, Predictor
from ml.recommendation import generate_pass_explanations


class TestFeatureExtractor:
    """Test suite for feature extraction."""

    def test_extract_features_keys(self):
        code = "int main() { int x = 2 + 3; return x; }"
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])

        features = extract_features(ir_res["instructions"], ast=p_res["ast_node"])

        assert isinstance(features, dict)
        assert len(features) == 15
        for fname in FEATURE_NAMES:
            assert fname in features

    def test_feature_vector_shape_and_type(self):
        code = "int main() { int x = 10; return x; }"
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])

        features = extract_features(ir_res["instructions"], ast=p_res["ast_node"])
        vec = get_feature_vector(features)

        assert isinstance(vec, np.ndarray)
        assert vec.shape == (15,)
        assert vec.dtype == np.float32

    def test_specific_feature_counts(self):
        code = """
        int main() {
            int x = 2 + 3;
            int y = x * 8;
            int i = 0;
            while (i < 5) {
                i = i + 1;
            }
            return y;
        }
        """
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])
        feats = extract_features(ir_res["instructions"], ast=p_res["ast_node"])

        assert feats["num_loops"] == 1
        assert feats["loop_depth_max"] == 1
        assert feats["const_literal_count"] >= 3   # 2, 3, 8, 0, 5, 1
        assert feats["mul_by_power_of_2"] == 1     # x * 8


class TestDatasetAndTraining:
    """Test suite for dataset file and trained model artifacts."""

    def test_dataset_exists_and_valid(self):
        assert os.path.exists(DATASET_PATH)
        df = pd.read_csv(DATASET_PATH)
        assert len(df) == 600
        assert df.shape[1] == 20   # 15 features + 5 labels

        for fname in FEATURE_NAMES:
            assert fname in df.columns
        for lname in LABEL_NAMES:
            assert lname in df.columns

    def test_model_and_metrics_files_exist(self):
        assert os.path.exists(MODEL_PATH)
        assert os.path.exists(METRICS_PATH)

    def test_model_metrics_quality(self):
        import json
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        assert metrics["dataset_total_samples"] == 600
        assert metrics["train_samples"] == 480
        assert metrics["test_samples"] == 120
        assert metrics["hamming_loss"] < 0.05
        assert metrics["exact_match_ratio"] > 0.85


class TestPredictor:
    """Test suite for ML predictor and pass recommendations."""

    def test_predict_passes_structure(self):
        code = "int main() { int x = 10 + 20; return x; }"
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])

        pred_res = predict_passes(ir_res["instructions"], ast=p_res["ast_node"])

        assert "recommended_passes" in pred_res
        assert "confidences" in pred_res
        assert "features" in pred_res
        assert "details" in pred_res
        assert "model_info" in pred_res

        # Recommended passes should be subset of canonical passes
        for p in pred_res["recommended_passes"]:
            assert p in PASS_APPLICATION_ORDER

    def test_predict_order(self):
        code = "int main() { int x = 2 + 3; int y = x * 4; return y; }"
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])

        pred_res = predict_passes(ir_res["instructions"], ast=p_res["ast_node"])
        recs = pred_res["recommended_passes"]

        # Recommended passes must preserve PASS_APPLICATION_ORDER relative order
        indices = [PASS_APPLICATION_ORDER.index(p) for p in recs]
        assert indices == sorted(indices)

    def test_benchmark_program_recommendations(self):
        # Program with constant folding + strength reduction opportunity
        code = """
        int main() {
            int a = 10 + 20 + 30;
            int b = a * 8;
            return b;
        }
        """
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])
        pred_res = predict_passes(ir_res["instructions"], ast=p_res["ast_node"])

        recs = pred_res["recommended_passes"]
        assert len(recs) >= 1
        assert any(p in recs for p in ["CONSTANT_FOLDING", "CONSTANT_PROPAGATION", "STRENGTH_REDUCTION"])


class TestExplanations:
    """Test suite for recommendation explanations."""

    def test_generate_pass_explanations(self):
        code = "int main() { int x = 5 + 5; return x; }"
        p_res = parse(code)
        ir_res = generate(p_res["ast_node"])
        pred_res = predict_passes(ir_res["instructions"], ast=p_res["ast_node"])

        exps = generate_pass_explanations(pred_res["features"], pred_res)

        assert len(exps) == 5
        for item in exps:
            assert "pass" in item
            assert "confidence" in item
            assert "recommended" in item
            assert "explanation" in item
            assert item["result_type"] == "ESTIMATED"
            assert len(item["explanation"]) > 20


class TestClosedLoopIntegration:
    """Test end-to-end integration: ML recommendations -> Optimizer execution -> Measured results."""

    def test_closed_loop_pipeline(self):
        code = """
        int main() {
            int a = 10 + 20;
            int b = 30 + 40;
            int x = a + b;
            int y = a + b;
            return x + y;
        }
        """
        # 1. Compile
        p_res = parse(code)
        assert p_res["success"]
        ast = p_res["ast_node"]

        s_res = analyze(ast)
        assert s_res["success"]

        ir_res = generate(ast)
        tac = ir_res["instructions"]
        assert len(tac) > 0

        # 2. ML Predict
        pred_res = predict_passes(tac, ast=ast)
        rec_passes = pred_res["recommended_passes"]
        assert len(rec_passes) > 0

        # 3. Optimizer applies ONLY ML-recommended passes
        opt_res = apply(tac, passes=rec_passes)

        # 4. Verification
        assert opt_res.passes_recommended == rec_passes
        assert len(opt_res.passes_applied) > 0
        assert opt_res.stats["result_type"] == "MEASURED"
        assert opt_res.instructions_after != opt_res.instructions_before
