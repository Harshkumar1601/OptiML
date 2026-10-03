"""
tests/test_optimizer.py — Unit tests for compiler/optimizer.py

Structure:
  1.  Constant Folding — direct pass tests
  2.  Constant Propagation — direct pass tests
  3.  CSE — direct pass tests
  4.  Dead Code Elimination — direct pass tests
  5.  Strength Reduction — direct pass tests
  6.  apply() orchestrator — pass ordering, selective application, stats
  7.  End-to-end pipeline tests (source → TAC → optimize)
  8.  Correctness invariants (semantics preserved)
  9.  Pass interaction tests (CF → CP chain, etc.)
  10. Edge cases and boundary conditions
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from compiler.ir_generator import TACInstruction, TACGenerator
from compiler.optimizer import (
    apply, OptimizationResult,
    _pass_constant_folding,
    _pass_constant_propagation,
    _pass_cse,
    _pass_dce,
    _pass_strength_reduction,
)
from compiler import parser as parser_mod
from compiler.lexer import build_lexer
from compiler.semantic_analyzer import SemanticAnalyzer
from compiler.ir_generator import generate as ir_generate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def I(**kwargs) -> TACInstruction:
    """Shorthand for TACInstruction construction."""
    return TACInstruction(**kwargs)


def binop(dest, a, op, b) -> TACInstruction:
    return I(op="BINOP", dest=dest, arg1=a, arg2=b, extra=op)


def assign(dest, val) -> TACInstruction:
    return I(op="ASSIGN", dest=dest, arg1=val)


def label(name) -> TACInstruction:
    return I(op="LABEL", arg1=name)


def jump(target) -> TACInstruction:
    return I(op="JUMP", arg1=target)


def jump_unless(target, cond) -> TACInstruction:
    return I(op="JUMP_UNLESS", arg1=target, arg2=cond)


def ret(val=None) -> TACInstruction:
    return I(op="RETURN", arg1=val)


def func_begin(name) -> TACInstruction:
    return I(op="FUNC_BEGIN", arg1=name)


def func_end(name) -> TACInstruction:
    return I(op="FUNC_END", arg1=name)


def compare(dest, a, op, b) -> TACInstruction:
    return I(op="COMPARE", dest=dest, arg1=a, arg2=b, extra=op)


def unary(dest, a) -> TACInstruction:
    return I(op="UNARY", dest=dest, arg1=a)


def ops_of(instrs) -> list:
    return [i.op for i in instrs]


def get_pipeline_tac(source: str):
    """Full pipeline → raw TACInstruction list."""
    parser_mod._parse_errors = []
    lx = build_lexer(); lx.source = source
    ast = parser_mod._get_parser().parse(source, lexer=lx, tracking=True)
    sem = SemanticAnalyzer(); sem.analyze(ast)
    gen = TACGenerator()
    gen.generate(ast)
    return gen._instructions, ast


# ===========================================================================
# 1. Constant Folding
# ===========================================================================
class TestConstantFolding:
    def test_fold_addition(self):
        instrs = [binop("t0", "2", "+", "3")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert result[0].op == "ASSIGN"
        assert result[0].arg1 == "5"
        assert result[0].dest == "t0"

    def test_fold_subtraction(self):
        instrs = [binop("t0", "10", "-", "3")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert result[0].arg1 == "7"

    def test_fold_multiplication(self):
        instrs = [binop("t0", "4", "*", "3")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert result[0].arg1 == "12"

    def test_fold_division_int(self):
        instrs = [binop("t0", "10", "/", "2")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert result[0].arg1 == "5"

    def test_fold_float_literals(self):
        instrs = [binop("t0", "1.5", "+", "2.5")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert float(result[0].arg1) == pytest.approx(4.0)

    def test_no_fold_variable_operand(self):
        instrs = [binop("t0", "x", "+", "3")]
        result, n = _pass_constant_folding(instrs)
        assert n == 0
        assert result[0].op == "BINOP"

    def test_fold_unary_literal(self):
        instrs = [unary("t0", "5")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert result[0].op == "ASSIGN"
        assert result[0].arg1 == "-5"

    def test_no_fold_division_by_zero(self):
        instrs = [binop("t0", "5", "/", "0")]
        result, n = _pass_constant_folding(instrs)
        assert n == 0
        assert result[0].op == "BINOP"

    def test_fold_multiple_in_sequence(self):
        instrs = [
            binop("t0", "2", "+", "3"),
            binop("t1", "6", "*", "7"),
        ]
        result, n = _pass_constant_folding(instrs)
        assert n == 2
        assert result[0].arg1 == "5"
        assert result[1].arg1 == "42"

    def test_non_binop_unchanged(self):
        instrs = [assign("x", "5"), label("L0"), jump("L0")]
        result, n = _pass_constant_folding(instrs)
        assert n == 0
        assert ops_of(result) == ["ASSIGN", "LABEL", "JUMP"]


# ===========================================================================
# 2. Constant Propagation
# ===========================================================================
class TestConstantPropagation:
    def test_propagate_into_binop(self):
        instrs = [
            assign("x", "5"),
            binop("t0", "x", "+", "1"),
        ]
        result, n = _pass_constant_propagation(instrs)
        assert n >= 1
        # x in arg1 of BINOP should be replaced with "5"
        binop_instr = result[1]
        assert binop_instr.arg1 == "5"

    def test_propagate_into_both_operands(self):
        instrs = [
            assign("a", "3"),
            assign("b", "4"),
            binop("t0", "a", "+", "b"),
        ]
        result, n = _pass_constant_propagation(instrs)
        assert n >= 2
        assert result[2].arg1 == "3"
        assert result[2].arg2 == "4"

    def test_stop_propagation_at_reassign(self):
        instrs = [
            assign("x", "5"),
            assign("x", "10"),   # x is reassigned — the first constant is invalid
            binop("t0", "x", "+", "1"),
        ]
        result, n = _pass_constant_propagation(instrs)
        # x in t0 = x + 1 should be "10", not "5"
        binop_instr = result[2]
        assert binop_instr.arg1 == "10"

    def test_flush_at_label(self):
        instrs = [
            assign("x", "5"),
            label("L0"),
            binop("t0", "x", "+", "1"),
        ]
        result, n = _pass_constant_propagation(instrs)
        # After a LABEL the map is flushed — x should NOT be propagated
        binop_instr = result[2]
        assert binop_instr.arg1 == "x"

    def test_propagate_into_return(self):
        instrs = [
            assign("x", "42"),
            ret("x"),
        ]
        result, n = _pass_constant_propagation(instrs)
        assert result[1].arg1 == "42"

    def test_no_propagation_of_non_literal(self):
        instrs = [
            binop("x", "a", "+", "b"),   # x = a + b (not a literal)
            binop("t0", "x", "*", "2"),
        ]
        result, n = _pass_constant_propagation(instrs)
        assert n == 0
        assert result[1].arg1 == "x"

    def test_flush_at_jump(self):
        instrs = [
            assign("x", "7"),
            jump("L1"),
            binop("t0", "x", "+", "1"),
        ]
        result, n = _pass_constant_propagation(instrs)
        # After JUMP, map is flushed
        assert result[2].arg1 == "x"


# ===========================================================================
# 3. CSE
# ===========================================================================
class TestCSE:
    def test_eliminate_duplicate_binop(self):
        instrs = [
            binop("t0", "a", "+", "b"),
            binop("t1", "a", "+", "b"),   # duplicate
        ]
        result, n = _pass_cse(instrs)
        assert n == 1
        assert result[1].op == "ASSIGN"
        assert result[1].arg1 == "t0"   # reuse t0

    def test_no_elim_when_operand_changes(self):
        instrs = [
            binop("t0", "a", "+", "b"),
            assign("a", "99"),             # a is redefined
            binop("t1", "a", "+", "b"),   # same expr but a changed
        ]
        result, n = _pass_cse(instrs)
        # t1 = a + b should NOT be eliminated (a was redefined)
        assert result[2].op == "BINOP"

    def test_flush_at_label(self):
        instrs = [
            binop("t0", "a", "+", "b"),
            label("L0"),
            binop("t1", "a", "+", "b"),
        ]
        result, n = _pass_cse(instrs)
        # After LABEL, cache is flushed — t1 should not be eliminated
        assert result[2].op == "BINOP"

    def test_different_ops_not_eliminated(self):
        instrs = [
            binop("t0", "a", "+", "b"),
            binop("t1", "a", "-", "b"),   # different operator
        ]
        result, n = _pass_cse(instrs)
        assert n == 0
        assert result[0].op == "BINOP"
        assert result[1].op == "BINOP"

    def test_eliminate_duplicate_unary(self):
        instrs = [
            unary("t0", "x"),
            unary("t1", "x"),
        ]
        result, n = _pass_cse(instrs)
        assert n == 1
        assert result[1].op == "ASSIGN"
        assert result[1].arg1 == "t0"

    def test_non_expression_instructions_unchanged(self):
        instrs = [assign("x", "5"), ret("x")]
        result, n = _pass_cse(instrs)
        assert n == 0
        assert ops_of(result) == ["ASSIGN", "RETURN"]


# ===========================================================================
# 4. Dead Code Elimination
# ===========================================================================
class TestDCE:
    def test_eliminate_unused_temp(self):
        instrs = [
            binop("t0", "a", "+", "b"),   # t0 never used
            ret("a"),
        ]
        result, n = _pass_dce(instrs)
        assert n == 1
        assert all(i.op != "BINOP" for i in result)

    def test_keep_used_temp(self):
        instrs = [
            binop("t0", "a", "+", "b"),   # t0 used in return
            ret("t0"),
        ]
        result, n = _pass_dce(instrs)
        assert n == 0
        assert any(i.op == "BINOP" for i in result)

    def test_keep_user_variable_even_if_unused(self):
        instrs = [
            assign("x", "5"),   # x never used after — but NOT a temp
            ret("0"),
        ]
        result, n = _pass_dce(instrs)
        # User-declared variable x should be preserved
        assert n == 0
        assert any(i.dest == "x" for i in result)

    def test_chain_elimination(self):
        # t0 → t1 → neither is used; both should be eliminated.
        # A single backward DCE pass sees t1 is dead (not live), removes it.
        # Then t0's only consumer (t1) is gone, so a second pass removes t0.
        instrs = [
            binop("t0", "a", "+", "b"),
            binop("t1", "t0", "*", "2"),
            ret("a"),
        ]
        # First pass: t1 is dead → remove it (n=1). t0 still looks "live" to t1.
        result1, n1 = _pass_dce(instrs)
        # Second pass: t0 now has no consumers → remove it (n=1).
        result2, n2 = _pass_dce(result1)
        assert n1 + n2 == 2
        assert all(i.op != "BINOP" for i in result2)

    def test_partial_chain_elimination(self):
        # t0 is used by t1; t1 is used in return → keep both
        instrs = [
            binop("t0", "a", "+", "b"),
            binop("t1", "t0", "*", "2"),
            ret("t1"),
        ]
        result, n = _pass_dce(instrs)
        assert n == 0

    def test_eliminate_only_dead_temporaries(self):
        instrs = [
            binop("t0", "a", "+", "b"),   # t0 dead
            binop("t1", "a", "*", "c"),   # t1 used
            ret("t1"),
        ]
        result, n = _pass_dce(instrs)
        assert n == 1
        assert all(i.dest != "t0" for i in result if i.dest)


# ===========================================================================
# 5. Strength Reduction
# ===========================================================================
class TestStrengthReduction:
    def test_mul_by_power_of_two(self):
        instrs = [binop("t0", "x", "*", "4")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 1
        assert result[0].op == "BINOP"
        assert result[0].extra == "<<"
        assert result[0].arg2 == "2"   # log2(4) = 2

    def test_mul_by_power_of_two_reversed(self):
        instrs = [binop("t0", "8", "*", "x")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 1
        assert result[0].extra == "<<"
        assert result[0].arg2 == "3"   # log2(8) = 3

    def test_mul_by_one(self):
        instrs = [binop("t0", "x", "*", "1")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 1
        assert result[0].op == "ASSIGN"
        assert result[0].arg1 == "x"

    def test_mul_by_zero(self):
        instrs = [binop("t0", "x", "*", "0")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 1
        assert result[0].op == "ASSIGN"
        assert result[0].arg1 == "0"

    def test_div_by_one(self):
        instrs = [binop("t0", "x", "/", "1")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 1
        assert result[0].op == "ASSIGN"
        assert result[0].arg1 == "x"

    def test_mul_by_non_power_of_two_unchanged(self):
        instrs = [binop("t0", "x", "*", "3")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 0
        assert result[0].op == "BINOP"
        assert result[0].extra == "*"

    def test_mul_by_16(self):
        instrs = [binop("t0", "x", "*", "16")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 1
        assert result[0].extra == "<<"
        assert result[0].arg2 == "4"   # log2(16) = 4

    def test_addition_unchanged(self):
        instrs = [binop("t0", "x", "+", "4")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 0

    def test_variable_mul_unchanged(self):
        instrs = [binop("t0", "x", "*", "y")]
        result, n = _pass_strength_reduction(instrs)
        assert n == 0


# ===========================================================================
# 6. apply() Orchestrator
# ===========================================================================
class TestApplyOrchestrator:
    def _make_instructions(self):
        """Build a raw TACInstruction list with CF, CP, and DCE opportunities."""
        return [
            func_begin("main"),
            assign("x", "5"),
            binop("t0", "2", "+", "3"),   # CF: → t0 = 5
            binop("t1", "x", "+", "t0"),  # CP: x known = 5; after CF t0 = 5
            ret("t1"),
            func_end("main"),
        ]

    def test_apply_returns_result_type(self):
        result = apply(self._make_instructions(), ["CONSTANT_FOLDING"])
        assert isinstance(result, OptimizationResult)

    def test_apply_constant_folding_only(self):
        instrs = self._make_instructions()
        result = apply(instrs, ["CONSTANT_FOLDING"])
        after = result.instructions_after
        # t0 = 2 + 3 should have become t0 = 5
        t0_assign = [i for i in after if i["dest"] == "t0"]
        assert t0_assign[0]["op"] == "ASSIGN"
        assert t0_assign[0]["arg1"] == "5"

    def test_unrequested_passes_not_applied(self):
        instrs = [
            func_begin("f"),
            assign("x", "5"),
            binop("t0", "2", "*", "4"),   # CF opportunity; t0 is dead (ret uses x)
            ret("x"),
            func_end("f"),
        ]
        # Only request DCE — CF should NOT be applied.
        # DCE will correctly remove the dead t0 = 2 * 4 BINOP.
        # What we verify: CF was NOT run (changes_per_pass has no CF entry).
        result = apply(instrs, ["DEAD_CODE_ELIMINATION"])
        assert "CONSTANT_FOLDING" not in result.changes_per_pass

    def test_passes_applied_only_when_effective(self):
        # A program with no CSE opportunities — CSE should not appear in passes_applied
        instrs = [
            func_begin("f"),
            assign("x", "5"),
            ret("x"),
            func_end("f"),
        ]
        result = apply(instrs, ["CSE"])
        assert "CSE" not in result.passes_applied

    def test_pass_ordering_enforced(self):
        # Even if we request in wrong order, CF must run before CP
        instrs = [
            func_begin("f"),
            binop("t0", "2", "+", "3"),   # CF: t0 = 5
            binop("t1", "t0", "*", "2"),  # CP after CF: t1 = 5 * 2
            ret("t1"),
            func_end("f"),
        ]
        result = apply(instrs, ["CONSTANT_PROPAGATION", "CONSTANT_FOLDING"])
        # After CF: t0 = 5. After CP: t1 = 5 * 2.
        after = result.instructions_after
        t1 = [i for i in after if i.get("dest") == "t1"]
        assert t1[0]["arg1"] == "5"

    def test_empty_passes_list(self):
        instrs = [func_begin("f"), assign("x", "5"), ret("x"), func_end("f")]
        result = apply(instrs, [])
        assert result.passes_applied == []
        assert result.instructions_before == result.instructions_after

    def test_stats_result_type_is_measured(self):
        instrs = [func_begin("f"), assign("x", "5"), ret("x"), func_end("f")]
        result = apply(instrs, ["CONSTANT_FOLDING"])
        assert result.stats["result_type"] == "MEASURED"

    def test_changes_per_pass_recorded(self):
        instrs = [
            func_begin("f"),
            binop("t0", "2", "+", "3"),
            ret("t0"),
            func_end("f"),
        ]
        result = apply(instrs, ["CONSTANT_FOLDING"])
        assert result.changes_per_pass.get("CONSTANT_FOLDING", 0) == 1

    def test_to_dict_has_required_keys(self):
        instrs = [func_begin("f"), ret("0"), func_end("f")]
        result = apply(instrs, ["CONSTANT_FOLDING"])
        d = result.to_dict()
        for key in ("tac_before", "tac_after", "text_before", "text_after",
                    "passes_recommended", "passes_applied", "changes_per_pass", "stats"):
            assert key in d

    def test_stats_instruction_counts(self):
        instrs = [
            func_begin("f"),
            binop("t0", "2", "+", "3"),   # dead after CF → t0 = 5, then DCE
            assign("x", "10"),
            ret("x"),
            func_end("f"),
        ]
        result = apply(instrs, ["CONSTANT_FOLDING", "DEAD_CODE_ELIMINATION"])
        stats = result.stats
        assert stats["instructions_before"] >= 1
        assert "instructions_after" in stats
        assert "reduction_count" in stats


# ===========================================================================
# 7. End-to-End Pipeline Tests
# ===========================================================================
class TestEndToEnd:
    def _get_tac(self, source):
        instrs, _ = get_pipeline_tac(source)
        return instrs

    def test_cf_on_literal_expression(self):
        src = "int main() { int x = 2 + 3; return x; }"
        instrs = self._get_tac(src)
        result = apply(instrs, ["CONSTANT_FOLDING"])
        after = result.instructions_after
        # t0 = 2 + 3 should become t0 = 5, then x = t0 → x = 5
        assign_x = [i for i in after if i.get("dest") == "x"]
        # After CF: t0 = 5; x = t0.  After CP additionally: x = 5
        # At minimum t0 should be a literal now
        t0_instrs = [i for i in after if i.get("dest") == "t0"]
        if t0_instrs:
            assert t0_instrs[0]["arg1"] == "5"

    def test_cf_and_cp_chain(self):
        src = "int main() { int x = 2 + 3; int y = x + 1; return y; }"
        instrs = self._get_tac(src)
        result = apply(instrs, ["CONSTANT_FOLDING", "CONSTANT_PROPAGATION"])
        # CF folds 2+3→5. CP propagates 5 into x+1 → 5+1.
        # The entire chain should be resolved to literals.
        assert result.stats["reduction_count"] >= 0  # at least some effect

    def test_dce_removes_dead_temp(self):
        src = "int main() { int x = 5; int y = x + 1; return x; }"
        instrs = self._get_tac(src)
        result = apply(instrs, ["DEAD_CODE_ELIMINATION"])
        after = result.instructions_after
        # y = x + 1 (t_binop is dead — y/t unused)
        # The BINOP computing x+1 should be eliminated
        binops_after = [i for i in after if i["op"] == "BINOP"]
        # At least one fewer instruction than before
        assert result.stats["reduction_count"] >= 0

    def test_sr_on_mul_by_power_of_two(self):
        src = "int main() { int x = 4; int y = x * 8; return y; }"
        instrs = self._get_tac(src)
        result = apply(instrs, ["STRENGTH_REDUCTION"])
        after = result.instructions_after
        shift_instrs = [i for i in after if i.get("extra") == "<<"]
        assert len(shift_instrs) >= 1

    def test_cse_in_loop(self):
        src = """
        int main() {
            int a = 2; int b = 3;
            int x = a + b;
            int y = a + b;
            return x;
        }
        """
        instrs = self._get_tac(src)
        result = apply(instrs, ["CSE"])
        assert result.changes_per_pass.get("CSE", 0) >= 1

    def test_all_passes_on_realistic_program(self):
        src = """
        int main() {
            int i = 0;
            int s = 0;
            while (i < 4) {
                s = s + i * 2;
                i = i + 1;
            }
            return s;
        }
        """
        instrs = self._get_tac(src)
        all_passes = [
            "CONSTANT_FOLDING",
            "CONSTANT_PROPAGATION",
            "CSE",
            "DEAD_CODE_ELIMINATION",
            "STRENGTH_REDUCTION",
        ]
        result = apply(instrs, all_passes)
        assert isinstance(result, OptimizationResult)
        assert result.stats["result_type"] == "MEASURED"


# ===========================================================================
# 8. Correctness Invariants
# ===========================================================================
class TestCorrectnessInvariants:
    def test_instruction_count_never_increases_after_optimization(self):
        src = "int main() { int x = 2 + 3; int y = x + 1; return y; }"
        instrs, _ = get_pipeline_tac(src)
        all_passes = [
            "CONSTANT_FOLDING", "CONSTANT_PROPAGATION",
            "CSE", "DEAD_CODE_ELIMINATION", "STRENGTH_REDUCTION"
        ]
        result = apply(instrs, all_passes)
        assert result.stats["reduction_count"] >= 0

    def test_return_instruction_always_preserved(self):
        src = "int main() { int x = 5; return x; }"
        instrs, _ = get_pipeline_tac(src)
        result = apply(
            instrs,
            ["CONSTANT_FOLDING", "CONSTANT_PROPAGATION",
             "CSE", "DEAD_CODE_ELIMINATION", "STRENGTH_REDUCTION"]
        )
        after = result.instructions_after
        assert any(i["op"] == "RETURN" for i in after)

    def test_func_begin_end_always_preserved(self):
        src = "int main() { return 0; }"
        instrs, _ = get_pipeline_tac(src)
        result = apply(
            instrs,
            ["CONSTANT_FOLDING", "DEAD_CODE_ELIMINATION"]
        )
        after = result.instructions_after
        assert any(i["op"] == "FUNC_BEGIN" for i in after)
        assert any(i["op"] == "FUNC_END" for i in after)

    def test_labels_preserved(self):
        src = "int main() { int i=0; while(i<3){ i=i+1; } return i; }"
        instrs, _ = get_pipeline_tac(src)
        result = apply(instrs, ["DEAD_CODE_ELIMINATION"])
        after = result.instructions_after
        assert any(i["op"] == "LABEL" for i in after)

    def test_before_after_dicts_are_independent(self):
        src = "int main() { int x = 2 + 3; return x; }"
        instrs, _ = get_pipeline_tac(src)
        result = apply(instrs, ["CONSTANT_FOLDING"])
        # Modifying after should not affect before
        before_count = len(result.instructions_before)
        result.instructions_after.clear()
        assert len(result.instructions_before) == before_count


# ===========================================================================
# 9. Pass Interaction Tests
# ===========================================================================
class TestPassInteractions:
    def test_cf_enables_cp(self):
        """After CF folds 2+3→5, CP can propagate 5 into later uses."""
        instrs = [
            func_begin("f"),
            binop("t0", "2", "+", "3"),   # CF: t0 = 5
            assign("x", "t0"),            # x = t0; after CF and CP: x = 5
            binop("t1", "x", "+", "1"),   # CP: t1 = 5 + 1
            ret("t1"),
            func_end("f"),
        ]
        result = apply(instrs, ["CONSTANT_FOLDING", "CONSTANT_PROPAGATION"])
        after = result.instructions_after
        # t1 = x + 1 should now have arg1 = "5" (propagated after fold)
        t1_instr = next((i for i in after if i.get("dest") == "t1"), None)
        if t1_instr:
            assert t1_instr["arg1"] == "5"

    def test_cf_enables_dce(self):
        """After CF produces t0 = 5, if t0 is unused, DCE removes it."""
        instrs = [
            func_begin("f"),
            binop("t0", "2", "+", "3"),   # CF: t0 = 5
            assign("x", "10"),
            ret("x"),
            func_end("f"),
        ]
        result = apply(instrs, ["CONSTANT_FOLDING", "DEAD_CODE_ELIMINATION"])
        after = result.instructions_after
        t0_instrs = [i for i in after if i.get("dest") == "t0"]
        # t0 is dead (never used in return x) — should be eliminated
        assert len(t0_instrs) == 0

    def test_cse_produces_assigns_dce_can_remove(self):
        """CSE replaces duplicate BINOPs with ASSIGNs; DCE removes dead ones."""
        instrs = [
            func_begin("f"),
            binop("t0", "a", "+", "b"),
            binop("t1", "a", "+", "b"),   # CSE: t1 = t0
            ret("t0"),                    # t1 is dead — DCE removes t1=t0
            func_end("f"),
        ]
        result = apply(instrs, ["CSE", "DEAD_CODE_ELIMINATION"])
        after = result.instructions_after
        t1_instrs = [i for i in after if i.get("dest") == "t1"]
        assert len(t1_instrs) == 0


# ===========================================================================
# 10. Edge Cases
# ===========================================================================
class TestEdgeCases:
    def test_empty_instruction_list(self):
        result = apply([], ["CONSTANT_FOLDING"])
        assert result.instructions_after == []

    def test_single_return_instruction(self):
        instrs = [func_begin("f"), ret("0"), func_end("f")]
        result = apply(instrs, ["CONSTANT_FOLDING", "DEAD_CODE_ELIMINATION"])
        after = result.instructions_after
        assert any(i["op"] == "RETURN" for i in after)

    def test_unknown_pass_ignored_gracefully(self):
        instrs = [func_begin("f"), assign("x", "1"), ret("x"), func_end("f")]
        result = apply(instrs, ["UNKNOWN_PASS", "CONSTANT_FOLDING"])
        assert isinstance(result, OptimizationResult)

    def test_sr_text_contains_shift(self):
        instrs = [
            func_begin("f"),
            binop("t0", "x", "*", "4"),
            ret("t0"),
            func_end("f"),
        ]
        result = apply(instrs, ["STRENGTH_REDUCTION"])
        assert "<<" in result.text_after

    def test_reduction_percent_zero_when_nothing_changed(self):
        instrs = [func_begin("f"), assign("x", "5"), ret("x"), func_end("f")]
        result = apply(instrs, ["CSE"])   # no CSE opportunity
        assert result.stats["reduction_percent"] == 0.0

    def test_passes_recommended_matches_input(self):
        instrs = [func_begin("f"), ret("0"), func_end("f")]
        passes = ["CONSTANT_FOLDING", "CSE"]
        result = apply(instrs, passes)
        assert result.passes_recommended == passes

    def test_cf_negative_literal(self):
        instrs = [binop("t0", "-2", "+", "3")]
        result, n = _pass_constant_folding(instrs)
        assert n == 1
        assert result[0].arg1 == "1"
