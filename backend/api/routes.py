"""
api/routes.py — Flask blueprint defining all REST API routes.

Endpoints:
  GET  /api/health    — Liveness probe
  POST /api/analyze   — Full compiler + ML pipeline (single call, returns everything)
  POST /api/tokenize  — Lexer only
  GET  /api/model     — ML model metadata / evaluation metrics
"""

import json
import os
from flask import Blueprint, jsonify, request

from api.pipeline import run_pipeline
from compiler.lexer import tokenize
import config

api_blueprint = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bad_request(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


def _get_source_code() -> tuple:
    """
    Extract source_code from a JSON request body.
    Returns (source_code, error_response | None).
    """
    if not request.is_json:
        return None, _bad_request("Request Content-Type must be application/json.")

    body = request.get_json(silent=True) or {}
    source_code = body.get("source_code", "").strip()

    if not source_code:
        return None, _bad_request("Missing required field: 'source_code'.")

    return source_code, None


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@api_blueprint.route("/health", methods=["GET"])
def health():
    """Liveness probe — returns 200 when the server is running."""
    model_loaded = os.path.exists(config.MODEL_PATH)
    return jsonify({
        "success": True,
        "status":  "online",
        "message": "ML-Powered Compiler Optimization Advisor API is running.",
        "version": "1.0.0-phase6",
        "model_loaded": model_loaded,
        "passes": config.OPTIMIZATION_PASSES,
    })


# ---------------------------------------------------------------------------
# POST /api/analyze — Full pipeline (main endpoint)
# ---------------------------------------------------------------------------

@api_blueprint.route("/analyze", methods=["POST"])
def analyze():
    """
    Full compiler + ML pipeline.

    Request body (JSON):
      { "source_code": "<C-like source code string>" }

    Response body (JSON):
      Full pipeline response matching architecture_plan_v2.md §10.
      - success: bool
      - source_code: str
      - phases: { tokens, ast, symbol_table, semantic_errors,
                  tac_before, tac_after, ... }
      - ml: { features, recommendations, model_info }
      - stats: { instructions_before, instructions_after,
                 reduction_count, reduction_percent,
                 passes_recommended, passes_applied, result_type }

    On parse/semantic error:
      - success: false
      - error: human-readable description
      - errors: list of error objects
      - phases: partial results collected so far
    """
    source_code, err = _get_source_code()
    if err:
        return err

    try:
        result = run_pipeline(source_code)
        status_code = 200 if result.get("success") else 422
        return jsonify(result), status_code

    except Exception as exc:
        return jsonify({
            "success": False,
            "error":   f"Internal pipeline error: {str(exc)}",
        }), 500


# ---------------------------------------------------------------------------
# POST /api/tokenize — Lexer only
# ---------------------------------------------------------------------------

@api_blueprint.route("/tokenize", methods=["POST"])
def tokenize_only():
    """
    Lex source code and return the token stream.

    Request body (JSON):
      { "source_code": "<C-like source code string>" }

    Response body (JSON):
      {
        "success": bool,
        "tokens": [ {"type": str, "value": str, "line": int, "column": int}, ... ],
        "errors": [ ... ]
      }
    """
    source_code, err = _get_source_code()
    if err:
        return err

    try:
        result = tokenize(source_code)
        return jsonify({
            "success": len(result.get("errors", [])) == 0,
            "tokens":  result.get("tokens", []),
            "errors":  result.get("errors", []),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# GET /api/model — ML model info and evaluation metrics
# ---------------------------------------------------------------------------

@api_blueprint.route("/model", methods=["GET"])
def model_info():
    """
    Return ML model metadata and test-set evaluation metrics.

    Response body (JSON):
      {
        "success": bool,
        "model_loaded": bool,
        "metrics": { ... }  (contents of model_metrics.json)
      }
    """
    model_loaded = os.path.exists(config.MODEL_PATH)
    metrics = None

    if os.path.exists(config.METRICS_PATH):
        try:
            with open(config.METRICS_PATH, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception:
            metrics = None

    return jsonify({
        "success":      True,
        "model_loaded": model_loaded,
        "passes":       config.OPTIMIZATION_PASSES,
        "threshold":    config.ML_CONFIDENCE_THRESHOLD,
        "metrics":      metrics,
    })
