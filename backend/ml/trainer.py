"""
ml/trainer.py — Train and evaluate the MultiOutputClassifier model.

Uses strict 80/20 train/test split on dataset.csv, fits a RandomForest
MultiOutputClassifier, calculates evaluation metrics on the unseen 20% test set,
and saves model.pkl and model_metrics.json.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import joblib
from typing import Dict, Any, Tuple

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import (
    hamming_loss,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DATASET_PATH,
    MODEL_PATH,
    METRICS_PATH,
    MODELS_DIR,
    FEATURE_NAMES,
    TRAIN_TEST_SPLIT,
    RANDOM_SEED,
    RF_N_ESTIMATORS,
    OPTIMIZATION_PASSES,
)
from ml.generate_dataset import LABEL_NAMES


def train_and_evaluate(
    dataset_path: str = DATASET_PATH,
    model_path: str = MODEL_PATH,
    metrics_path: str = METRICS_PATH,
    seed: int = RANDOM_SEED,
) -> Dict[str, Any]:
    """
    Train ML model on dataset and save model .pkl and metrics .json.

    Returns:
        Dict containing training and evaluation metrics.
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found at {dataset_path}. Run generate_dataset.py first.")

    df = pd.read_csv(dataset_path)

    X = df[FEATURE_NAMES]
    Y = df[LABEL_NAMES]

    test_size = 1.0 - TRAIN_TEST_SPLIT
    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=test_size, random_state=seed
    )

    # Base estimator: Random Forest Classifier
    base_rf = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS,
        random_state=seed,
        n_jobs=-1,
    )
    model = MultiOutputClassifier(base_rf)
    model.fit(X_train, Y_train)

    # Predict on test set
    Y_pred = model.predict(X_test)
    Y_pred_df = pd.DataFrame(Y_pred, columns=LABEL_NAMES, index=Y_test.index)

    # Compute overall metrics
    h_loss = float(hamming_loss(Y_test, Y_pred))
    subset_acc = float(accuracy_score(Y_test, Y_pred))

    per_pass_metrics = {}
    for i, (lname, pass_name) in enumerate(zip(LABEL_NAMES, OPTIMIZATION_PASSES)):
        y_true = Y_test[lname]
        y_p = Y_pred_df[lname]

        acc = float(accuracy_score(y_true, y_p))
        prec = float(precision_score(y_true, y_p, zero_division=0))
        rec = float(recall_score(y_true, y_p, zero_division=0))
        f1 = float(f1_score(y_true, y_p, zero_division=0))

        per_pass_metrics[pass_name] = {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
        }

    metrics = {
        "dataset_total_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "train_ratio": TRAIN_TEST_SPLIT,
        "hamming_loss": round(h_loss, 4),
        "exact_match_ratio": round(subset_acc, 4),
        "model_type": "MultiOutputClassifier(RandomForestClassifier)",
        "n_estimators": RF_N_ESTIMATORS,
        "random_seed": seed,
        "per_pass_metrics": per_pass_metrics,
    }

    # Ensure output directories exist
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)

    # Save model and metrics
    joblib.dump(model, model_path)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Model trained successfully! Saved to {model_path}")
    print(f"Test Hamming Loss: {metrics['hamming_loss']}")
    print(f"Test Exact Match Ratio: {metrics['exact_match_ratio']}")

    return metrics


if __name__ == "__main__":
    train_and_evaluate()
