"""
tests/test_parser.py — Unit tests for compiler/parser.py

Test categories:
  1.  Valid declarations (with and without initialization)
  2.  Assignments
  3.  Arithmetic expressions (precedence, associativity, nesting)
  4.  Unary minus
  5.  Function definitions (with/without params)
  6.  Function calls (as statement and expression)
  7.  If / if-else statements
  8.  While loops
  9.  For loops
  10. Return statements
  11. Conditions (relational, &&, ||, parenthesized)
  12. Comments in source (should not affect AST)
  13. Syntax error cases
  14. AST structure validation (checking node types and fields)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from compiler.parser import parse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def wrap(body: str) -> str:
    """Wrap a statement list in a minimal main() function for testing."""
    return f"int main() {{\n{body}\n}}"


def parse_ok(source: str) -> dict:
    """Assert success=True and return the AST dict."""
    result = parse(source)
    assert result["success"] is True, (
        f"Expected success but got errors: {result['errors']}"
    )
    assert result["ast"] is not None
    return result["ast"]


def parse_fail(source: str) -> list:
    """Assert success=False and return the error list."""
    result = parse(source)
    assert result["success"] is False, (
        f"Expected failure but parsing succeeded with AST: {result['ast']}"
    )
    return result["errors"]


def first_func(ast: dict) -> dict:
    """Return the first function definition from a program AST dict."""
    return ast["functions"][0]


def first_stmt(ast: dict) -> dict:
    """Return the first statement of the first function's body."""
    return first_func(ast)["body"]["statements"][0]


# ===========================================================================
# 1. Declarations
# ===========================================================================
class TestDeclarations:
    def test_int_declaration_no_init(self):
        ast = parse_ok(wrap("int x;"))
        s = first_stmt(ast)
        assert s["node"] == "Declaration"
        assert s["var_type"] == "int"
        assert s["name"] == "x"
        assert s["init_expr"] is None

    def test_float_declaration_no_init(self):
        ast = parse_ok(wrap("float y;"))
        s = first_stmt(ast)
        assert s["node"] == "Declaration"
        assert s["var_type"] == "float"

    def test_int_declaration_with_literal_init(self):
        ast = parse_ok(wrap("int x = 5;"))
        s = first_stmt(ast)
        assert s["node"] == "Declaration"
        assert s["init_expr"]["node"] == "IntLiteral"
        assert s["init_expr"]["value"] == 5

    def test_float_declaration_with_float_init(self):
        ast = parse_ok(wrap("float x = 3.14;"))
        s = first_stmt(ast)
        assert s["init_expr"]["node"] == "FloatLiteral"
        assert abs(s["init_expr"]["value"] - 3.14) < 1e-9

    def test_declaration_with_expr_init(self):
        ast = parse_ok(wrap("int x = 2 + 3;"))
        s = first_stmt(ast)
        assert s["init_expr"]["node"] == "BinOp"
        assert s["init_expr"]["op"] == "+"

    def test_multiple_declarations(self):
        ast = parse_ok(wrap("int a; int b; float c;"))
        stmts = first_func(ast)["body"]["statements"]
        assert len(stmts) == 3
        assert all(s["node"] == "Declaration" for s in stmts)


# ===========================================================================
# 2. Assignments
# ===========================================================================
class TestAssignments:
    def test_simple_assignment(self):
        ast = parse_ok(wrap("int x; x = 10;"))
        s = first_func(ast)["body"]["statements"][1]
        assert s["node"] == "Assignment"
        assert s["name"] == "x"
        assert s["expr"]["node"] == "IntLiteral"

    def test_assignment_with_binop(self):
        ast = parse_ok(wrap("int x; x = a + b;"))
        s = first_func(ast)["body"]["statements"][1]
        assert s["expr"]["node"] == "BinOp"

    def test_assignment_with_identifier_rhs(self):
        ast = parse_ok(wrap("int x; int y; x = y;"))
        s = first_func(ast)["body"]["statements"][2]
        assert s["expr"]["node"] == "Identifier"
        assert s["expr"]["name"] == "y"


