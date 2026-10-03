"""
tests/test_pipeline.py — Integration tests for Phase 6 API pipeline.

Tests:
  - Pipeline serializers (tokens, AST, symbol table, TAC, ML, stats)
  - run_pipeline() happy path: success, correct keys, MEASURED stats
  - run_pipeline() error paths: parse errors, semantic errors
  - Flask route smoke tests: /health, /analyze, /tokenize, /model
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from api.pipeline import run_pipeline
from api.serializers import (
    serialize_tokens, serialize_ast, serialize_symbol_table,
    serialize_semantic_errors, serialize_tac, serialize_optimization,
    serialize_ml_prediction, assemble_response,
)
from compiler.lexer import tokenize
from compiler.parser import parse
from compiler.semantic_analyzer import analyze
from compiler.ir_generator import generate
from compiler.optimizer import apply
from ml.model import predict_passes
from ml.recommendation import generate_pass_explanations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flask_client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def simple_source():
    return "int main() { int x = 2 + 3; return x; }"


@pytest.fixture
def rich_source():
    return """
    int main() {
        int a = 10 + 20;
        int b = a * 8;
        int c = a + b;
        int d = a + b;
        return d;
    }
    """


# ---------------------------------------------------------------------------
# Serializer unit tests
# ---------------------------------------------------------------------------

class TestSerializers:

    def test_serialize_tokens_returns_list(self, simple_source):
        t = tokenize(simple_source)
        tokens = serialize_tokens(t)
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all("type" in tok for tok in tokens)

    def test_serialize_ast_returns_dict(self, simple_source):
        p = parse(simple_source)
        ast = serialize_ast(p)
        assert isinstance(ast, dict)
        assert ast.get("node") == "Program"

    def test_serialize_symbol_table(self, simple_source):
        p = parse(simple_source)
        s = analyze(p["ast_node"])
        st = serialize_symbol_table(s)
        assert isinstance(st, list)

    def test_serialize_semantic_errors_empty_on_valid(self, simple_source):
        p = parse(simple_source)
        s = analyze(p["ast_node"])
        errs = serialize_semantic_errors(s)
        assert errs == []

    def test_serialize_tac_has_instructions_and_text(self, simple_source):
        p = parse(simple_source)
        ir = generate(p["ast_node"])
        tac = serialize_tac(ir)
        assert "instructions" in tac
        assert "text" in tac
        assert len(tac["instructions"]) > 0

    def test_serialize_ml_prediction_structure(self, simple_source):
        p = parse(simple_source)
        ir = generate(p["ast_node"])
        pred = predict_passes(ir["instructions"], ast=p["ast_node"])
        exps = generate_pass_explanations(pred["features"], pred)
        ml_block = serialize_ml_prediction(pred, exps)

        assert "features" in ml_block
        assert "recommendations" in ml_block
        assert "model_info" in ml_block
        assert len(ml_block["recommendations"]) == 5
        for r in ml_block["recommendations"]:
            assert "pass" in r
            assert "confidence" in r
            assert "applied" in r
            assert "explanation" in r

    def test_assemble_response_top_level_keys(self, simple_source):
        p = parse(simple_source)
        t = tokenize(simple_source)
        s = analyze(p["ast_node"])
        ir = generate(p["ast_node"])
        pred = predict_passes(ir["instructions"], ast=p["ast_node"])
        exps = generate_pass_explanations(pred["features"], pred)
        opt = apply(ir["instructions"], passes=pred["recommended_passes"])

        resp = assemble_response(
            source_code=simple_source,
            tokenize_result=t,
            parse_result=p,
            semantic_result=s,
            ir_result=ir,
            ml_pred=pred,
            explanations=exps,
            opt_result=opt,
        )
        assert "success" in resp
        assert "source_code" in resp
        assert "phases" in resp
        assert "ml" in resp
        assert "stats" in resp


# ---------------------------------------------------------------------------
# Pipeline run_pipeline() tests
# ---------------------------------------------------------------------------

class TestPipeline:

    def test_happy_path_success(self, simple_source):
        result = run_pipeline(simple_source)
        assert result["success"] is True

    def test_happy_path_required_keys(self, simple_source):
        result = run_pipeline(simple_source)
        assert "phases" in result
        assert "ml" in result
        assert "stats" in result
        assert "source_code" in result

    def test_phases_contains_all_required_keys(self, simple_source):
        result = run_pipeline(simple_source)
        phases = result["phases"]
        for key in ("tokens", "ast", "symbol_table", "semantic_errors",
                    "tac_before", "tac_before_text", "tac_after", "tac_after_text"):
            assert key in phases, f"Missing key in phases: {key}"

    def test_stats_result_type_is_measured(self, simple_source):
        result = run_pipeline(simple_source)
        assert result["stats"]["result_type"] == "MEASURED"

    def test_stats_numeric_fields(self, simple_source):
        result = run_pipeline(simple_source)
        stats = result["stats"]
        assert isinstance(stats["instructions_before"], int)
        assert isinstance(stats["instructions_after"], int)
        assert isinstance(stats["reduction_count"], int)
        assert isinstance(stats["reduction_percent"], float)

    def test_rich_program_applies_passes(self, rich_source):
        result = run_pipeline(rich_source)
        assert result["success"] is True
        stats = result["stats"]
        assert len(stats["passes_recommended"]) > 0
        assert len(stats["passes_applied"]) > 0

    def test_ml_block_has_5_recommendations(self, simple_source):
        result = run_pipeline(simple_source)
        recs = result["ml"]["recommendations"]
        assert len(recs) == 5
        pass_names = {r["pass"] for r in recs}
        from config import OPTIMIZATION_PASSES
        assert pass_names == set(OPTIMIZATION_PASSES)

    def test_recommendations_result_type_estimated(self, simple_source):
        result = run_pipeline(simple_source)
        for r in result["ml"]["recommendations"]:
            assert r["result_type"] == "ESTIMATED"

    def test_applied_flag_consistent_with_stats(self, rich_source):
        result = run_pipeline(rich_source)
        applied_in_recs = {r["pass"] for r in result["ml"]["recommendations"] if r["applied"]}
        applied_in_stats = set(result["stats"]["passes_applied"])
        assert applied_in_recs == applied_in_stats

    def test_parse_error_returns_failure(self):
        result = run_pipeline("int main( { return 0; }")
        assert result["success"] is False
        assert "error" in result
        assert result["ml"] is None

    def test_semantic_error_returns_failure(self):
        result = run_pipeline("int main() { int x = undeclared + 5; return x; }")
        assert result["success"] is False
        assert result["errors"] is not None
        assert len(result["errors"]) > 0

    def test_partial_phases_on_semantic_error(self):
        result = run_pipeline("int main() { int x = undeclared + 5; return x; }")
        phases = result["phases"]
        # Tokens and AST were still collected before semantic failure
        assert len(phases["tokens"]) > 0
        assert phases["ast"] is not None


# ---------------------------------------------------------------------------
# Flask route integration tests
# ---------------------------------------------------------------------------

class TestRoutes:

    def test_health_returns_200(self, flask_client):
        resp = flask_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["status"] == "online"
        assert "model_loaded" in data

    def test_analyze_valid_program(self, flask_client, simple_source):
        resp = flask_client.post(
            "/api/analyze",
            json={"source_code": simple_source},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "phases" in data
        assert "ml" in data
        assert "stats" in data

    def test_analyze_semantic_error_returns_422(self, flask_client):
        resp = flask_client.post(
            "/api/analyze",
            json={"source_code": "int main() { int x = bad + 5; return x; }"},
            content_type="application/json",
        )
        assert resp.status_code == 422
        data = resp.get_json()
        assert data["success"] is False

    def test_analyze_missing_source_returns_400(self, flask_client):
        resp = flask_client.post(
            "/api/analyze",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_analyze_wrong_content_type_returns_400(self, flask_client):
        resp = flask_client.post(
            "/api/analyze",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_tokenize_endpoint(self, flask_client, simple_source):
        resp = flask_client.post(
            "/api/tokenize",
            json={"source_code": simple_source},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["tokens"], list)
        assert len(data["tokens"]) > 0

    def test_model_endpoint(self, flask_client):
        resp = flask_client.get("/api/model")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "model_loaded" in data
        assert "passes" in data
        assert "threshold" in data

    def test_unknown_endpoint_returns_404(self, flask_client):
        resp = flask_client.get("/api/nonexistent")
        assert resp.status_code == 404
