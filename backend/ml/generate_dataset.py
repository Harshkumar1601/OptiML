"""
ml/generate_dataset.py — Synthetic dataset generator and auto-labeler.

Generates synthetic C-like programs with controlled optimization opportunities,
compiles them to TAC, extracts 15 structural features, and auto-labels each
optimization pass based on actual measured instruction reduction / modifications.
"""

import os
import sys
import random
import csv
from typing import List, Dict, Tuple, Any

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DATA_DIR,
    DATASET_PATH,
    TEST_PROGRAMS_DIR,
    DATASET_SIZE,
    RANDOM_SEED,
    FEATURE_NAMES,
    OPTIMIZATION_PASSES,
)
from compiler.lexer import build_lexer, tokenize
from compiler.parser import parse
from compiler.semantic_analyzer import analyze
from compiler.ir_generator import generate
from compiler.optimizer import apply
from ml.feature_extractor import extract_features


LABEL_NAMES = ["apply_cf", "apply_cp", "apply_cse", "apply_dce", "apply_sr"]


def _random_var(prefix: str = "v", existing: List[str] = None) -> str:
    """Generate a random variable name."""
    names = ["x", "y", "z", "a", "b", "c", "m", "n", "p", "q", "r", "s", "val", "cnt"]
    if existing:
        names = [n for n in names if n not in existing]
    if not names:
        names = [f"{prefix}_{random.randint(1, 100)}"]
    return random.choice(names)


def generate_synthetic_program(
    has_cf: bool = False,
    has_cp: bool = False,
    has_cse: bool = False,
    has_dce: bool = False,
    has_sr: bool = False,
    has_loop: bool = False,
    has_func: bool = False,
) -> str:
    """
    Generate a valid restricted C-like source code string based on feature flags.
    """
    lines: List[str] = []
    var_list: List[str] = []

    # Optional helper function
    if has_func:
        lines.append("int calc_helper(int val, int factor) {")
        lines.append("    int res = val + factor;")
        lines.append("    return res;")
        lines.append("}")
        lines.append("")

    lines.append("int main() {")

    # Variable declarations & constant expressions
    v1 = "x"
    v2 = "y"
    v3 = "z"
    var_list.extend([v1, v2, v3])

    lines.append(f"    int {v1} = 0;")
    lines.append(f"    int {v2} = 0;")
    lines.append(f"    int {v3} = 0;")

    # Constant folding opportunity
    if has_cf:
        c1 = random.randint(2, 50)
        c2 = random.randint(2, 50)
        c3 = random.randint(1, 20)
        cf_op = random.choice(["+", "*", "-", "compound"])
        if cf_op == "+":
            lines.append(f"    {v1} = {c1} + {c2};")
        elif cf_op == "*":
            lines.append(f"    {v1} = {c1} * {c2};")
        elif cf_op == "-":
            lines.append(f"    {v1} = {c1} - {c2};")
        else:
            lines.append(f"    {v1} = {c1} + {c2} * {c3};")
    else:
        lines.append(f"    {v1} = 10;")

    # Constant propagation opportunity
    if has_cp:
        const_val = random.randint(5, 100)
        lines.append(f"    int k = {const_val};")
        lines.append(f"    {v2} = k + {v1};")
    else:
        lines.append(f"    {v2} = {v1} + 5;")

    # Common subexpression elimination opportunity
    if has_cse:
        a_var = "a_sub"
        b_var = "b_sub"
        lines.append(f"    int {a_var} = {v1} + 1;")
        lines.append(f"    int {b_var} = {v2} + 2;")
        lines.append(f"    int r1 = {a_var} + {b_var};")
        lines.append(f"    int r2 = {a_var} + {b_var};")
        lines.append(f"    {v3} = r1 + r2;")
    else:
        lines.append(f"    {v3} = {v1} + {v2};")

    # Strength reduction opportunity
    if has_sr:
        pow2 = random.choice([2, 4, 8, 16, 32])
        sr_var = "sr_target"
        lines.append(f"    int {sr_var} = {v3} * {pow2};")
        lines.append(f"    {v3} = {sr_var};")

    # Dead code / unused temporaries opportunity
    if has_dce:
        dead_var = "dead_tmp"
        lines.append(f"    int {dead_var} = {v1} * 99;")
        lines.append(f"    int unused_calc = {v2} + {v3};")
        # Notice dead_var and unused_calc are assigned but unused in subsequent return/output

    # Optional loop
    if has_loop:
        lines.append(f"    int i = 0;")
        lines.append(f"    while (i < 5) {{")
        if has_cf:
            lines.append(f"        {v1} = {v1} + (2 * 4);")
        else:
            lines.append(f"        {v1} = {v1} + i;")
        lines.append(f"        i = i + 1;")
        lines.append(f"    }}")

    if has_func:
        lines.append(f"    {v3} = calc_helper({v1}, {v2});")

    lines.append(f"    return {v3};")
    lines.append("}")

    return "\n".join(lines)


