"""
ml/feature_extractor.py — Extract 15 numerical features from AST and TAC.

This module analyzes Three-Address Code (TAC) and optionally the AST to extract
15 structural features used by the ML optimization pass classifier.

Features extracted:
  1.  num_loops
  2.  loop_depth_max
  3.  num_functions
  4.  num_assignments
  5.  num_branches
  6.  tac_total_instructions
  7.  temp_var_count
  8.  const_literal_count
  9.  add_op_count
  10. mul_op_count
  11. div_op_count
  12. num_unique_vars
  13. repeated_rhs_count
  14. mul_by_power_of_2
  15. single_use_temp_count
"""

import re
import sys
import os
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import FEATURE_NAMES


def _get_field(inst: Any, field: str, default: Any = None) -> Any:
    """Helper to extract field from either dict or object."""
    if isinstance(inst, dict):
        return inst.get(field, default)
    return getattr(inst, field, default)


def _is_temp_var(name: Any) -> bool:
    """Check if variable name is a temporary (t0, t1, t2...)."""
    if isinstance(name, str) and re.match(r"^t\d+$", name):
        return True
    return False


def _is_number(val: Any) -> bool:
    """Check if value is a numeric literal."""
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        try:
            float(val)
            return True
        except ValueError:
            return False
    return False


def _to_number(val: Any) -> Optional[Union[int, float]]:
    """Convert value to int or float if possible."""
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            return None
    return None


def _is_power_of_two(n: Any) -> bool:
    """Check if value is a positive integer power of 2 (2, 4, 8, 16...)."""
    num = _to_number(n)
    if num is None or not isinstance(num, int) or num <= 0:
        return False
    # A power of 2 has only one bit set: (n & (n - 1)) == 0
    return (num & (num - 1)) == 0 and num > 1


def _count_ast_loops_and_depth(ast_node: Any) -> Tuple[int, int]:
    """Traverse AST to count total loops and max loop depth."""
    if ast_node is None:
        return 0, 0

    total_loops = 0
    max_depth = 0

    node_type = getattr(ast_node, "__class__", None).__name__ if hasattr(ast_node, "__class__") else ""
    if isinstance(ast_node, dict):
        node_type = ast_node.get("type", "")

    is_loop = node_type in ("WhileNode", "ForNode", "While", "For")

    current_loop_inc = 1 if is_loop else 0
    sub_max_depth = 0

    # Get children
    children = []
    for attr in ("functions", "statements", "stmts", "body", "then_block", "else_block", "else_body", "main_func"):
        if hasattr(ast_node, attr):
            val = getattr(ast_node, attr)
            if isinstance(val, list):
                children.extend(val)
            elif val is not None:
                children.append(val)

    if isinstance(ast_node, dict):
        node_type = ast_node.get("node", ast_node.get("type", ""))
        for k in ("functions", "statements", "stmts", "body", "then_block", "else_block", "else_body", "main_func", "children"):
            v = ast_node.get(k)
            if isinstance(v, list):
                children.extend(v)
            elif v:
                children.append(v)

    for child in children:
        child_loops, child_depth = _count_ast_loops_and_depth(child)
        total_loops += child_loops
        if child_depth > sub_max_depth:
            sub_max_depth = child_depth

    if is_loop:
        total_loops += 1
        max_depth = 1 + sub_max_depth
    else:
        max_depth = sub_max_depth

    return total_loops, max_depth


