"""
api/pipeline.py — Orchestrator for the full 10-step compiler + ML pipeline.

Step sequence (mirrors architecture_plan_v2.md §1):
  [1]  Lexer            — tokenize source code
  [2]  Parser           — produce AST + parse errors
  [3]  Semantic         — type-check + build symbol table
  [4]  IR Generator     — emit TAC from the semantically valid AST
  [5]  Feature Extractor — compute 15 structural features from TAC + AST
  [6]  ML Predictor     — recommend optimization passes from features
  [7]  Explanation Gen  — human-readable per-pass explanations
  [8]  Optimizer        — apply ONLY ML-recommended passes
  [9]  Diff & Stats     — compute measured before/after instruction counts
  [10] Response         — assemble full JSON response

The pipeline is deliberately STRICT:
  • Each step is attempted in order.
  • If lexing, parsing, or semantic analysis returns errors, the pipeline
    stops early and returns the errors collected so far.
  • IR generation and optimization still run on best-effort if semantics
    pass, because the ML demonstrator needs TAC to extract features.
  • The ML model is used as a gatekeeper: optimizer ONLY applies passes
    recommended by the model.
  • All result metrics are labelled MEASURED (actual instruction counts).
"""

from typing import Any, Dict

from compiler.lexer import tokenize
from compiler.parser import parse
from compiler.semantic_analyzer import analyze
from compiler.ir_generator import generate
from compiler.optimizer import apply
from ml.feature_extractor import extract_features
from ml.model import predict_passes
from ml.recommendation import generate_pass_explanations
from api.serializers import assemble_response


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline(source_code: str) -> Dict[str, Any]:
    """
    Run the full 10-step compiler + ML optimization pipeline on source_code.

    Returns a fully assembled JSON-safe dict matching the schema in
    architecture_plan_v2.md §10.

    On early errors (lex / parse / semantic failures) the function returns
    a partial response that includes everything collected up to that point,
    with success=False and a populated error list.
    """

    # ------------------------------------------------------------------
    # Step 1: Lexical Analysis
    # ------------------------------------------------------------------
    tokenize_result = tokenize(source_code)
    token_errors    = tokenize_result.get("errors", [])

    # ------------------------------------------------------------------
    # Step 2: Parsing
    # ------------------------------------------------------------------
    parse_result = parse(source_code)
    parse_errors = parse_result.get("errors", [])
    ast_node     = parse_result.get("ast_node")

    if not parse_result.get("success") or ast_node is None:
        return _error_response(
            source_code      = source_code,
            tokenize_result  = tokenize_result,
            parse_result     = parse_result,
            message          = "Syntax error(s) detected — cannot proceed past parsing.",
            errors           = parse_errors or token_errors,
        )

    # ------------------------------------------------------------------
    # Step 3: Semantic Analysis
    # ------------------------------------------------------------------
    semantic_result = analyze(ast_node)
    semantic_errors = semantic_result.get("errors", [])

    if not semantic_result.get("success"):
        return _error_response(
            source_code      = source_code,
            tokenize_result  = tokenize_result,
            parse_result     = parse_result,
            semantic_result  = semantic_result,
            message          = "Semantic error(s) detected — cannot proceed past semantic analysis.",
            errors           = semantic_errors,
        )

    # ------------------------------------------------------------------
    # Step 4: IR Generation (Three-Address Code)
    # ------------------------------------------------------------------
    ir_result    = generate(ast_node)
    instructions = ir_result.get("instructions", [])

    if not instructions:
        return _error_response(
            source_code     = source_code,
            tokenize_result = tokenize_result,
            parse_result    = parse_result,
            semantic_result = semantic_result,
            ir_result       = ir_result,
            message         = "IR generation produced no instructions.",
            errors          = ir_result.get("errors", []),
        )

    # ------------------------------------------------------------------
    # Step 5 & 6: Feature Extraction + ML Prediction
    # ------------------------------------------------------------------
    ml_pred = predict_passes(instructions, ast=ast_node)
    recommended_passes = ml_pred.get("recommended_passes", [])

    # ------------------------------------------------------------------
    # Step 7: Explanation Generation
    # ------------------------------------------------------------------
    explanations = generate_pass_explanations(
        features    = ml_pred.get("features", {}),
        predictions = ml_pred,
    )

    # ------------------------------------------------------------------
    # Step 8 & 9: Optimization (only ML-recommended passes) + Diff/Stats
    # ------------------------------------------------------------------
    opt_result = apply(
        instructions,
        passes=recommended_passes,
        ast=ast_node,
        symbol_table=semantic_result.get("symbol_table"),
    )

    # ------------------------------------------------------------------
    # Step 10: Assemble full response
    # ------------------------------------------------------------------
    return assemble_response(
        source_code     = source_code,
        tokenize_result = tokenize_result,
        parse_result    = parse_result,
        semantic_result = semantic_result,
        ir_result       = ir_result,
        ml_pred         = ml_pred,
        explanations    = explanations,
        opt_result      = opt_result,
    )


# ---------------------------------------------------------------------------
# Error response builder (partial pipeline state)
# ---------------------------------------------------------------------------

def _error_response(
    source_code:     str,
    tokenize_result: Dict[str, Any],
    parse_result:    Dict[str, Any],
    message:         str,
    errors:          list,
    semantic_result: Dict[str, Any] = None,
    ir_result:       Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Build a structured error response preserving all partial pipeline data.
    """
    phases: Dict[str, Any] = {
        "tokens":          tokenize_result.get("tokens", []),
        "token_errors":    tokenize_result.get("errors", []),
        "ast":             parse_result.get("ast"),
        "parse_errors":    parse_result.get("errors", []),
        "symbol_table":    semantic_result.get("symbol_table", []) if semantic_result else [],
        "semantic_errors": semantic_result.get("errors", []) if semantic_result else [],
        "tac_before":      ir_result.get("instructions", []) if ir_result else [],
        "tac_before_text": ir_result.get("text", "") if ir_result else "",
        "tac_after":       [],
        "tac_after_text":  "",
        "optimized_code":  "",
        "optimized_c_code": "",
        "optimized_tac":   "",
    }

    return {
        "success":     False,
        "source_code": source_code,
        "error":       message,
        "errors":      errors,
        "phases":      phases,
        "ml":          None,
        "stats":       None,
    }
