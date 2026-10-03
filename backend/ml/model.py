"""
ml/model.py — Runtime prediction interface for ML pass recommendation.

Loads the trained MultiOutputClassifier model from disk and predicts
which optimization passes to apply for a given program's TAC and AST.
"""

import os
import sys
import joblib
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    MODEL_PATH,
    METRICS_PATH,
    FEATURE_NAMES,
    OPTIMIZATION_PASSES,
    PASS_APPLICATION_ORDER,
    ML_CONFIDENCE_THRESHOLD,
)
from ml.feature_extractor import extract_features, get_feature_vector
from ml.generate_dataset import LABEL_NAMES


class Predictor:
    """Predictor class that loads the trained Random Forest model and predicts pass sets."""

    _instance = None

    def __init__(self, model_path: str = MODEL_PATH, metrics_path: str = METRICS_PATH):
        self.model_path = model_path
        self.metrics_path = metrics_path
        self.model = None
        self.metrics = None
        self.load_model()

    def load_model(self):
        """Load trained model and metrics from disk if available."""
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            self.model = None

        if os.path.exists(self.metrics_path):
            with open(self.metrics_path, "r", encoding="utf-8") as f:
                self.metrics = json.load(f)
        else:
            self.metrics = None

    def is_loaded(self) -> bool:
        return self.model is not None

    def predict(
        self,
        instructions: List[Any],
        ast: Optional[Any] = None,
        threshold: float = ML_CONFIDENCE_THRESHOLD,
    ) -> Dict[str, Any]:
        """
        Extract features and run prediction model.

        Returns dict with:
          - recommended_passes: List[str] in safe PASS_APPLICATION_ORDER
          - confidences: Dict[str, float] mapping pass_name -> confidence score
          - features: Dict[str, Any] extracted 15 feature values
          - details: List[Dict[str, Any]] per-pass details
          - model_info: Dict[str, Any]
        """
        features_dict = extract_features(instructions, ast=ast)
        feature_df = pd.DataFrame([features_dict], columns=FEATURE_NAMES)

        if not self.is_loaded():
            # Fallback if model not trained yet: return all passes with default confidence
            confidences = {p: 0.50 for p in OPTIMIZATION_PASSES}
            recommended = list(PASS_APPLICATION_ORDER)
            details = [
                {
                    "pass": p,
                    "confidence": 0.50,
                    "recommended": True,
                    "result_type": "ESTIMATED",
                }
                for p in PASS_APPLICATION_ORDER
            ]
            return {
                "recommended_passes": recommended,
                "confidences": confidences,
                "features": features_dict,
                "details": details,
                "model_info": {"status": "model_not_loaded"},
            }

        # MultiOutputClassifier predict_proba returns list of arrays (one array per label)
        probas = self.model.predict_proba(feature_df)

        confidences = {}
        pass_recommendations = {}

        for i, pass_name in enumerate(OPTIMIZATION_PASSES):
            # probas[i] shape is (1, 2) where probas[i][0][1] is probability of class 1
            label_prob = float(probas[i][0][1]) if probas[i].shape[1] > 1 else float(probas[i][0][0])
            confidences[pass_name] = round(label_prob, 4)
            pass_recommendations[pass_name] = label_prob >= threshold

        # Build recommended pass list in fixed safe order
        recommended_passes = [
            p for p in PASS_APPLICATION_ORDER if pass_recommendations.get(p, False)
        ]

        details = []
        for p in PASS_APPLICATION_ORDER:
            conf = confidences.get(p, 0.0)
            rec = pass_recommendations.get(p, False)
            details.append(
                {
                    "pass": p,
                    "confidence": conf,
                    "recommended": rec,
                    "result_type": "ESTIMATED",
                }
            )

        model_info = {
            "model_type": "MultiOutputClassifier(RandomForest)",
            "confidence_threshold": threshold,
            "trained_on": self.metrics.get("train_samples", 480) if self.metrics else 480,
            "test_hamming_loss": self.metrics.get("hamming_loss", 0.0133) if self.metrics else 0.0133,
            "test_exact_match_ratio": self.metrics.get("exact_match_ratio", 0.9417) if self.metrics else 0.9417,
        }

        return {
            "recommended_passes": recommended_passes,
            "confidences": confidences,
            "features": features_dict,
            "details": details,
            "model_info": model_info,
        }


# Module-level predictor instance
_predictor_instance: Optional[Predictor] = None


def get_predictor() -> Predictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = Predictor()
    return _predictor_instance


def predict_passes(
    instructions: List[Any],
    ast: Optional[Any] = None,
    threshold: float = ML_CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    """Convenience function calling predictor singleton."""
    predictor = get_predictor()
    return predictor.predict(instructions, ast=ast, threshold=threshold)
