"""
api/serializers.py — Convert internal compiler/ML objects to JSON-safe dicts.

All functions in this module accept raw objects from the compiler pipeline and
return plain Python dicts/lists that Flask can serialize to JSON responses.
These live separately from the compiler modules so the pipeline stays clean.
"""

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Token serializer
# ---------------------------------------------------------------------------

def serialize_tokens(tokenize_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Serialize tokenize() result to a clean list of token dicts.

    Input:  tokenize() returns {"tokens": [...], "errors": [...]}
    Output: [{"type": str, "value": str, "line": int, "column": int}, ...]
    """
    return tokenize_result.get("tokens", [])


# ---------------------------------------------------------------------------
# AST serializer
# ---------------------------------------------------------------------------

def serialize_ast(parse_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return the already JSON-safe AST dict from parse().

    Input:  parse() returns {"ast": dict|None, "ast_node": ProgramNode, ...}
    Output: The nested AST dict (already JSON-safe via to_dict()).
    """
    return parse_result.get("ast")


# ---------------------------------------------------------------------------
# Symbol table serializer
# ---------------------------------------------------------------------------

def serialize_symbol_table(semantic_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Serialize semantic_analyzer.analyze() symbol_table to list of dicts.

    Input:  analyze() returns {"symbol_table": [...], "errors": [...], "success": bool}
    Output: list of symbol entry dicts
    """
    return semantic_result.get("symbol_table", [])


def serialize_semantic_errors(semantic_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of semantic error dicts from analyze()."""
    return semantic_result.get("errors", [])


# ---------------------------------------------------------------------------
# TAC serializer
# ---------------------------------------------------------------------------

def serialize_tac(ir_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize ir_generator.generate() result.

    Input:  generate() returns {"instructions": list[dict], "text": str, ...}
    Output: {"instructions": [...], "text": str}
    """
    return {
        "instructions": ir_result.get("instructions", []),
        "text": ir_result.get("text", ""),
    }


# ---------------------------------------------------------------------------
# Optimization result serializer
# ---------------------------------------------------------------------------

def serialize_optimization(opt_result: Any) -> Dict[str, Any]:
    """
    Serialize optimizer.apply() OptimizationResult.

    Handles both OptimizationResult dataclass objects and plain dicts.
    """
    if hasattr(opt_result, "to_dict"):
        return opt_result.to_dict()
    return opt_result


# ---------------------------------------------------------------------------
# ML prediction serializer
# ---------------------------------------------------------------------------

def serialize_ml_prediction(pred_result: Dict[str, Any], explanations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Serialize predict_passes() result + explanation list to ML response block.

    Returns the "ml" section of the full API response (see architecture_plan_v2.md).
    """
    model_info = pred_result.get("model_info", {})

    recommendations = []
    for exp in explanations:
        pass_name = exp["pass"]
        recommendations.append({
            "pass":        pass_name,
            "confidence":  exp["confidence"],
            "recommended": exp["recommended"],
            "applied":     False,        # filled in later by the pipeline
            "explanation": exp["explanation"],
            "result_type": "ESTIMATED",
        })

    return {
        "features":        pred_result.get("features", {}),
        "recommendations": recommendations,
        "model_info":      model_info,
    }


# ---------------------------------------------------------------------------
# Full pipeline response assembler
# ---------------------------------------------------------------------------

def assemble_response(
    source_code:      str,
    tokenize_result:  Dict[str, Any],
    parse_result:     Dict[str, Any],
    semantic_result:  Dict[str, Any],
    ir_result:        Dict[str, Any],
    ml_pred:          Dict[str, Any],
    explanations:     List[Dict[str, Any]],
    opt_result:       Any,
) -> Dict[str, Any]:
    """
    Assemble the full JSON response from all pipeline stage outputs.

    Matches the schema defined in architecture_plan_v2.md §10.
    """
    opt_dict = serialize_optimization(opt_result)
    stats    = opt_dict.get("stats", {})

    # Annotate which passes were actually applied into the ML recommendations
    applied_set = set(stats.get("passes_applied", []))
    ml_block    = serialize_ml_prediction(ml_pred, explanations)
    for rec in ml_block["recommendations"]:
        rec["applied"] = rec["pass"] in applied_set

    return {
        "success":     True,
        "source_code": source_code,
        "phases": {
            "tokens":           serialize_tokens(tokenize_result),
            "token_errors":     tokenize_result.get("errors", []),
            "ast":              serialize_ast(parse_result),
            "parse_errors":     parse_result.get("errors", []),
            "symbol_table":     serialize_symbol_table(semantic_result),
            "semantic_errors":  serialize_semantic_errors(semantic_result),
            "tac_before":       ir_result.get("instructions", []),
            "tac_before_text":  ir_result.get("text", ""),
            "tac_after":        opt_dict.get("tac_after", []),
            "tac_after_text":   opt_dict.get("text_after", ""),
            "optimized_code":   opt_dict.get("optimized_c_code") or opt_dict.get("optimized_code", ""),
            "optimized_c_code": opt_dict.get("optimized_c_code") or opt_dict.get("optimized_code", ""),
            "optimized_tac":    opt_dict.get("optimized_tac") or opt_dict.get("text_after", ""),
        },
        "optimized_c_code": opt_dict.get("optimized_c_code") or opt_dict.get("optimized_code", ""),
        "optimized_tac":    opt_dict.get("optimized_tac") or opt_dict.get("text_after", ""),
        "ml":    ml_block,
        "stats": stats,
    }
