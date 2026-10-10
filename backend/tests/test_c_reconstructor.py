"""
tests/test_c_reconstructor.py — Unit & integration tests for C code reconstruction
and ML Advisor Suggested C Code response fields.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.pipeline import run_pipeline
from compiler.parser import parse
from compiler.ir_generator import generate
from compiler.optimizer import apply
from compiler.c_reconstructor import reconstruct_c_code


class TestCReconstructor:
    """Tests verifying clean C code generation from optimized TAC and AST."""

    def test_multi_pass_c_code_no_tac_temporaries(self):
        source = """
        int main() {
            int a = 10 + 5;
            int b = a * 2;
            int x = a * 4;
            int y = a * 4;
            int dead_var = 999;
            return b + x + y;
        }
        """
        res = run_pipeline(source)
        assert res["success"] is True

        opt_c = res["phases"]["optimized_c_code"]
        opt_tac = res["phases"]["optimized_tac"]

        # 1. Suggested C code must NOT contain raw TAC temporary variables
        for temp in ["t0", "t1", "t2", "t3", "t4", "t5"]:
            assert temp not in opt_c, f"Found temporary '{temp}' in reconstructed C code"

        # 2. Optimized TAC must continue displaying intermediate representation
        assert "t0 =" in opt_tac or "t1 =" in opt_tac or "t2 =" in opt_tac

        # 3. Two representations must be different
        assert opt_c != opt_tac

        # 4. Must contain proper C declarations, assignments, and returns
        assert "int a = 15;" in opt_c
        assert "int b = a << 1;" in opt_c
        assert "int x = a << 2;" in opt_c
        assert "int y = a << 2;" in opt_c
        assert "int dead_var = 999;" in opt_c
        assert "return b + x + y;" in opt_c

        # 5. Must parse cleanly with the compiler's own parser
        parsed = parse(opt_c)
        assert parsed["success"] is True, f"Errors parsing optimized C: {parsed.get('errors')}"

    def test_functions_and_while_loop(self):
        source = """
        int add(int a, int b) {
            return a + b;
        }

        int main() {
            int x = 10;
            int y = 20;
            int sum = add(x, y);
            int i = 0;
            while (i < 5) {
                sum = sum + i;
                i = i + 1;
            }
            return sum;
        }
        """
        res = run_pipeline(source)
        assert res["success"] is True

        opt_c = res["phases"]["optimized_c_code"]

        # Verify function signatures and control flow preserved
        assert "int add(int a, int b) {" in opt_c
        assert "return a + b;" in opt_c
        assert "int main() {" in opt_c
        assert "while (i < 5) {" in opt_c
        assert "sum = sum + i;" in opt_c
        assert "i = i + 1;" in opt_c
        assert "return sum;" in opt_c

        # Must parse cleanly
        parsed = parse(opt_c)
        assert parsed["success"] is True

    def test_for_loop_and_if_else(self):
        source = """
        int main() {
            int total = 0;
            for (int i = 0; i < 10; i = i + 1) {
                if (i > 5) {
                    total = total + i * 4;
                } else {
                    total = total + i * 2;
                }
            }
            return total;
        }
        """
        p = parse(source)
        ir = generate(p["ast_node"])
        opt = apply(ir["instructions"], passes=["STRENGTH_REDUCTION"], ast=p["ast_node"])

        opt_c = reconstruct_c_code(opt.instructions_after, ast=p["ast_node"])

        assert "for (int i = 0; i < 10; i = i + 1) {" in opt_c
        assert "if (i > 5) {" in opt_c
        assert "} else {" in opt_c
        # Strength-reduced operations are safely converted to shifts
        assert "i << 2" in opt_c
        assert "i << 1" in opt_c

        parsed = parse(opt_c)
        assert parsed["success"] is True

    def test_cse_reconstructed_variable_reuse(self):
        source = """
        int main() {
            int a = 5;
            int b = 10;
            int x = a + b;
            int y = a + b;
            int z = x + y;
            return z;
        }
        """
        p = parse(source)
        ir = generate(p["ast_node"])
        opt = apply(ir["instructions"], passes=["CSE"], ast=p["ast_node"])

        opt_c = reconstruct_c_code(opt.instructions_after, ast=p["ast_node"])

        # CSE should reuse variable x for y
        assert "int x = a + b;" in opt_c
        assert "int y = x;" in opt_c
        assert "int z = x + y;" in opt_c

        parsed = parse(opt_c)
        assert parsed["success"] is True

    def test_constant_folding_and_floats(self):
        source = """
        int main() {
            int a = 100 + 200 * 3;
            float b = 1.5 + 2.5;
            int c = 4 * 8 - 2;
            return a;
        }
        """
        res = run_pipeline(source)
        assert res["success"] is True

        opt_c = res["phases"]["optimized_c_code"]
        assert "float b" in opt_c
        assert "int a" in opt_c
        assert "return a;" in opt_c

        parsed = parse(opt_c)
        assert parsed["success"] is True

    def test_fallback_reconstruction_without_ast(self):
        source = """
        int main() {
            int a = 10 + 5;
            int b = a * 2;
            return b;
        }
        """
        p = parse(source)
        ir = generate(p["ast_node"])
        opt = apply(ir["instructions"], passes=["CONSTANT_FOLDING", "STRENGTH_REDUCTION"])

        # Call reconstruct_c_code without passing ast
        opt_c = reconstruct_c_code(opt.instructions_after, ast=None)

        assert "int a = 15;" in opt_c
        assert "int b = a << 1;" in opt_c
        assert "return b;" in opt_c
        for temp in ["t0", "t1", "t2"]:
            assert temp not in opt_c

    def test_pipeline_response_keys_contract(self):
        source = "int main() { int x = 2 + 3; return x; }"
        res = run_pipeline(source)
        assert res["success"] is True

        phases = res["phases"]
        assert "optimized_c_code" in phases
        assert "optimized_code" in phases
        assert "optimized_tac" in phases
        assert "tac_after_text" in phases
        assert "tac_after" in phases

        # Top-level helper fields
        assert "optimized_c_code" in res
        assert "optimized_tac" in res

        assert isinstance(phases["optimized_c_code"], str)
        assert len(phases["optimized_c_code"]) > 0
        assert phases["optimized_c_code"] == phases["optimized_code"]
        assert phases["optimized_tac"] == phases["tac_after_text"]
