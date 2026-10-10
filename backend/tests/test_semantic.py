"""
tests/test_semantic.py — Unit tests for compiler/symbol_table.py
                         and compiler/semantic_analyzer.py.

All tests work at the pipeline level:
  source → parse() → ASTNode objects → analyze() → result dict

This means the tests also verify AST-to-semantic-analyzer integration.

Test categories:
  1.  Symbol table unit tests (direct API)
  2.  Valid programs — no errors expected
  3.  Undeclared variable errors
  4.  Duplicate declaration errors
  5.  Type mismatch errors (assignment)
  6.  Type mismatch errors (function arguments)
  7.  Return type errors
  8.  Missing return errors
  9.  Undeclared function call errors
  10. Argument count mismatch errors
  11. Scope / shadowing tests
  12. For-loop scoping tests
  13. Compound condition tests
  14. Result dict structure validation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from compiler.parser import parse
from compiler.semantic_analyzer import analyze, SemanticAnalyzer
from compiler.symbol_table import SymbolTable, DuplicateDeclarationError
from compiler import ast_nodes as N


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run(source: str) -> dict:
    """Parse source then run semantic analysis. Return the semantic result dict."""
    parse_result = parse(source)
    # Reconstruct ASTNode objects from the parse result
    # The parser returns them in p[0]; we need the raw AST objects.
    # We call parse() via the internal path that returns node objects.
    # Re-import and use the internal parser:
    from compiler import parser as parser_mod
    parser_mod._parse_errors = []
    from compiler.lexer import build_lexer
    lexer = build_lexer()
    lexer.source = source
    p = parser_mod._get_parser()
    ast_node = p.parse(source, lexer=lexer, tracking=True)
    if ast_node is None:
        return {"symbol_table": [], "errors": [{"code": "PARSE_FAILED"}], "success": False}
    analyzer = SemanticAnalyzer()
    return analyzer.analyze(ast_node)


def error_codes(result: dict) -> list:
    """Return just the list of error codes from a semantic result."""
    return [e["code"] for e in result["errors"]]


def has_error(result: dict, code: str) -> bool:
    return code in error_codes(result)


def sym_names(result: dict) -> list:
    return [s["name"] for s in result["symbol_table"]]


# ===========================================================================
# 1. Symbol Table Unit Tests
# ===========================================================================
class TestSymbolTableDirect:
    def test_initial_scope_level_is_zero(self):
        st = SymbolTable()
        assert st.scope_level == 0

    def test_push_pop_scope(self):
        st = SymbolTable()
        st.push_scope()
        assert st.scope_level == 1
        st.pop_scope()
        assert st.scope_level == 0

    def test_declare_and_lookup(self):
        st = SymbolTable()
        entry = {"name": "x", "kind": "variable", "type": "int", "line": 1}
        st.declare(entry)
        found = st.lookup("x")
        assert found is not None
        assert found["name"] == "x"
        assert found["type"] == "int"

    def test_lookup_nonexistent_returns_none(self):
        st = SymbolTable()
        assert st.lookup("nothere") is None

    def test_duplicate_in_same_scope_raises(self):
        st = SymbolTable()
        e1 = {"name": "x", "kind": "variable", "type": "int", "line": 1}
        e2 = {"name": "x", "kind": "variable", "type": "float", "line": 2}
        st.declare(e1)
        with pytest.raises(DuplicateDeclarationError):
            st.declare(e2)

    def test_same_name_in_inner_scope_allowed(self):
        st = SymbolTable()
        e1 = {"name": "x", "kind": "variable", "type": "int", "line": 1}
        st.declare(e1)
        st.push_scope()
        e2 = {"name": "x", "kind": "variable", "type": "float", "line": 5}
        st.declare(e2)   # should not raise
        found = st.lookup("x")
        assert found["type"] == "float"   # inner scope wins

    def test_lookup_after_pop_returns_outer(self):
        st = SymbolTable()
        e1 = {"name": "x", "kind": "variable", "type": "int", "line": 1}
        st.declare(e1)
        st.push_scope()
        e2 = {"name": "x", "kind": "variable", "type": "float", "line": 5}
        st.declare(e2)
        st.pop_scope()
        found = st.lookup("x")
        assert found["type"] == "int"     # back to outer

    def test_lookup_current_scope_only(self):
        st = SymbolTable()
        e1 = {"name": "x", "kind": "variable", "type": "int", "line": 1}
        st.declare(e1)
        st.push_scope()
        assert st.lookup_current("x") is None   # not in current scope
        assert st.lookup("x") is not None       # found in outer

    def test_to_list_returns_all_symbols(self):
        st = SymbolTable()
        st.declare({"name": "a", "kind": "variable", "type": "int", "line": 1})
        st.push_scope()
        st.declare({"name": "b", "kind": "variable", "type": "float", "line": 2})
        flat = st.to_list()
        names = [s["name"] for s in flat]
        assert "a" in names
        assert "b" in names

    def test_current_function_tracking(self):
        st = SymbolTable()
        assert st.current_function() is None
        entry = {"name": "foo", "kind": "function", "type": "int",
                 "return_type": "int", "param_types": [], "line": 1}
        st.set_current_function(entry)
        assert st.current_function()["name"] == "foo"
        st.set_current_function(None)
        assert st.current_function() is None


# ===========================================================================
# 2. Valid Programs — No Errors Expected
# ===========================================================================
class TestValidPrograms:
    def test_minimal_main(self):
        src = "int main() { return 0; }"
        result = run(src)
        assert result["success"] is True
        assert result["errors"] == []

    def test_declaration_with_init(self):
        src = "int main() { int x = 5; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_float_declaration(self):
        src = "float main() { float x = 3.14; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_assignment_after_declaration(self):
        src = "int main() { int x; x = 10; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_int_assigned_to_float_allowed(self):
        # int → float widening is allowed
        src = "float main() { float x = 5; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_arithmetic_expression(self):
        src = "int main() { int x = 2 + 3; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_function_with_params(self):
        src = """
        int add(int a, int b) {
            int result = a + b;
            return result;
        }
        int main() {
            int x = add(1, 2);
            return x;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_forward_call(self):
        # main() calls add() which is defined after main
        src = """
        int main() {
            int x = add(3, 4);
            return x;
        }
        int add(int a, int b) {
            return a + b;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_if_else_with_declared_vars(self):
        src = """
        int main() {
            int x = 5;
            if (x > 0) {
                int y = 1;
                y = y + 1;
            } else {
                int y = 0;
            }
            return x;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_while_loop(self):
        src = """
        int main() {
            int i = 0;
            while (i < 10) {
                i = i + 1;
            }
            return i;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_for_loop(self):
        src = """
        int main() {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) {
                s = s + i;
            }
            return s;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_unary_minus_int(self):
        src = "int main() { int x = -5; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_unary_minus_float(self):
        src = "float main() { float x = -3.14; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_function_call_as_stmt(self):
        src = """
        int helper() { return 1; }
        int main() { helper(); return 0; }
        """
        result = run(src)
        assert result["success"] is True

    def test_nested_if(self):
        src = """
        int main() {
            int x = 5;
            int y = 3;
            if (x > 0) {
                if (y > 0) {
                    x = x + y;
                }
            }
            return x;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_compound_and_condition(self):
        src = """
        int main() {
            int x = 1;
            int y = 2;
            if (x > 0 && y > 0) {
                x = x + y;
            }
            return x;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_multiple_functions(self):
        src = """
        int square(int x) { return x * x; }
        int cube(int x) { return x * x * x; }
        int main() {
            int a = square(3);
            int b = cube(2);
            return a + b;
        }
        """
        result = run(src)
        assert result["success"] is True


# ===========================================================================
# 3. Undeclared Variable Errors
# ===========================================================================
class TestUndeclaredVariable:
    def test_use_before_declaration(self):
        src = "int main() { x = 5; return 0; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_use_in_expression(self):
        src = "int main() { int x = y + 1; return x; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_use_in_return(self):
        src = "int main() { return z; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_use_in_condition(self):
        src = "int main() { if (undef > 0) { } return 0; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_use_in_while_condition(self):
        src = "int main() { while (ghost < 5) { } return 0; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_self_reference_in_init(self):
        # `int x = x + 1` — x is not declared at the point of its own init
        src = "int main() { int x = x + 1; return x; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_out_of_scope_variable(self):
        # y is declared inside the if block — not visible outside
        src = """
        int main() {
            if (1 == 1) { int y = 5; }
            int z = y;
            return z;
        }
        """
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_error_message_contains_variable_name(self):
        src = "int main() { int x = ghost; return x; }"
        result = run(src)
        errors = [e for e in result["errors"] if e["code"] == "UNDECLARED_VARIABLE"]
        assert any("ghost" in e["message"] for e in errors)

    def test_error_contains_line_number(self):
        src = "int main() {\n    int x = ghost;\n    return x;\n}"
        result = run(src)
        errors = [e for e in result["errors"] if e["code"] == "UNDECLARED_VARIABLE"]
        assert any(e["line"] is not None for e in errors)


# ===========================================================================
# 4. Duplicate Declaration Errors
# ===========================================================================
class TestDuplicateDeclaration:
    def test_duplicate_in_same_block(self):
        src = "int main() { int x; int x; return 0; }"
        result = run(src)
        assert has_error(result, "DUPLICATE_DECLARATION")

    def test_duplicate_with_different_types(self):
        src = "int main() { int x; float x; return 0; }"
        result = run(src)
        assert has_error(result, "DUPLICATE_DECLARATION")

    def test_duplicate_function_names(self):
        src = """
        int foo() { return 1; }
        int foo() { return 2; }
        int main() { return 0; }
        """
        result = run(src)
        assert has_error(result, "DUPLICATE_DECLARATION")

    def test_no_duplicate_in_different_blocks(self):
        # Same name in then-block and else-block is fine — different scopes
        src = """
        int main() {
            if (1 == 1) { int x = 1; }
            else        { int x = 2; }
            return 0;
        }
        """
        result = run(src)
        assert not has_error(result, "DUPLICATE_DECLARATION")

    def test_error_message_contains_name(self):
        src = "int main() { int x; int x; return 0; }"
        result = run(src)
        errors = [e for e in result["errors"] if e["code"] == "DUPLICATE_DECLARATION"]
        assert any("x" in e["message"] for e in errors)


# ===========================================================================
# 5. Type Mismatch — Assignment
# ===========================================================================
class TestTypeMismatchAssignment:
    def test_float_to_int_variable(self):
        src = "int main() { int x = 3.14; return x; }"
        result = run(src)
        assert has_error(result, "TYPE_MISMATCH")

    def test_float_expr_to_int(self):
        src = "int main() { float y = 1.5; int x = y; return x; }"
        result = run(src)
        assert has_error(result, "TYPE_MISMATCH")

    def test_int_to_float_allowed(self):
        src = "float main() { float x = 5; return x; }"
        result = run(src)
        assert not has_error(result, "TYPE_MISMATCH")

    def test_float_literal_assigned_to_float_ok(self):
        src = "float main() { float x = 2.5; return x; }"
        result = run(src)
        assert result["success"] is True

    def test_mixed_arithmetic_float_to_int(self):
        # int + float → float, assigned to int → mismatch
        src = "int main() { float y = 1.5; int x = 1 + y; return x; }"
        result = run(src)
        assert has_error(result, "TYPE_MISMATCH")

    def test_error_message_mentions_variable(self):
        src = "int main() { int myVar = 3.14; return myVar; }"
        result = run(src)
        errors = [e for e in result["errors"] if e["code"] == "TYPE_MISMATCH"]
        assert any("myVar" in e["message"] for e in errors)


# ===========================================================================
# 6. Type Mismatch — Function Arguments
# ===========================================================================
class TestTypeMismatchArgs:
    def test_float_arg_to_int_param(self):
        src = """
        int double_it(int x) { return x + x; }
        int main() { int r = double_it(1.5); return r; }
        """
        result = run(src)
        assert has_error(result, "TYPE_MISMATCH")

    def test_int_arg_to_float_param_ok(self):
        src = """
        float scale(float x) { return x; }
        int main() { float r = scale(3); return 0; }
        """
        result = run(src)
        assert not has_error(result, "TYPE_MISMATCH")


# ===========================================================================
# 7. Return Type Errors
# ===========================================================================
class TestReturnTypeErrors:
    def test_float_returned_from_int_function(self):
        src = "int main() { return 3.14; }"
        result = run(src)
        assert has_error(result, "RETURN_TYPE_MISMATCH")

    def test_int_returned_from_float_function_ok(self):
        # Widening: int → float is allowed
        src = "float main() { return 5; }"
        result = run(src)
        assert not has_error(result, "RETURN_TYPE_MISMATCH")

    def test_bare_return_in_typed_function(self):
        src = "int main() { return; }"
        result = run(src)
        assert has_error(result, "RETURN_TYPE_MISMATCH")

    def test_correct_return_type_no_error(self):
        src = "int main() { return 0; }"
        result = run(src)
        assert not has_error(result, "RETURN_TYPE_MISMATCH")


# ===========================================================================
# 8. Missing Return
# ===========================================================================
class TestMissingReturn:
    def test_function_with_no_return(self):
        src = "int main() { int x = 5; }"
        result = run(src)
        assert has_error(result, "MISSING_RETURN")

    def test_function_with_return_no_error(self):
        src = "int main() { return 0; }"
        result = run(src)
        assert not has_error(result, "MISSING_RETURN")

    def test_missing_return_in_helper_function(self):
        src = """
        int helper() { int x = 1; }
        int main() { return 0; }
        """
        result = run(src)
        # helper() should trigger MISSING_RETURN, main() should not
        missing = [e for e in result["errors"] if e["code"] == "MISSING_RETURN"]
        assert len(missing) == 1
        assert missing[0]["name"] == "helper"


# ===========================================================================
# 9. Undeclared Function Call
# ===========================================================================
class TestUndeclaredFunction:
    def test_call_to_undefined_function(self):
        src = "int main() { int x = ghost(); return x; }"
        result = run(src)
        assert has_error(result, "UNDECLARED_FUNCTION")

    def test_error_contains_function_name(self):
        src = "int main() { mystery(1, 2); return 0; }"
        result = run(src)
        errors = [e for e in result["errors"] if e["code"] == "UNDECLARED_FUNCTION"]
        assert any("mystery" in e["message"] for e in errors)

    def test_known_function_no_error(self):
        src = """
        int known() { return 1; }
        int main() { int x = known(); return x; }
        """
        result = run(src)
        assert not has_error(result, "UNDECLARED_FUNCTION")


# ===========================================================================
# 10. Argument Count Mismatch
# ===========================================================================
class TestArgumentCountMismatch:
    def test_too_few_args(self):
        src = """
        int add(int a, int b) { return a + b; }
        int main() { int x = add(1); return x; }
        """
        result = run(src)
        assert has_error(result, "ARGUMENT_COUNT_MISMATCH")

    def test_too_many_args(self):
        src = """
        int square(int x) { return x * x; }
        int main() { int r = square(2, 3, 4); return r; }
        """
        result = run(src)
        assert has_error(result, "ARGUMENT_COUNT_MISMATCH")

    def test_correct_arg_count_no_error(self):
        src = """
        int add(int a, int b) { return a + b; }
        int main() { int x = add(1, 2); return x; }
        """
        result = run(src)
        assert not has_error(result, "ARGUMENT_COUNT_MISMATCH")

    def test_zero_args_correct(self):
        src = """
        int one() { return 1; }
        int main() { int x = one(); return x; }
        """
        result = run(src)
        assert not has_error(result, "ARGUMENT_COUNT_MISMATCH")


# ===========================================================================
# 11. Scope / Shadowing Tests
# ===========================================================================
class TestScoping:
    def test_inner_scope_variable_not_visible_outside(self):
        src = """
        int main() {
            if (1 == 1) { int inner = 42; }
            int z = inner;
            return z;
        }
        """
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_outer_variable_visible_in_inner_scope(self):
        src = """
        int main() {
            int x = 10;
            if (x > 0) {
                x = x + 1;
            }
            return x;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_parameter_visible_in_function_body(self):
        src = """
        int double_it(int n) {
            return n + n;
        }
        int main() { return 0; }
        """
        result = run(src)
        assert result["success"] is True

    def test_variable_from_other_function_not_visible(self):
        src = """
        int foo() { int secret = 42; return secret; }
        int main() { int x = secret; return x; }
        """
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")


# ===========================================================================
# 12. For-Loop Scoping
# ===========================================================================
class TestForLoopScoping:
    def test_for_init_var_not_visible_after_loop(self):
        src = """
        int main() {
            for (int i = 0; i < 3; i = i + 1) { }
            int x = i;
            return x;
        }
        """
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_for_init_var_visible_in_body(self):
        src = """
        int main() {
            int s = 0;
            for (int i = 0; i < 5; i = i + 1) {
                s = s + i;
            }
            return s;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_for_outer_var_visible_in_body(self):
        src = """
        int main() {
            int total = 0;
            for (int i = 0; i < 3; i = i + 1) {
                total = total + 1;
            }
            return total;
        }
        """
        result = run(src)
        assert result["success"] is True


# ===========================================================================
# 13. Compound Condition Tests
# ===========================================================================
class TestCompoundConditions:
    def test_and_with_declared_vars(self):
        src = """
        int main() {
            int x = 1; int y = 2;
            if (x > 0 && y > 0) { x = x + y; }
            return x;
        }
        """
        result = run(src)
        assert result["success"] is True

    def test_or_with_undeclared_var(self):
        src = """
        int main() {
            int x = 1;
            if (x > 0 || ghost > 0) { }
            return x;
        }
        """
        result = run(src)
        assert has_error(result, "UNDECLARED_VARIABLE")

    def test_nested_condition(self):
        src = """
        int main() {
            int a = 1; int b = 2; int c = 3;
            if (a > 0 && b > 0 && c > 0) { return 1; }
            return 0;
        }
        """
        result = run(src)
        assert result["success"] is True


# ===========================================================================
# 14. Result Dict Structure
# ===========================================================================
class TestResultStructure:
    def test_result_has_required_keys(self):
        result = run("int main() { return 0; }")
        assert "symbol_table" in result
        assert "errors" in result
        assert "success" in result

    def test_symbol_table_is_list(self):
        result = run("int main() { return 0; }")
        assert isinstance(result["symbol_table"], list)

    def test_symbol_entry_has_required_fields(self):
        result = run("int main() { int x = 5; return x; }")
        var_entries = [s for s in result["symbol_table"] if s["name"] == "x"]
        assert len(var_entries) == 1
        entry = var_entries[0]
        assert "name" in entry
        assert "kind" in entry
        assert "type" in entry
        assert "line" in entry

    def test_function_in_symbol_table(self):
        result = run("int main() { return 0; }")
        funcs = [s for s in result["symbol_table"] if s["name"] == "main"]
        assert len(funcs) == 1
        assert funcs[0]["kind"] == "function"

    def test_error_has_required_fields(self):
        result = run("int main() { int x = ghost; return x; }")
        for err in result["errors"]:
            assert "code" in err
            assert "message" in err
            # line may be None for some errors
            assert "line" in err

    def test_success_false_on_error(self):
        result = run("int main() { int x = ghost; return x; }")
        assert result["success"] is False

    def test_success_true_on_valid(self):
        result = run("int main() { return 0; }")
        assert result["success"] is True

    def test_multiple_errors_all_reported(self):
        src = """
        int main() {
            int x = ghost1;
            int y = ghost2;
            int z = ghost3;
            return 0;
        }
        """
        result = run(src)
        undeclared = [e for e in result["errors"] if e["code"] == "UNDECLARED_VARIABLE"]
        assert len(undeclared) == 3


class TestDynamicSymbolEvaluation:
    def test_user_loop_and_function_symbol_evaluation(self):
        src = """
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
        result = run(src)
        assert result["success"] is True
        sym_map = {s["name"]: s["value"] for s in result["symbol_table"]}
        assert sym_map["x"] == "10"
        assert sym_map["y"] == "20"
        assert sym_map["sum"] == "40"
        assert sym_map["i"] == "5"
