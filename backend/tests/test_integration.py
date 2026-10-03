"""
tests/test_integration.py — Integration and Benchmark Suite for Phase 8.

Validates end-to-end compiler + ML optimization pipeline on held-out benchmark
programs and target pass benchmarks.
"""

import os
import glob
import pytest
from typing import Dict, Any

from api.pipeline import run_pipeline
import config


# Path to held-out test programs
TEST_PROGRAMS_DIR = os.path.join(config.BASE_DIR, "ml", "data", "test_programs")


class TestHeldOutBenchmarks:
    """Test full pipeline on the held-out benchmark files in ml/data/test_programs/."""

    def test_held_out_directory_exists(self):
        assert os.path.exists(TEST_PROGRAMS_DIR)
        assert os.path.isdir(TEST_PROGRAMS_DIR)

    def test_all_held_out_programs_pass_pipeline(self):
        c_files = glob.glob(os.path.join(TEST_PROGRAMS_DIR, "*.c"))
        assert len(c_files) >= 5, f"Expected at least 5 benchmark files in {TEST_PROGRAMS_DIR}"

        for filepath in c_files:
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            result = run_pipeline(code)
            assert result["success"] is True, f"Benchmark {os.path.basename(filepath)} failed pipeline: {result.get('errors')}"
            
            # Schema validation
            assert "phases" in result
            assert "ml" in result
            assert "stats" in result
            
            # Check phases populating
            phases = result["phases"]
            assert len(phases["tokens"]) > 0
            assert phases["ast"] is not None
            assert len(phases["symbol_table"]) > 0
            assert len(phases["semantic_errors"]) == 0
            assert len(phases["tac_before"]) > 0
            assert len(phases["tac_after"]) > 0

            # Check ML block
            ml = result["ml"]
            assert "features" in ml
            assert len(ml["features"]) == 15
            assert "recommendations" in ml
            assert len(ml["recommendations"]) == 5
            
            for rec in ml["recommendations"]:
                assert "pass" in rec
                assert 0.0 <= rec["confidence"] <= 1.0
                assert isinstance(rec["applied"], bool)
                assert rec["result_type"] == "ESTIMATED"

            # Check stats block
            stats = result["stats"]
            assert stats["instructions_before"] >= stats["instructions_after"]
            assert stats["reduction_count"] >= 0
            assert stats["reduction_percent"] >= 0.0
            assert stats["result_type"] == "MEASURED"


class TestOptimizationPassBenchmarks:
    """Specific benchmark tests targeting each of the 5 optimization passes."""

    def test_constant_folding_benchmark(self):
        code = """
        int main() {
            int a = 100 + 200 * 3;
            float b = 1.5 + 2.5;
            return a;
        }
        """
        result = run_pipeline(code)
        assert result["success"] is True
        
        recommendations = {r["pass"]: r for r in result["ml"]["recommendations"]}
        assert "CONSTANT_FOLDING" in recommendations
        assert recommendations["CONSTANT_FOLDING"]["confidence"] >= 0.5
        assert "CONSTANT_FOLDING" in result["stats"]["passes_recommended"]

    def test_constant_propagation_benchmark(self):
        code = """
        int main() {
            int x = 10;
            int y = 20;
            int z = x + y + 5;
            return z;
        }
        """
        result = run_pipeline(code)
        assert result["success"] is True
        
        recommendations = {r["pass"]: r for r in result["ml"]["recommendations"]}
        assert "CONSTANT_PROPAGATION" in recommendations
        assert 0.0 <= recommendations["CONSTANT_PROPAGATION"]["confidence"] <= 1.0

    def test_cse_benchmark(self):
        code = """
        int main() {
            int a = 5;
            int b = 10;
            int x = a + b;
            int y = a + b;
            int z = x + y;
            return z;
        }
        """
        result = run_pipeline(code)
        assert result["success"] is True
        
        recommendations = {r["pass"]: r for r in result["ml"]["recommendations"]}
        assert "CSE" in recommendations
        assert isinstance(recommendations["CSE"]["applied"], bool)

    def test_dead_code_elimination_benchmark(self):
        code = """
        int main() {
            int active = 42;
            int unused1 = 100;
            int unused2 = unused1 + 50;
            return active;
        }
        """
        result = run_pipeline(code)
        assert result["success"] is True
        
        recommendations = {r["pass"]: r for r in result["ml"]["recommendations"]}
        assert "DEAD_CODE_ELIMINATION" in recommendations

    def test_strength_reduction_benchmark(self):
        code = """
        int main() {
            int val = 8;
            int mult4 = val * 4;
            int mult8 = val * 8;
            return mult4 + mult8;
        }
        """
        result = run_pipeline(code)
        assert result["success"] is True
        
        recommendations = {r["pass"]: r for r in result["ml"]["recommendations"]}
        assert "STRENGTH_REDUCTION" in recommendations
        assert recommendations["STRENGTH_REDUCTION"]["applied"] is True

    def test_comprehensive_multi_pass_benchmark(self):
        code = """
        int main() {
            int a = 10 + 5;
            int b = a * 2;
            int x = a * 4;
            int y = a * 4;
            int dead_var = 999;
            return b + x + y;
        }
        """
        result = run_pipeline(code)
        assert result["success"] is True
        
        applied = result["stats"]["passes_applied"]
        assert len(applied) >= 1
        assert result["stats"]["instructions_after"] <= result["stats"]["instructions_before"]


class TestErrorRecoveryAndEdgeCases:
    """Validate integration error handling and graceful degradation."""

    def test_syntax_error_handled_gracefully(self):
        code = "int main() { int x = ; return 0; }"
        result = run_pipeline(code)
        
        assert result["success"] is False
        assert "Syntax error" in result["error"] or "cannot proceed" in result["error"]
        assert len(result["errors"]) > 0
        assert result["ml"] is None
        assert result["stats"] is None

    def test_semantic_error_handled_gracefully(self):
        code = "int main() { int x = undeclared_var + 5; return 0; }"
        result = run_pipeline(code)
        
        assert result["success"] is False
        assert "Semantic error" in result["error"] or "cannot proceed" in result["error"]
        assert len(result["errors"]) > 0
        assert len(result["phases"]["semantic_errors"]) > 0
        assert result["ml"] is None
        assert result["stats"] is None

    def test_empty_program_handled(self):
        result = run_pipeline("")
        assert result["success"] is False
        assert len(result["errors"]) > 0