def extract_features(
    instructions: List[Any],
    ast: Optional[Any] = None
) -> Dict[str, Union[int, float]]:
    """
    Extract 15 numerical features from TAC instructions (and optional AST).

    Returns:
        Dict mapping feature name (from FEATURE_NAMES) -> value.
    """
    if instructions is None:
        instructions = []

    # 1 & 2: Loop count and max depth
    if ast is not None:
        num_loops, loop_depth_max = _count_ast_loops_and_depth(ast)
    else:
        # Fallback loop detection in TAC via backward jumps
        seen_labels = set()
        num_loops = 0
        loop_depth_max = 0
        for inst in instructions:
            op = _get_field(inst, "op")
            arg1 = _get_field(inst, "arg1")
            if op == "LABEL":
                seen_labels.add(arg1)
            elif op in ("JUMP", "JUMP_IF", "JUMP_UNLESS") and arg1 in seen_labels:
                num_loops += 1
        if num_loops > 0:
            loop_depth_max = 1

    # 3: Number of functions
    num_functions = 0
    for inst in instructions:
        if _get_field(inst, "op") == "FUNC_BEGIN":
            num_functions += 1

    # 4: Number of assignments
    assignment_ops = {"ASSIGN", "BINOP", "UNARY", "COMPARE", "AND", "OR", "NOT", "CALL"}
    num_assignments = 0
    for inst in instructions:
        op = _get_field(inst, "op")
        dest = _get_field(inst, "dest")
        if op in assignment_ops and dest is not None:
            num_assignments += 1

    # 5: Number of branches
    branch_ops = {"JUMP_IF", "JUMP_UNLESS"}
    num_branches = sum(1 for inst in instructions if _get_field(inst, "op") in branch_ops)

    # 6: Total TAC instructions
    tac_total_instructions = len(instructions)

    # Variables & Constants collection
    temp_vars = set()
    user_vars = set()
    const_literal_count = 0
    temp_uses: Dict[str, int] = {}
    rhs_expressions: List[Tuple[str, str, str]] = []
    add_op_count = 0
    mul_op_count = 0
    div_op_count = 0
    mul_by_power_of_2 = 0

    for inst in instructions:
        op = _get_field(inst, "op")
        dest = _get_field(inst, "dest")
        arg1 = _get_field(inst, "arg1")
        arg2 = _get_field(inst, "arg2")
        extra = _get_field(inst, "extra")

        # Check dest
        if dest is not None:
            if _is_temp_var(dest):
                temp_vars.add(dest)
            elif isinstance(dest, str) and not _is_number(dest):
                user_vars.add(dest)

        # Check arg1 and arg2
        for arg in (arg1, arg2):
            if arg is not None:
                if _is_number(arg):
                    const_literal_count += 1
                elif _is_temp_var(arg):
                    temp_vars.add(arg)
                    temp_uses[arg] = temp_uses.get(arg, 0) + 1
                elif isinstance(arg, str) and op not in ("LABEL", "JUMP", "JUMP_IF", "JUMP_UNLESS", "FUNC_BEGIN", "FUNC_END"):
                    user_vars.add(arg)

        # Arithmetic ops and power of 2 check
        if op in ("BINOP", "COMPARE"):
            operator = extra or ""
            if operator in ("+", "-"):
                add_op_count += 1
            elif operator == "*":
                mul_op_count += 1
                if _is_power_of_two(arg1) or _is_power_of_two(arg2):
                    mul_by_power_of_2 += 1
            elif operator == "/":
                div_op_count += 1

            # RHS tracking for CSE
            expr_key = (operator, str(arg1), str(arg2))
            rhs_expressions.append(expr_key)

        elif op == "UNARY":
            if extra in ("+", "-"):
                add_op_count += 1

    # 12: Unique non-temp variable count
    num_unique_vars = len(user_vars)

    # 7: Temp var count
    temp_var_count = len(temp_vars)

    # 13: Repeated RHS count
    from collections import Counter
    counts = Counter(rhs_expressions)
    repeated_rhs_count = sum(c - 1 for c in counts.values() if c > 1)

    # 15: Single-use (or dead) temp count
    single_use_temp_count = 0
    for t in temp_vars:
        uses = temp_uses.get(t, 0)
        if uses <= 1:
            single_use_temp_count += 1

    # Assemble dictionary matching FEATURE_NAMES
    features = {
        "num_loops": num_loops,
        "loop_depth_max": loop_depth_max,
        "num_functions": num_functions,
        "num_assignments": num_assignments,
        "num_branches": num_branches,
        "tac_total_instructions": tac_total_instructions,
        "temp_var_count": temp_var_count,
        "const_literal_count": const_literal_count,
        "add_op_count": add_op_count,
        "mul_op_count": mul_op_count,
        "div_op_count": div_op_count,
        "num_unique_vars": num_unique_vars,
        "repeated_rhs_count": repeated_rhs_count,
        "mul_by_power_of_2": mul_by_power_of_2,
        "single_use_temp_count": single_use_temp_count,
    }

    return features


def get_feature_vector(features: Dict[str, Union[int, float]]) -> np.ndarray:
    """
    Convert feature dictionary to 1D numpy array ordered by FEATURE_NAMES.
    """
    vector = [float(features.get(name, 0)) for name in FEATURE_NAMES]
    return np.array(vector, dtype=np.float32)