# ===========================================================================
# 3. Arithmetic Expressions
# ===========================================================================
class TestArithmeticExpressions:
    def test_addition(self):
        ast = parse_ok(wrap("int x = a + b;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["node"] == "BinOp"
        assert expr["op"] == "+"
        assert expr["left"]["name"] == "a"
        assert expr["right"]["name"] == "b"

    def test_subtraction(self):
        ast = parse_ok(wrap("int x = a - b;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["op"] == "-"

    def test_multiplication(self):
        ast = parse_ok(wrap("int x = a * b;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["op"] == "*"

    def test_division(self):
        ast = parse_ok(wrap("int x = a / b;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["op"] == "/"

    def test_precedence_mul_over_add(self):
        # a + b * c → BinOp(+, a, BinOp(*, b, c))
        ast = parse_ok(wrap("int x = a + b * c;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["op"] == "+"
        assert expr["right"]["op"] == "*"

    def test_precedence_add_over_mul_with_parens(self):
        # (a + b) * c → BinOp(*, BinOp(+, a, b), c)
        ast = parse_ok(wrap("int x = (a + b) * c;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["op"] == "*"
        assert expr["left"]["op"] == "+"

    def test_left_associativity_add(self):
        # a + b + c → BinOp(+, BinOp(+, a, b), c)
        ast = parse_ok(wrap("int x = a + b + c;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["op"] == "+"
        assert expr["left"]["op"] == "+"   # left-associative

    def test_nested_parens(self):
        ast = parse_ok(wrap("int x = ((a + b));"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["node"] == "BinOp"


# ===========================================================================
# 4. Unary Minus
# ===========================================================================
class TestUnaryMinus:
    def test_unary_minus_literal(self):
        ast = parse_ok(wrap("int x = -5;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["node"] == "UnaryOp"
        assert expr["op"] == "-"
        assert expr["operand"]["node"] == "IntLiteral"
        assert expr["operand"]["value"] == 5

    def test_unary_minus_identifier(self):
        ast = parse_ok(wrap("int x = -y;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["node"] == "UnaryOp"
        assert expr["operand"]["node"] == "Identifier"

    def test_unary_minus_subexpr(self):
        ast = parse_ok(wrap("int x = -(a + b);"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["node"] == "UnaryOp"
        assert expr["operand"]["node"] == "BinOp"

    def test_double_unary_minus(self):
        ast = parse_ok(wrap("int x = --y;"))
        expr = first_stmt(ast)["init_expr"]
        assert expr["node"] == "UnaryOp"
        assert expr["operand"]["node"] == "UnaryOp"


# ===========================================================================
# 5. Function Definitions
# ===========================================================================
class TestFunctionDefinitions:
    def test_main_no_params(self):
        ast = parse_ok("int main() { return 0; }")
        func = first_func(ast)
        assert func["node"] == "FunctionDef"
        assert func["name"] == "main"
        assert func["return_type"] == "int"
        assert func["params"] == []

    def test_function_with_params(self):
        ast = parse_ok("int add(int a, int b) { return a; }")
        func = first_func(ast)
        assert len(func["params"]) == 2
        assert func["params"][0]["name"] == "a"
        assert func["params"][0]["type"] == "int"
        assert func["params"][1]["name"] == "b"

    def test_function_float_return(self):
        ast = parse_ok("float average(int a, int b) { return a; }")
        func = first_func(ast)
        assert func["return_type"] == "float"

    def test_multiple_functions(self):
        src = """
        int foo() { return 1; }
        int bar() { return 2; }
        """
        ast = parse_ok(src)
        assert len(ast["functions"]) == 2
        assert ast["functions"][0]["name"] == "foo"
        assert ast["functions"][1]["name"] == "bar"

    def test_empty_body(self):
        ast = parse_ok("int main() { }")
        func = first_func(ast)
        assert func["body"]["statements"] == []


# ===========================================================================
# 6. Function Calls
# ===========================================================================
class TestFunctionCalls:
    def test_func_call_no_args_as_stmt(self):
        ast = parse_ok(wrap("foo();"))
        s = first_stmt(ast)
        assert s["node"] == "FuncCallStmt"
        assert s["call_expr"]["name"] == "foo"
        assert s["call_expr"]["args"] == []

    def test_func_call_with_args_as_stmt(self):
        ast = parse_ok(wrap("bar(x, y);"))
        s = first_stmt(ast)
        assert s["call_expr"]["name"] == "bar"
        assert len(s["call_expr"]["args"]) == 2

    def test_func_call_as_expr_in_declaration(self):
        ast = parse_ok(wrap("int x = add(1, 2);"))
        init = first_stmt(ast)["init_expr"]
        assert init["node"] == "FuncCallExpr"
        assert init["name"] == "add"
        assert len(init["args"]) == 2

    def test_func_call_arg_is_expr(self):
        ast = parse_ok(wrap("int x = foo(a + b);"))
        init = first_stmt(ast)["init_expr"]
        assert init["args"][0]["node"] == "BinOp"


# ===========================================================================
# 7. If / If-Else
# ===========================================================================
class TestIfStatements:
    def test_if_no_else(self):
        ast = parse_ok(wrap("if (x > 0) { return x; }"))
        s = first_stmt(ast)
        assert s["node"] == "If"
        assert s["else_block"] is None

    def test_if_with_else(self):
        ast = parse_ok(wrap("if (x > 0) { return x; } else { return 0; }"))
        s = first_stmt(ast)
        assert s["node"] == "If"
        assert s["then_block"] is not None
        assert s["else_block"] is not None

    def test_if_condition_structure(self):
        ast = parse_ok(wrap("if (a < b) { return a; }"))
        cond = first_stmt(ast)["condition"]
        assert cond["node"] == "Condition"
        assert cond["op"] == "<"

    def test_nested_if(self):
        src = wrap("if (x > 0) { if (y > 0) { return 1; } }")
        ast = parse_ok(src)
        outer = first_stmt(ast)
        inner = outer["then_block"]["statements"][0]
        assert inner["node"] == "If"


# ===========================================================================
# 8. While Loops
# ===========================================================================
class TestWhileLoops:
    def test_while_loop(self):
        ast = parse_ok(wrap("while (i < 10) { i = i + 1; }"))
        s = first_stmt(ast)
        assert s["node"] == "While"
        assert s["condition"]["op"] == "<"
        assert len(s["body"]["statements"]) == 1

    def test_empty_while_body(self):
        ast = parse_ok(wrap("while (x < 5) { }"))
        s = first_stmt(ast)
        assert s["body"]["statements"] == []


# ===========================================================================
# 9. For Loops
# ===========================================================================
class TestForLoops:
    def test_for_loop_with_declaration_init(self):
        src = wrap("for (int i = 0; i < 10; i = i + 1) { }")
        ast = parse_ok(src)
        s = first_stmt(ast)
        assert s["node"] == "For"
        assert s["init"]["node"] == "Declaration"
        assert s["condition"]["op"] == "<"
        assert s["update"]["node"] == "Assignment"

    def test_for_loop_with_assignment_init(self):
        src = wrap("int i; for (i = 0; i < 5; i = i + 1) { }")
        ast = parse_ok(src)
        for_stmt = first_func(ast)["body"]["statements"][1]
        assert for_stmt["node"] == "For"
        assert for_stmt["init"]["node"] == "Assignment"

    def test_for_loop_body(self):
        src = wrap("for (int i = 0; i < 3; i = i + 1) { int x = i; }")
        ast = parse_ok(src)
        s = first_stmt(ast)
        assert len(s["body"]["statements"]) == 1


# ===========================================================================
# 10. Return Statements
# ===========================================================================
class TestReturnStatements:
    def test_return_with_literal(self):
        ast = parse_ok(wrap("return 0;"))
        s = first_stmt(ast)
        assert s["node"] == "Return"
        assert s["expr"]["node"] == "IntLiteral"
        assert s["expr"]["value"] == 0

    def test_return_with_expression(self):
        ast = parse_ok(wrap("return a + b;"))
        s = first_stmt(ast)
        assert s["expr"]["node"] == "BinOp"

    def test_return_identifier(self):
        ast = parse_ok(wrap("return x;"))
        s = first_stmt(ast)
        assert s["expr"]["node"] == "Identifier"

    def test_bare_return(self):
        src = "int main() { return; }"
        ast = parse_ok(src)
        s = first_stmt(ast)
        assert s["node"] == "Return"
        assert s["expr"] is None


# ===========================================================================
# 11. Conditions
# ===========================================================================
class TestConditions:
    def test_less_than(self):
        ast = parse_ok(wrap("if (a < b) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == "<"

    def test_greater_equal(self):
        ast = parse_ok(wrap("if (a >= b) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == ">="

    def test_equality(self):
        ast = parse_ok(wrap("if (a == b) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == "=="

    def test_not_equal(self):
        ast = parse_ok(wrap("if (a != b) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == "!="

    def test_and_condition(self):
        ast = parse_ok(wrap("if (a > 0 && b > 0) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == "&&"
        assert cond["left"]["node"] == "Condition"
        assert cond["right"]["node"] == "Condition"

    def test_or_condition(self):
        ast = parse_ok(wrap("if (a < 0 || b < 0) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == "||"

    def test_parenthesized_condition(self):
        ast = parse_ok(wrap("if ((a > 0) && (b > 0)) { }"))
        cond = first_stmt(ast)["condition"]
        assert cond["op"] == "&&"


# ===========================================================================
# 12. Comments in Source
# ===========================================================================
class TestCommentsInSource:
    def test_comments_dont_affect_ast(self):
        src_with = wrap("// declare x\nint x = 5; /* init */")
        src_without = wrap("int x = 5;")
        ast1 = parse_ok(src_with)
        ast2 = parse_ok(src_without)
        # Both should produce identical AST structure
        s1 = first_stmt(ast1)
        s2 = first_stmt(ast2)
        assert s1["node"] == s2["node"]
        assert s1["var_type"] == s2["var_type"]
        assert s1["name"] == s2["name"]


# ===========================================================================
# 13. Syntax Errors
# ===========================================================================
class TestSyntaxErrors:
    def test_missing_semicolon(self):
        errors = parse_fail(wrap("int x = 5"))
        assert len(errors) > 0

    def test_missing_closing_brace(self):
        errors = parse_fail("int main() { return 0;")
        assert len(errors) > 0

    def test_missing_condition_in_if(self):
        errors = parse_fail(wrap("if () { }"))
        assert len(errors) > 0

    def test_invalid_type(self):
        # "string" is not a valid type — should fail to parse as declaration
        errors = parse_fail(wrap("string x;"))
        assert len(errors) > 0

    def test_assignment_to_literal(self):
        # "5 = x" is syntactically invalid
        errors = parse_fail(wrap("5 = x;"))
        assert len(errors) > 0

    def test_empty_source(self):
        result = parse("")
        # Empty source has no functions — should not succeed
        assert result["ast"] is None or result["success"] is False

    def test_parse_result_structure(self):
        result = parse(wrap("int x = 5;"))
        assert "ast" in result
        assert "errors" in result
        assert "success" in result


# ===========================================================================
# 14. AST Structure Validation
# ===========================================================================
class TestASTStructure:
    def test_program_node_structure(self):
        ast = parse_ok("int main() { return 0; }")
        assert ast["node"] == "Program"
        assert "functions" in ast
        assert isinstance(ast["functions"], list)

    def test_function_def_fields(self):
        ast = parse_ok("int foo(int x) { return x; }")
        func = first_func(ast)
        assert "node" in func
        assert "name" in func
        assert "return_type" in func
        assert "params" in func
        assert "body" in func
        assert "line" in func

    def test_block_node_fields(self):
        ast = parse_ok("int main() { int x; }")
        body = first_func(ast)["body"]
        assert "node" in body
        assert "statements" in body
        assert isinstance(body["statements"], list)

    def test_line_numbers_in_ast(self):
        # All nodes must have a "line" field for semantic analysis
        ast = parse_ok("int main() {\nint x = 5;\n}")
        stmt = first_stmt(ast)
        assert "line" in stmt
        assert stmt["line"] >= 1

    def test_complete_program_ast(self):
        src = """
        int add(int a, int b) {
            int result = a + b;
            return result;
        }

        int main() {
            int x = add(2, 3);
            return x;
        }
        """
        ast = parse_ok(src)
        assert len(ast["functions"]) == 2
        add_func = ast["functions"][0]
        main_func = ast["functions"][1]
        assert add_func["name"] == "add"
        assert main_func["name"] == "main"
        assert len(add_func["params"]) == 2