def auto_label_program(instructions: List[Any]) -> Dict[str, int]:
    """
    Test each of the 5 optimization passes individually on the TAC instructions.
    Returns label 1 if the pass modifies or reduces instruction count, else 0.
    """
    labels = {}

    # 1. CONSTANT_FOLDING
    res_cf = apply(instructions, ["CONSTANT_FOLDING"])
    labels["apply_cf"] = 1 if res_cf.stats["instructions_after"] < res_cf.stats["instructions_before"] or res_cf.instructions_after != res_cf.instructions_before else 0

    # 2. CONSTANT_PROPAGATION
    res_cp = apply(instructions, ["CONSTANT_PROPAGATION"])
    labels["apply_cp"] = 1 if res_cp.instructions_after != res_cp.instructions_before else 0

    # 3. CSE
    res_cse = apply(instructions, ["CSE"])
    labels["apply_cse"] = 1 if res_cse.stats["instructions_after"] < res_cse.stats["instructions_before"] or res_cse.instructions_after != res_cse.instructions_before else 0

    # 4. DEAD_CODE_ELIMINATION
    res_dce_iso = apply(instructions, ["DEAD_CODE_ELIMINATION"])
    res_full = apply(instructions, ["CONSTANT_FOLDING", "CONSTANT_PROPAGATION", "CSE", "DEAD_CODE_ELIMINATION", "STRENGTH_REDUCTION"])
    labels["apply_dce"] = 1 if (
        res_dce_iso.instructions_after != res_dce_iso.instructions_before
        or "DEAD_CODE_ELIMINATION" in res_full.passes_applied
    ) else 0

    # 5. STRENGTH_REDUCTION
    res_sr = apply(instructions, ["STRENGTH_REDUCTION"])
    labels["apply_sr"] = 1 if res_sr.instructions_after != res_sr.instructions_before else 0

    return labels


def generate_dataset(
    size: int = DATASET_SIZE,
    output_path: str = DATASET_PATH,
    seed: int = RANDOM_SEED
) -> str:
    """
    Generate synthetic program dataset, compile, extract features, label, and write CSV.
    """
    random.seed(seed)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs(TEST_PROGRAMS_DIR, exist_ok=True)

    rows = []
    fieldnames = FEATURE_NAMES + LABEL_NAMES

    attempts = 0
    successful = 0

    while successful < size and attempts < size * 5:
        attempts += 1

        # Select random combination of features
        has_cf = random.random() < 0.50
        has_cp = random.random() < 0.50
        has_cse = random.random() < 0.45
        has_dce = random.random() < 0.45
        has_sr = random.random() < 0.40
        has_loop = random.random() < 0.35
        has_func = random.random() < 0.25

        # Ensure at least 1 feature is enabled for non-empty program
        if not (has_cf or has_cp or has_cse or has_dce or has_sr):
            has_cf = True

        source_code = generate_synthetic_program(
            has_cf=has_cf,
            has_cp=has_cp,
            has_cse=has_cse,
            has_dce=has_dce,
            has_sr=has_sr,
            has_loop=has_loop,
            has_func=has_func,
        )

        try:
            parse_result = parse(source_code)
            if not parse_result["success"] or parse_result["ast_node"] is None:
                continue

            ast_node = parse_result["ast_node"]
            sem_result = analyze(ast_node)
            if not sem_result["success"]:
                continue

            ir_result = generate(ast_node)
            instructions = ir_result["instructions"]
            if not instructions:
                continue

            # Extract features
            features = extract_features(instructions, ast=ast_node)

            # Auto-label ground truth
            labels = auto_label_program(instructions)

            # Combine feature dict + label dict
            row = {}
            for fname in FEATURE_NAMES:
                row[fname] = features.get(fname, 0)
            for lname in LABEL_NAMES:
                row[lname] = labels.get(lname, 0)

            rows.append(row)
            successful += 1

        except Exception as e:
            continue

    # Write dataset CSV
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Also save 5 benchmark test programs to TEST_PROGRAMS_DIR
    _generate_test_programs()

    print(f"Dataset generated successfully! ({len(rows)} samples saved to {output_path})")
    return output_path


def _generate_test_programs():
    """Generate 5 representative benchmark programs in TEST_PROGRAMS_DIR."""
    benchmarks = {
        "prog1_cf_cp.c": """
int main() {
    int x = 10 + 20;
    int y = x * 2;
    int z = y + 5;
    return z;
}
""",
        "prog2_cse.c": """
int main() {
    int a = 5;
    int b = 10;
    int x = a + b;
    int y = a + b;
    int z = x * y;
    return z;
}
""",
        "prog3_sr_dce.c": """
int main() {
    int x = 10;
    int y = x * 8;
    int dead_var = 999;
    return y;
}
""",
        "prog4_loop_all.c": """
int main() {
    int sum = 0;
    int step = 2 * 4;
    int i = 0;
    while (i < 10) {
        int a = i + 1;
        int b = i + 1;
        sum = sum + a + b + step;
        i = i + 1;
    }
    return sum;
}
""",
        "prog5_function.c": """
int calculate(int val) {
    int factor = 4 * 2;
    int res = val * factor;
    return res;
}

int main() {
    int start = 5;
    int out = calculate(start);
    return out;
}
"""
    }

    for name, code in benchmarks.items():
        filepath = os.path.join(TEST_PROGRAMS_DIR, name)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code.strip())


if __name__ == "__main__":
    generate_dataset()
