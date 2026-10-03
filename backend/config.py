"""
config.py — Central configuration for the ML-Powered Compiler Optimization Advisor.
All tunable parameters are defined here so that no magic numbers appear in the codebase.
"""

import os

# ---------------------------------------------------------------------------
# Base Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.join(BASE_DIR, "ml")
DATA_DIR = os.path.join(ML_DIR, "data")
MODELS_DIR = os.path.join(ML_DIR, "saved_models")

MODEL_PATH = os.path.join(MODELS_DIR, "optimizer_model.pkl")
METRICS_PATH = os.path.join(MODELS_DIR, "model_metrics.json")
DATASET_PATH = os.path.join(DATA_DIR, "dataset.csv")
TEST_PROGRAMS_DIR = os.path.join(DATA_DIR, "test_programs")

# ---------------------------------------------------------------------------
# ML Configuration
# ---------------------------------------------------------------------------

# Confidence threshold: ML pass is applied only if confidence >= this value
ML_CONFIDENCE_THRESHOLD = 0.50

# Random seed for reproducible dataset generation and model training
RANDOM_SEED = 42

# Train/test split ratio
TRAIN_TEST_SPLIT = 0.80          # 80% train, 20% test

# Number of synthetic programs to generate for training
DATASET_SIZE = 600               # results in ~480 train / ~120 test

# Random Forest parameters
RF_N_ESTIMATORS = 100
RF_MAX_DEPTH = None              # Grow full trees (let RF regularize via ensembling)

# ---------------------------------------------------------------------------
# Optimization Passes — Canonical Names
# ---------------------------------------------------------------------------
OPTIMIZATION_PASSES = [
    "CONSTANT_FOLDING",
    "CONSTANT_PROPAGATION",
    "CSE",
    "DEAD_CODE_ELIMINATION",
    "STRENGTH_REDUCTION",
]

# Fixed safe application order (must not change without updating optimizer.py)
PASS_APPLICATION_ORDER = [
    "CONSTANT_FOLDING",          # 1st: fold constants before propagating
    "CONSTANT_PROPAGATION",      # 2nd: propagate now-known constants
    "CSE",                       # 3rd: eliminate repeated subexpressions
    "DEAD_CODE_ELIMINATION",     # 4th: clean up dead temporaries
    "STRENGTH_REDUCTION",        # 5th: structural substitutions last
]

# ---------------------------------------------------------------------------
# Flask Configuration
# ---------------------------------------------------------------------------
FLASK_DEBUG = True
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# ---------------------------------------------------------------------------
# Feature Names (must match feature_extractor.py output order)
# ---------------------------------------------------------------------------
FEATURE_NAMES = [
    "num_loops",
    "loop_depth_max",
    "num_functions",
    "num_assignments",
    "num_branches",
    "tac_total_instructions",
    "temp_var_count",
    "const_literal_count",
    "add_op_count",
    "mul_op_count",
    "div_op_count",
    "num_unique_vars",
    "repeated_rhs_count",
    "mul_by_power_of_2",
    "single_use_temp_count",
]
