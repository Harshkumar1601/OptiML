"""
tests/test_ir.py — Unit tests for compiler/ir_generator.py

All tests run the full pipeline: source → parse → semantic → TAC.
They inspect the structured TACInstruction list (via to_dict()) and
the human-readable text output.

Test categories:
  1.  Simple assignment
  2.  Arithmetic expressions + operator precedence
  3.  Unary minus
  4.  Nested / complex expressions
  5.  If statements (no else)
  6.  If-else statements
  7.  While loops
  8.  For loops
  9.  Nested control flow
  10. Return statements
  11. Function calls (with and without return value)
  12. Multiple functions
  13. Temporary variable generation
  14. Label generation (uniqueness, naming)
  15. IR validation utility
  16. Semantically invalid programs do not reach TAC generation
  17. TAC text / human-readable output
  18. Result dict structure
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from compiler import parser as parser_mod
from compiler.lexer import build_lexer
from compiler.semantic_analyzer import SemanticAnalyzer
from compiler.ir_generator import (
    TACGenerator, TACInstruction, generate, validate_instructions
)
from compiler import ast_nodes as N


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _parse_to_ast(source: str):
    """Parse source and return the raw ProgramNode (or None on parse failure)."""
    parser_mod._parse_errors = []
    lexer = build_lexer()
    lexer.source = source
    p = parser_mod._get_parser()
    return p.parse(source, lexer=lexer, tracking=True)


def compile_tac(source: str) -> dict:
    """
    Full pipeline: source → parse → semantic analysis → TAC generation.
    Returns the TAC result dict.
    Skips TAC generation if parsing or semantic analysis fails.
    """
    ast = _parse_to_ast(source)
    if ast is None:
        return {"instructions": [], "text": "", "errors": ["Parse failed"], "success": False}
    sem = SemanticAnalyzer()
    sem_result = sem.analyze(ast)
    if not sem_result["success"]:
        return {"instructions": [], "text": "", "errors": sem_result["errors"], "success": False}
    return generate(ast)


def ops(result: dict) -> list:
    """Return just the op list from a TAC result."""
    return [i["op"] for i in result["instructions"]]


def assigns(result: dict) -> list:
    """Return all ASSIGN instructions."""
    return [i for i in result["instructions"] if i["op"] == "ASSIGN"]


def labels(result: dict) -> list:
    """Return all LABEL instructions."""
    return [i for i in result["instructions"] if i["op"] == "LABEL"]


def jumps(result: dict) -> list:
    """Return all JUMP / JUMP_IF / JUMP_UNLESS instructions."""
    return [i for i in result["instructions"]
            if i["op"] in ("JUMP", "JUMP_IF", "JUMP_UNLESS")]


def binops(result: dict) -> list:
    return [i for i in result["instructions"] if i["op"] == "BINOP"]


def compares(result: dict) -> list:
    return [i for i in result["instructions"] if i["op"] == "COMPARE"]


def returns(result: dict) -> list:
    return [i for i in result["instructions"] if i["op"] == "RETURN"]


# ===========================================================================
# 1. Simple Assignment
# ===========================================================================
class TestSimpleAssignment:
    def test_int_declaration_with_literal(self):
        result = compile_tac("int main() { int x = 5; return x; }")
        assert result["success"]
        asgns = assigns(result)
        # One ASSIGN for x = 5
        x_assigns = [a for a in asgns if a["dest"] == "x"]
        assert len(x_assigns) >= 1
        assert x_assigns[0]["arg1"] == "5"

    def test_float_declaration_with_literal(self):
        result = compile_tac("float main() { float x = 3.14; return x; }")
        assert result["success"]
        asgns = assigns(result)
        x_assigns = [a for a in asgns if a["dest"] == "x"]
        assert len(x_assigns) >= 1
        assert "3.14" in x_assigns[0]["arg1"]

    def test_assignment_after_declaration(self):
        result = compile_tac("int main() { int x; x = 10; return x; }")
        assert result["success"]
        asgns = [a for a in assigns(result) if a["dest"] == "x"]
        assert any(a["arg1"] == "10" for a in asgns)

    def test_identifier_assigned_to_identifier(self):
        result = compile_tac("int main() { int x = 5; int y = x; return y; }")
        assert result["success"]
        y_assigns = [a for a in assigns(result) if a["dest"] == "y"]
        assert any(a["arg1"] == "x" for a in y_assigns)


# ===========================================================================
# 2. Arithmetic Expressions + Operator Precedence
# ===========================================================================
class TestArithmeticExpressions:
    def test_addition(self):
        result = compile_tac("int main() { int x = 2 + 3; return x; }")
        assert result["success"]
        bops = binops(result)
        assert any(b["extra"] == "+" for b in bops)

    def test_subtraction(self):
        result = compile_tac("int main() { int x = 5 - 2; return x; }")
        assert result["success"]
        assert any(b["extra"] == "-" for b in binops(result))

    def test_multiplication(self):
        result = compile_tac("int main() { int x = 3 * 4; return x; }")
        assert result["success"]
        assert any(b["extra"] == "*" for b in binops(result))

    def test_division(self):
        result = compile_tac("int main() { int x = 10 / 2; return x; }")
        assert result["success"]
        assert any(b["extra"] == "/" for b in binops(result))

    def test_precedence_mul_before_add(self):
        # a + b * c → BINOP(*) must come before BINOP(+)
        result = compile_tac("int main() { int x = 2 + 3 * 4; return x; }")
        assert result["success"]
        bops = binops(result)
        # The multiplication BINOP must appear before the addition BINOP
        ops_list = [b["extra"] for b in bops]
        mul_idx = ops_list.index("*")
        add_idx = ops_list.index("+")
        assert mul_idx < add_idx

    def test_parenthesized_addition_before_mul(self):
        # (a + b) * c → BINOP(+) must come before BINOP(*)
        result = compile_tac("int main() { int x = (2 + 3) * 4; return x; }")
        assert result["success"]
        bops = binops(result)
        ops_list = [b["extra"] for b in bops]
        add_idx = ops_list.index("+")
        mul_idx = ops_list.index("*")
        assert add_idx < mul_idx

    def test_two_binops_produce_two_temps(self):
        result = compile_tac("int main() { int x = 1 + 2 + 3; return x; }")
        assert result["success"]
        assert len(binops(result)) == 2
        dests = [b["dest"] for b in binops(result)]
        # Each BINOP should write to a unique temporary
        assert len(set(dests)) == 2


# ===========================================================================
# 3. Unary Minus
# ===========================================================================
class TestUnaryMinus:
    def test_unary_on_literal(self):
        result = compile_tac("int main() { int x = -5; return x; }")
        assert result["success"]
        unaries = [i for i in result["instructions"] if i["op"] == "UNARY"]
        assert len(unaries) == 1
        assert unaries[0]["arg1"] == "5"

    def test_unary_on_identifier(self):
        result = compile_tac("int main() { int y = 3; int x = -y; return x; }")
        assert result["success"]
        unaries = [i for i in result["instructions"] if i["op"] == "UNARY"]
        assert any(u["arg1"] == "y" for u in unaries)

    def test_unary_on_subexpr(self):
        # -(a + b) → BINOP then UNARY
        result = compile_tac("int main() { int a = 2; int b = 3; int x = -(a + b); return x; }")
        assert result["success"]
        op_list = ops(result)
        assert "BINOP" in op_list
        assert "UNARY" in op_list
        binop_idx = op_list.index("BINOP")
        unary_idx = op_list.index("UNARY")
        assert binop_idx < unary_idx

    def test_double_unary(self):
        result = compile_tac("int main() { int y = 5; int x = --y; return x; }")
        assert result["success"]
        unaries = [i for i in result["instructions"] if i["op"] == "UNARY"]
        assert len(unaries) == 2


# ===========================================================================
# 4. Nested / Complex Expressions
# ===========================================================================
class TestNestedExpressions:
    def test_three_level_nesting(self):
        src = "int main() { int x = (1 + 2) * (3 - 4); return x; }"
        result = compile_tac(src)
        assert result["success"]
        assert len(binops(result)) == 3  # +, -, *

    def test_deep_nesting(self):
        src = "int main() { int x = 1 + 2 * 3 + 4 * 5; return x; }"
        result = compile_tac(src)
        assert result["success"]
        # 1 + (2*3) + (4*5) → 4 BINOP ops (2 muls + 2 adds)
        assert len(binops(result)) == 4

    def test_literal_rhs_no_temp_needed(self):
        # `int x = 5` — no temp required; arg1 should be the literal string
        result = compile_tac("int main() { int x = 5; return x; }")
        assert result["success"]
        asgns = [a for a in assigns(result) if a["dest"] == "x"]
        assert asgns[0]["arg1"] == "5"


# ===========================================================================
# 5. If Statements (no else)
# ===========================================================================
class TestIfNoElse:
    def test_if_emits_jump_unless(self):
        src = "int main() { int x = 5; if (x > 0) { x = x + 1; } return x; }"
        result = compile_tac(src)
        assert result["success"]
        assert "JUMP_UNLESS" in ops(result)

    def test_if_emits_one_label(self):
        src = "int main() { int x = 5; if (x > 0) { x = x + 1; } return x; }"
        result = compile_tac(src)
        assert result["success"]
        # If with no else: exactly 1 label (L_end)
        assert len(labels(result)) == 1

    def test_if_emits_compare(self):
        src = "int main() { int x = 5; if (x > 0) { x = 1; } return x; }"
        result = compile_tac(src)
        assert result["success"]
        cmps = compares(result)
        assert any(c["extra"] == ">" for c in cmps)

    def test_if_body_emits_assign(self):
        src = "int main() { int x = 5; if (x > 0) { x = 1; } return x; }"
        result = compile_tac(src)
        assert result["success"]
        # The body assign (x = 1) must appear between JUMP_UNLESS and LABEL
        op_list = ops(result)
        ju_idx = op_list.index("JUMP_UNLESS")
        lbl_idx = op_list.index("LABEL")
        # Find an ASSIGN between them
        body_assigns = [
            i for j, i in enumerate(result["instructions"])
            if i["op"] == "ASSIGN" and ju_idx < j < lbl_idx
        ]
        assert len(body_assigns) >= 1

    def test_if_condition_evaluates_before_jump(self):
        src = "int main() { int x = 5; if (x > 0) { x = 1; } return x; }"
        result = compile_tac(src)
        op_list = ops(result)
        cmp_idx = op_list.index("COMPARE")
        ju_idx  = op_list.index("JUMP_UNLESS")
        assert cmp_idx < ju_idx


# ===========================================================================
# 6. If-Else Statements
# ===========================================================================
class TestIfElse:
    def test_if_else_emits_two_labels(self):
        src = """
        int main() {
            int x = 5;
            if (x > 0) { x = 1; } else { x = 0; }
            return x;
        }
        """
        result = compile_tac(src)
        assert result["success"]
        assert len(labels(result)) == 2

    def test_if_else_emits_unconditional_jump(self):
        src = """
        int main() {
            int x = 5;
            if (x > 0) { x = 1; } else { x = 0; }
            return x;
        }
        """
        result = compile_tac(src)
        assert result["success"]
        assert "JUMP" in ops(result)

    def test_if_else_label_order(self):
        # L_else must appear before L_end in the instruction stream
        src = """
        int main() {
            int x = 5;
            if (x > 0) { x = 1; } else { x = 0; }
            return x;
        }
        """
        result = compile_tac(src)
        lbl_instrs = [i for i in result["instructions"] if i["op"] == "LABEL"]
        assert len(lbl_instrs) == 2
        l_else = lbl_instrs[0]["arg1"]
        l_end  = lbl_instrs[1]["arg1"]
        # l_else label number should be lower than l_end
        assert int(l_else[1:]) < int(l_end[1:])


# ===========================================================================
# 7. While Loops
# ===========================================================================
class TestWhileLoop:
    def test_while_emits_two_labels(self):
        src = """
        int main() {
            int i = 0;
            while (i < 10) { i = i + 1; }
            return i;
        }
        """
        result = compile_tac(src)
        assert result["success"]
        assert len(labels(result)) == 2

    def test_while_back_edge_jump(self):
        src = """
        int main() {
            int i = 0;
            while (i < 10) { i = i + 1; }
            return i;
        }
        """
        result = compile_tac(src)
        # A JUMP back to L_start must exist
        assert "JUMP" in ops(result)

    def test_while_start_label_comes_first(self):
        src = """
        int main() {
            int i = 0;
            while (i < 5) { i = i + 1; }
            return i;
        }
        """
        result = compile_tac(src)
        lbl_instrs = [i for i in result["instructions"] if i["op"] == "LABEL"]
        l_start = lbl_instrs[0]["arg1"]
        l_end   = lbl_instrs[1]["arg1"]
        assert int(l_start[1:]) < int(l_end[1:])

    def test_while_condition_evaluates_at_label(self):
        src = """
        int main() {
            int i = 0;
            while (i < 10) { i = i + 1; }
            return i;
        }
        """
        result = compile_tac(src)
        op_list = ops(result)
        lbl_idx = op_list.index("LABEL")    # L_start
        cmp_idx = op_list.index("COMPARE")
        # Compare must come after the start label
        assert cmp_idx > lbl_idx


# ===========================================================================
# 8. For Loops
# ===========================================================================
class TestForLoop:
    def test_for_loop_basic(self):
        src = """
        int main() {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) { s = s + i; }
            return s;
        }
        """
        result = compile_tac(src)
        assert result["success"]

    def test_for_emits_two_labels(self):
        src = """
        int main() {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) { s = s + i; }
            return s;
        }
        """
        result = compile_tac(src)
        assert len(labels(result)) == 2

    def test_for_init_assign_before_start_label(self):
        src = """
        int main() {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) { s = s + i; }
            return s;
        }
        """
        result = compile_tac(src)
        op_list = ops(result)
        # i = 0 ASSIGN should appear before the first LABEL
        first_label_idx = op_list.index("LABEL")
        init_assigns = [
            j for j, i in enumerate(result["instructions"])
            if i["op"] == "ASSIGN" and i["dest"] == "i"
        ]
        assert any(j < first_label_idx for j in init_assigns)

    def test_for_update_before_back_jump(self):
        src = """
        int main() {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) { s = s + i; }
            return s;
        }
        """
        result = compile_tac(src)
        op_list = ops(result)
        # The back-edge JUMP should be the last JUMP
        jump_indices = [j for j, o in enumerate(op_list) if o == "JUMP"]
        # The update assign (i = i + 1) should appear before last JUMP
        last_jump_idx = jump_indices[-1]
        update_indices = [
            j for j, i in enumerate(result["instructions"])
            if i["op"] == "ASSIGN" and i["dest"] == "i"
        ]
        # There should be at least one i-assign before the last JUMP
        assert any(j < last_jump_idx for j in update_indices)


# ===========================================================================
# 9. Nested Control Flow
# ===========================================================================
class TestNestedControlFlow:
    def test_nested_if_in_while(self):
        src = """
        int main() {
            int i = 0;
            int s = 0;
            while (i < 5) {
                if (i > 2) { s = s + i; }
                i = i + 1;
            }
            return s;
        }
        """
        result = compile_tac(src)
        assert result["success"]
        # while: 2 labels; if: 1 label → 3 total
        assert len(labels(result)) == 3

    def test_nested_for_loops_unique_labels(self):
        src = """
        int main() {
            int s = 0;
            int i = 0;
            int j = 0;
            for (i = 0; i < 3; i = i + 1) {
                for (j = 0; j < 3; j = j + 1) {
                    s = s + i;
                }
            }
            return s;
        }
        """
        result = compile_tac(src)
        assert result["success"]
        label_names = [i["arg1"] for i in labels(result)]
        # All label names must be unique
        assert len(label_names) == len(set(label_names))


# ===========================================================================
# 10. Return Statements
# ===========================================================================
class TestReturnStatements:
    def test_return_literal(self):
        result = compile_tac("int main() { return 0; }")
        assert result["success"]
        rets = returns(result)
        assert len(rets) >= 1
        assert rets[-1]["arg1"] == "0"

    def test_return_identifier(self):
        result = compile_tac("int main() { int x = 5; return x; }")
        assert result["success"]
        rets = returns(result)
        assert any(r["arg1"] == "x" for r in rets)

    def test_return_expression(self):
        result = compile_tac("int main() { int x = 2; return x + 3; }")
        assert result["success"]
        # The return value should be a temporary
        rets = returns(result)
        ret_val = rets[-1]["arg1"]
        assert ret_val.startswith("t")

    def test_bare_return(self):
        src = "int main() { int x = 1; return; }"
        # Parse+semantic may flag this (RETURN_TYPE_MISMATCH), but TAC still generates
        ast = _parse_to_ast(src)
        gen = TACGenerator()
        result = gen.generate(ast)
        ret_instrs = [i for i in result["instructions"] if i["op"] == "RETURN"]
        assert any(r["arg1"] is None for r in ret_instrs)


# ===========================================================================
# 11. Function Calls
# ===========================================================================
class TestFunctionCalls:
    def test_call_with_no_args(self):
        src = """
        int one() { return 1; }
        int main() { int x = one(); return x; }
        """
        result = compile_tac(src)
        assert result["success"]
        call_instrs = [i for i in result["instructions"] if i["op"] == "CALL"]
        assert any(c["arg1"] == "one" for c in call_instrs)

    def test_call_with_args_emits_params(self):
        src = """
        int add(int a, int b) { return a + b; }
        int main() { int x = add(1, 2); return x; }
        """
        result = compile_tac(src)
        assert result["success"]
        param_instrs = [i for i in result["instructions"] if i["op"] == "PARAM"]
        assert len(param_instrs) == 2

    def test_call_arg_count_in_call_instruction(self):
        src = """
        int add(int a, int b) { return a + b; }
        int main() { int x = add(1, 2); return x; }
        """
        result = compile_tac(src)
        call_instrs = [i for i in result["instructions"] if i["op"] == "CALL"]
        add_call = [c for c in call_instrs if c["arg1"] == "add"]
        assert add_call[0]["arg2"] == 2

    def test_call_result_assigned_to_temp(self):
        src = """
        int add(int a, int b) { return a + b; }
        int main() { int x = add(1, 2); return x; }
        """
        result = compile_tac(src)
        call_instrs = [i for i in result["instructions"]
                       if i["op"] == "CALL" and i["arg1"] == "add"]
        assert call_instrs[0]["dest"] is not None
        assert call_instrs[0]["dest"].startswith("t")

    def test_call_as_statement_no_dest(self):
        src = """
        int helper() { return 1; }
        int main() { helper(); return 0; }
        """
        result = compile_tac(src)
        assert result["success"]
        call_instrs = [i for i in result["instructions"]
                       if i["op"] == "CALL" and i["arg1"] == "helper"]
        assert call_instrs[0]["dest"] is None


# ===========================================================================
# 12. Multiple Functions
# ===========================================================================
class TestMultipleFunctions:
    def test_each_function_has_begin_end(self):
        src = """
        int foo() { return 1; }
        int bar() { return 2; }
        int main() { return 0; }
        """
        result = compile_tac(src)
        assert result["success"]
        begins = [i for i in result["instructions"] if i["op"] == "FUNC_BEGIN"]
        ends   = [i for i in result["instructions"] if i["op"] == "FUNC_END"]
        assert len(begins) == 3
        assert len(ends)   == 3

    def test_function_names_in_begin_end(self):
        src = """
        int foo() { return 1; }
        int main() { return 0; }
        """
        result = compile_tac(src)
        begins = [i for i in result["instructions"] if i["op"] == "FUNC_BEGIN"]
        names = [b["arg1"] for b in begins]
        assert "foo" in names
        assert "main" in names


# ===========================================================================
# 13. Temporary Variable Generation
# ===========================================================================
class TestTemporaryGeneration:
    def test_temps_are_unique(self):
        src = "int main() { int x = 1 + 2; int y = 3 + 4; return x + y; }"
        result = compile_tac(src)
        all_dests = [i["dest"] for i in result["instructions"]
                     if i["dest"] and i["dest"].startswith("t")]
        assert len(all_dests) == len(set(all_dests))

    def test_temps_are_sequentially_numbered(self):
        src = "int main() { int x = 1 + 2 + 3; return x; }"
        result = compile_tac(src)
        dests = [i["dest"] for i in result["instructions"]
                 if i["dest"] and i["dest"].startswith("t")]
        numbers = [int(d[1:]) for d in dests]
        assert numbers == sorted(numbers)

    def test_simple_literal_no_temp_needed(self):
        result = compile_tac("int main() { int x = 5; return x; }")
        # x = 5 should NOT create a temp — the literal goes directly into ASSIGN
        asgns = [a for a in assigns(result) if a["dest"] == "x"]
        assert asgns[0]["arg1"] == "5"   # literal, not a temp

    def test_identifier_rhs_no_extra_temp(self):
        result = compile_tac("int main() { int x = 5; int y = x; return y; }")
        y_asgns = [a for a in assigns(result) if a["dest"] == "y"]
        assert y_asgns[0]["arg1"] == "x"   # identifier, not a temp


# ===========================================================================
# 14. Label Generation
# ===========================================================================
class TestLabelGeneration:
    def test_labels_start_with_L(self):
        src = "int main() { int x = 0; if (x > 0) { x = 1; } return x; }"
        result = compile_tac(src)
        for lbl in labels(result):
            assert lbl["arg1"].startswith("L")

    def test_labels_are_unique_across_program(self):
        src = """
        int main() {
            int i = 0;
            while (i < 3) {
                if (i > 1) { i = i + 1; }
                i = i + 1;
            }
            return i;
        }
        """
        result = compile_tac(src)
        label_names = [l["arg1"] for l in labels(result)]
        assert len(label_names) == len(set(label_names))

    def test_jump_targets_exist_as_labels(self):
        src = """
        int main() {
            int x = 5;
            if (x > 0) { x = 1; } else { x = 0; }
            return x;
        }
        """
        result = compile_tac(src)
        label_names = {l["arg1"] for l in labels(result)}
        for jmp in jumps(result):
            # The jump target must be a declared label
            target = jmp["arg1"]
            assert target in label_names, f"Jump target {target} has no label"


# ===========================================================================
# 15. Validation Utility
# ===========================================================================
class TestValidationUtility:
    def test_valid_tac_passes_validation(self):
        result = compile_tac("int main() { int x = 5; return x; }")
        val = validate_instructions(result["instructions"])
        assert val["valid"] is True
        assert val["issues"] == []

    def test_missing_op_flagged(self):
        bad = [{"dest": "x", "arg1": "5", "arg2": None, "extra": None}]
        val = validate_instructions(bad)
        assert val["valid"] is False
        assert any("missing 'op'" in issue for issue in val["issues"])

    def test_unknown_opcode_flagged(self):
        bad = [{"op": "MAGIC", "dest": "x", "arg1": None, "arg2": None, "extra": None}]
        val = validate_instructions(bad)
        assert val["valid"] is False

    def test_duplicate_label_flagged(self):
        instrs = [
            {"op": "LABEL", "dest": None, "arg1": "L0", "arg2": None, "extra": None},
            {"op": "LABEL", "dest": None, "arg1": "L0", "arg2": None, "extra": None},
        ]
        val = validate_instructions(instrs)
        assert val["valid"] is False
        assert any("duplicate label" in issue for issue in val["issues"])

    def test_binop_missing_field_flagged(self):
        instrs = [
            {"op": "BINOP", "dest": "t0", "arg1": "a", "arg2": None, "extra": None}
        ]
        val = validate_instructions(instrs)
        assert val["valid"] is False

    def test_complex_program_validates(self):
        src = """
        int add(int a, int b) { return a + b; }
        int main() {
            int i = 0;
            while (i < 5) { i = i + 1; }
            int x = add(i, 2);
            return x;
        }
        """
        result = compile_tac(src)
        val = validate_instructions(result["instructions"])
        assert val["valid"] is True


# ===========================================================================
# 16. Semantically Invalid Programs Don't Reach TAC
# ===========================================================================
class TestInvalidProgramsBlocked:
    def test_undeclared_var_blocked(self):
        result = compile_tac("int main() { int x = ghost; return x; }")
        # Semantic analysis should have stopped us — instructions should be empty
        # (compile_tac returns early if semantic analysis fails)
        assert result["success"] is False

    def test_type_mismatch_blocked(self):
        result = compile_tac("int main() { int x = 3.14; return x; }")
        assert result["success"] is False

    def test_parse_error_blocked(self):
        result = compile_tac("int main() { int x = ; return x; }")
        assert result["success"] is False


# ===========================================================================
# 17. Human-Readable TAC Text Output
# ===========================================================================
class TestTACTextOutput:
    def test_text_is_string(self):
        result = compile_tac("int main() { return 0; }")
        assert isinstance(result["text"], str)

    def test_text_contains_return(self):
        result = compile_tac("int main() { return 0; }")
        assert "return" in result["text"]

    def test_text_contains_goto_for_while(self):
        src = "int main() { int i=0; while(i<3){ i=i+1; } return i; }"
        result = compile_tac(src)
        assert "goto" in result["text"]

    def test_text_contains_label_colon(self):
        src = "int main() { int x=5; if(x>0){ x=1; } return x; }"
        result = compile_tac(src)
        assert ":" in result["text"]

    def test_assign_text_format(self):
        result = compile_tac("int main() { int x = 5; return x; }")
        assert "x = 5" in result["text"]

    def test_binop_text_format(self):
        result = compile_tac("int main() { int x = 2 + 3; return x; }")
        # Should contain something like "t0 = 2 + 3"
        assert "+" in result["text"]

    def test_function_marker_in_text(self):
        result = compile_tac("int main() { return 0; }")
        assert "main" in result["text"]


# ===========================================================================
# 18. Result Dict Structure
# ===========================================================================
class TestResultDictStructure:
    def test_result_has_required_keys(self):
        result = compile_tac("int main() { return 0; }")
        assert "instructions" in result
        assert "text" in result
        assert "errors" in result
        assert "success" in result

    def test_instructions_is_list(self):
        result = compile_tac("int main() { return 0; }")
        assert isinstance(result["instructions"], list)

    def test_each_instruction_has_op(self):
        result = compile_tac("int main() { return 0; }")
        for instr in result["instructions"]:
            assert "op" in instr

    def test_each_instruction_has_all_fields(self):
        result = compile_tac("int main() { int x = 5; return x; }")
        for instr in result["instructions"]:
            for fld in ("op", "dest", "arg1", "arg2", "extra"):
                assert fld in instr

    def test_success_true_on_valid(self):
        result = compile_tac("int main() { return 0; }")
        assert result["success"] is True

    def test_success_false_on_invalid(self):
        result = compile_tac("int main() { return ghost; }")
        assert result["success"] is False
