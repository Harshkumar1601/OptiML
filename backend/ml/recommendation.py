"""
ml/recommendation.py — Generate detailed human-readable pass explanations.

Converts ML features, predictions, and confidence scores into clear, professional
academic explanations for each optimization pass.
"""

from typing import Dict, List, Any


def generate_pass_explanations(
    features: Dict[str, Any],
    predictions: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate detailed explanation structures for each optimization pass.

    Returns:
        List of dicts containing:
          - pass: Canonical pass name
          - confidence: float (0.0 - 1.0)
          - recommended: bool
          - explanation: Detailed human-readable text
          - result_type: "ESTIMATED"
    """
    confidences = predictions.get("confidences", {})
    recommended_set = set(predictions.get("recommended_passes", []))

    explanations = []

    # 1. CONSTANT_FOLDING
    cf_conf = confidences.get("CONSTANT_FOLDING", 0.0)
    cf_rec = "CONSTANT_FOLDING" in recommended_set
    c_count = features.get("const_literal_count", 0)
    add_count = features.get("add_op_count", 0)
    mul_count = features.get("mul_op_count", 0)

    if cf_rec:
        cf_exp = (
            f"Constant Folding recommended (confidence {cf_conf * 100:.1f}%): "
            f"Detected {c_count} constant literals and arithmetic operations ({add_count} add/sub, {mul_count} mul). "
            f"Pre-computing constant arithmetic expressions at compile time will eliminate runtime evaluation overhead."
        )
    else:
        cf_exp = (
            f"Constant Folding skipped (confidence {cf_conf * 100:.1f}% below threshold): "
            f"No foldable literal-only arithmetic expressions found in program TAC."
        )

    explanations.append({
        "pass": "CONSTANT_FOLDING",
        "confidence": cf_conf,
        "recommended": cf_rec,
        "explanation": cf_exp,
        "result_type": "ESTIMATED",
    })

    # 2. CONSTANT_PROPAGATION
    cp_conf = confidences.get("CONSTANT_PROPAGATION", 0.0)
    cp_rec = "CONSTANT_PROPAGATION" in recommended_set
    num_assign = features.get("num_assignments", 0)

    if cp_rec:
        cp_exp = (
            f"Constant Propagation recommended (confidence {cp_conf * 100:.1f}%): "
            f"Detected constant assignments among {num_assign} assignment instructions. "
            f"Propagating known literal values into subsequent expressions will enable further constant folding and dead assignment elimination."
        )
    else:
        cp_exp = (
            f"Constant Propagation skipped (confidence {cp_conf * 100:.1f}% below threshold): "
            f"No constant assignments requiring propagation to downstream operands."
        )

    explanations.append({
        "pass": "CONSTANT_PROPAGATION",
        "confidence": cp_conf,
        "recommended": cp_rec,
        "explanation": cp_exp,
        "result_type": "ESTIMATED",
    })

    # 3. CSE
    cse_conf = confidences.get("CSE", 0.0)
    cse_rec = "CSE" in recommended_set
    rep_rhs = features.get("repeated_rhs_count", 0)

    if cse_rec:
        cse_exp = (
            f"Common Subexpression Elimination recommended (confidence {cse_conf * 100:.1f}%): "
            f"Detected {rep_rhs} repeated right-hand side expressions. "
            f"Replacing redundant computations with existing temporary variable values will reduce instruction count."
        )
    else:
        cse_exp = (
            f"Common Subexpression Elimination skipped (confidence {cse_conf * 100:.1f}% below threshold): "
            f"No repeated subexpressions detected across active program blocks."
        )

    explanations.append({
        "pass": "CSE",
        "confidence": cse_conf,
        "recommended": cse_rec,
        "explanation": cse_exp,
        "result_type": "ESTIMATED",
    })

    # 4. DEAD_CODE_ELIMINATION
    dce_conf = confidences.get("DEAD_CODE_ELIMINATION", 0.0)
    dce_rec = "DEAD_CODE_ELIMINATION" in recommended_set
    dead_temps = features.get("single_use_temp_count", 0)

    if dce_rec:
        dce_exp = (
            f"Dead Code Elimination recommended (confidence {dce_conf * 100:.1f}%): "
            f"Detected {dead_temps} candidate dead temporaries or unread intermediate values. "
            f"Removing instructions writing to unread temporaries will streamline TAC output."
        )
    else:
        dce_exp = (
            f"Dead Code Elimination skipped (confidence {dce_conf * 100:.1f}% below threshold): "
            f"All temporary variables and instructions are actively read by downstream operands."
        )

    explanations.append({
        "pass": "DEAD_CODE_ELIMINATION",
        "confidence": dce_conf,
        "recommended": dce_rec,
        "explanation": dce_exp,
        "result_type": "ESTIMATED",
    })

    # 5. STRENGTH_REDUCTION
    sr_conf = confidences.get("STRENGTH_REDUCTION", 0.0)
    sr_rec = "STRENGTH_REDUCTION" in recommended_set
    pow2_muls = features.get("mul_by_power_of_2", 0)

    if sr_rec:
        sr_exp = (
            f"Strength Reduction recommended (confidence {sr_conf * 100:.1f}%): "
            f"Detected {pow2_muls} multiplication instructions by power-of-2 constants. "
            f"Replacing multiplication with left-shift bitwise operations reduces instruction cost."
        )
    else:
        sr_exp = (
            f"Strength Reduction skipped (confidence {sr_conf * 100:.1f}% below threshold): "
            f"No multiplication by power-of-2 integer constants detected."
        )

    explanations.append({
        "pass": "STRENGTH_REDUCTION",
        "confidence": sr_conf,
        "recommended": sr_rec,
        "explanation": sr_exp,
        "result_type": "ESTIMATED",
    })

    return explanations
