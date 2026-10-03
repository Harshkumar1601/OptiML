"""
tests/test_lexer.py — Unit tests for compiler/lexer.py

Test categories:
  1. Keywords — all 7 keywords tokenized correctly
  2. Identifiers — valid names, keyword disambiguation
  3. Literals — integers, floats, negative numbers (via MINUS token)
  4. Operators — all arithmetic, relational, logical, assignment operators
  5. Delimiters — all 6 delimiters
  6. Comments — single-line (//) and block (/* */) are silently discarded
  7. Whitespace & Newlines — ignored, but line numbers track correctly
  8. Error cases — illegal characters reported with correct line numbers
  9. Real programs — full tokenization of realistic code snippets
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from compiler.lexer import tokenize

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def types(source: str):
    """Return just the token type list for a source string."""
    result = tokenize(source)
    return [t["type"] for t in result["tokens"]]


def values(source: str):
    """Return just the token value list for a source string."""
    result = tokenize(source)
    return [t["value"] for t in result["tokens"]]


def lines(source: str):
    """Return just the token line list for a source string."""
    result = tokenize(source)
    return [t["line"] for t in result["tokens"]]


# ===========================================================================
# 1. Keywords
# ===========================================================================
class TestKeywords:
    def test_all_keywords_recognized(self):
        src = "int float if else while for return"
        assert types(src) == ["INT", "FLOAT", "IF", "ELSE", "WHILE", "FOR", "RETURN"]

    def test_keyword_values_are_strings(self):
        src = "int float"
        vals = values(src)
        assert vals == ["int", "float"]

    def test_keyword_case_sensitive(self):
        # Keywords are lowercase only; uppercase variants are identifiers
        result = tokenize("Int FLOAT While")
        assert types("Int FLOAT While") == ["IDENTIFIER", "IDENTIFIER", "IDENTIFIER"]


# ===========================================================================
# 2. Identifiers
# ===========================================================================
class TestIdentifiers:
    def test_simple_identifier(self):
        assert types("myVar") == ["IDENTIFIER"]
        assert values("myVar") == ["myVar"]

    def test_identifier_with_underscore(self):
        assert types("_hidden") == ["IDENTIFIER"]
        assert types("my_var_2") == ["IDENTIFIER"]

    def test_identifier_starts_with_underscore(self):
        assert types("_x") == ["IDENTIFIER"]

    def test_identifier_not_keyword(self):
        # "integer" contains "int" but is not the keyword
        assert types("integer") == ["IDENTIFIER"]
        assert values("integer") == ["integer"]

    def test_identifier_alpha_numeric(self):
        assert types("x1y2z3") == ["IDENTIFIER"]

    def test_multiple_identifiers(self):
        assert types("a b c") == ["IDENTIFIER", "IDENTIFIER", "IDENTIFIER"]

    def test_identifier_cannot_start_with_digit(self):
        # "1abc" → INTEGER_LITERAL(1) + IDENTIFIER(abc)
        assert types("1abc") == ["INTEGER_LITERAL", "IDENTIFIER"]


# ===========================================================================
# 3. Literals
# ===========================================================================
class TestLiterals:
    def test_integer_literal(self):
        result = tokenize("42")
        assert result["tokens"][0]["type"] == "INTEGER_LITERAL"
        assert result["tokens"][0]["value"] == 42
        assert isinstance(result["tokens"][0]["value"], int)

    def test_float_literal(self):
        result = tokenize("3.14")
        assert result["tokens"][0]["type"] == "FLOAT_LITERAL"
        assert abs(result["tokens"][0]["value"] - 3.14) < 1e-9
        assert isinstance(result["tokens"][0]["value"], float)

    def test_zero(self):
        assert types("0") == ["INTEGER_LITERAL"]
        assert values("0") == [0]

    def test_float_zero(self):
        assert types("0.0") == ["FLOAT_LITERAL"]

    def test_float_before_integer_match(self):
        # "3.14" must be FLOAT not INTEGER + DOT + INTEGER
        assert types("3.14") == ["FLOAT_LITERAL"]

    def test_large_integer(self):
        assert types("999999") == ["INTEGER_LITERAL"]
        assert values("999999") == [999999]

    def test_negative_number_is_two_tokens(self):
        # "-5" is a MINUS + INTEGER_LITERAL at the lexer level
        # (unary minus is a parser concept)
        assert types("-5") == ["MINUS", "INTEGER_LITERAL"]

    def test_multiple_literals(self):
        assert types("1 2.5 3") == ["INTEGER_LITERAL", "FLOAT_LITERAL", "INTEGER_LITERAL"]


# ===========================================================================
# 4. Operators
# ===========================================================================
class TestOperators:
    def test_arithmetic_operators(self):
        assert types("+ - * /") == ["PLUS", "MINUS", "TIMES", "DIVIDE"]

    def test_relational_operators(self):
        assert types("< > <= >= == !=") == ["LT", "GT", "LE", "GE", "EQ", "NEQ"]

    def test_logical_operators(self):
        assert types("&& ||") == ["AND", "OR"]

    def test_assignment_operator(self):
        assert types("=") == ["ASSIGN"]

    def test_le_not_lt_assign(self):
        # "<=" must be LE, not LT + ASSIGN
        assert types("<=") == ["LE"]

    def test_ge_not_gt_assign(self):
        assert types(">=") == ["GE"]

    def test_eq_not_two_assigns(self):
        assert types("==") == ["EQ"]

    def test_neq_not_not_assign(self):
        assert types("!=") == ["NEQ"]

    def test_mixed_expr_tokens(self):
        assert types("a + b * c") == [
            "IDENTIFIER", "PLUS", "IDENTIFIER", "TIMES", "IDENTIFIER"
        ]

    def test_assign_vs_eq(self):
        assert types("x = 5 == 5") == [
            "IDENTIFIER", "ASSIGN", "INTEGER_LITERAL", "EQ", "INTEGER_LITERAL"
        ]


# ===========================================================================
# 5. Delimiters
# ===========================================================================
class TestDelimiters:
    def test_all_delimiters(self):
        assert types("( ) { } ; ,") == [
            "LPAREN", "RPAREN", "LBRACE", "RBRACE", "SEMICOLON", "COMMA"
        ]

    def test_function_signature_tokens(self):
        src = "int foo ( int x , int y )"
        expected = [
            "INT", "IDENTIFIER",
            "LPAREN", "INT", "IDENTIFIER", "COMMA", "INT", "IDENTIFIER", "RPAREN"
        ]
        assert types(src) == expected


# ===========================================================================
# 6. Comments
# ===========================================================================
class TestComments:
    def test_single_line_comment_discarded(self):
        src = "// this is a comment\nint x;"
        result = tokenize(src)
        assert types(src) == ["INT", "IDENTIFIER", "SEMICOLON"]
        assert result["success"] is True

    def test_single_line_comment_mid_line(self):
        src = "int x; // declare x\nint y;"
        result = tokenize(src)
        assert types(src) == ["INT", "IDENTIFIER", "SEMICOLON", "INT", "IDENTIFIER", "SEMICOLON"]

    def test_block_comment_discarded(self):
        src = "/* block comment */ int x;"
        assert types(src) == ["INT", "IDENTIFIER", "SEMICOLON"]

    def test_multiline_block_comment_discarded(self):
        src = "/* line 1\n   line 2\n   line 3 */\nint x;"
        result = tokenize(src)
        assert types(src) == ["INT", "IDENTIFIER", "SEMICOLON"]
        assert result["success"] is True

    def test_block_comment_updates_line_count(self):
        src = "/* line 1\n   line 2 */\nint x;"
        result = tokenize(src)
        # 'int' token should appear on line 3 (after 2 comment lines)
        int_tok = [t for t in result["tokens"] if t["type"] == "INT"][0]
        assert int_tok["line"] == 3

    def test_comment_only_source_is_empty(self):
        result = tokenize("// nothing here")
        assert result["tokens"] == []
        assert result["success"] is True


# ===========================================================================
# 7. Whitespace & Line Numbers
# ===========================================================================
class TestWhitespaceAndLines:
    def test_whitespace_ignored(self):
        assert types("int   x") == ["INT", "IDENTIFIER"]
        assert types("int\tx") == ["INT", "IDENTIFIER"]

    def test_line_numbers_tracked(self):
        src = "int x;\nfloat y;"
        result = tokenize(src)
        toks = result["tokens"]
        # Tokens on line 1: INT, IDENTIFIER, SEMICOLON
        assert toks[0]["line"] == 1
        assert toks[1]["line"] == 1
        assert toks[2]["line"] == 1
        # Tokens on line 2: FLOAT, IDENTIFIER, SEMICOLON
        assert toks[3]["line"] == 2
        assert toks[4]["line"] == 2
        assert toks[5]["line"] == 2

    def test_blank_lines_counted(self):
        src = "int x;\n\n\nfloat y;"
        result = tokenize(src)
        float_tok = [t for t in result["tokens"] if t["type"] == "FLOAT"][0]
        assert float_tok["line"] == 4


# ===========================================================================
# 8. Error Cases
# ===========================================================================
class TestErrorCases:
    def test_illegal_character_at_symbol(self):
        result = tokenize("int @x;")
        assert result["success"] is False
        assert len(result["errors"]) == 1
        assert "@" in result["errors"][0]["message"]

    def test_illegal_character_hash(self):
        result = tokenize("#include")
        assert result["success"] is False
        assert "#" in result["errors"][0]["message"]

    def test_illegal_character_dollar(self):
        result = tokenize("int $x;")
        assert result["success"] is False

    def test_multiple_illegal_chars_all_reported(self):
        result = tokenize("@ # $")
        # All 3 illegal chars must be reported
        assert len(result["errors"]) == 3

    def test_illegal_char_line_number_reported(self):
        result = tokenize("int x;\n@ illegal")
        assert result["errors"][0]["line"] == 2

    def test_valid_tokens_still_emitted_after_illegal(self):
        # Lexer continues after illegal char
        result = tokenize("int @ x;")
        type_list = [t["type"] for t in result["tokens"]]
        assert "INT" in type_list
        assert "IDENTIFIER" in type_list

    def test_column_number_reported(self):
        result = tokenize("int @x;")
        assert result["errors"][0]["column"] == 5  # '@' is at column 5


# ===========================================================================
# 9. Real-program snippets
# ===========================================================================
class TestRealPrograms:
    def test_main_function_signature(self):
        src = "int main() {"
        assert types(src) == [
            "INT", "IDENTIFIER", "LPAREN", "RPAREN", "LBRACE"
        ]

    def test_variable_declaration_with_init(self):
        src = "int x = 2 + 3;"
        assert types(src) == [
            "INT", "IDENTIFIER", "ASSIGN",
            "INTEGER_LITERAL", "PLUS", "INTEGER_LITERAL", "SEMICOLON"
        ]

    def test_for_loop_tokens(self):
        src = "for (int i = 0; i < 10; i = i + 1)"
        expected = [
            "FOR", "LPAREN",
            "INT", "IDENTIFIER", "ASSIGN", "INTEGER_LITERAL", "SEMICOLON",
            "IDENTIFIER", "LT", "INTEGER_LITERAL", "SEMICOLON",
            "IDENTIFIER", "ASSIGN", "IDENTIFIER", "PLUS", "INTEGER_LITERAL",
            "RPAREN",
        ]
        assert types(src) == expected

    def test_if_else_tokens(self):
        src = "if (x > 0) { return x; } else { return 0; }"
        result = tokenize(src)
        assert result["success"] is True
        assert "IF" in types(src)
        assert "ELSE" in types(src)

    def test_full_program_no_errors(self):
        src = """
        // Compute the sum of n
        int sum(int n) {
            int result = 0;
            int i = 0;
            while (i < n) {
                result = result + i;
                i = i + 1;
            }
            return result;
        }

        int main() {
            int s = sum(10);
            return 0;
        }
        """
        result = tokenize(src)
        assert result["success"] is True
        assert len(result["errors"]) == 0
        assert len(result["tokens"]) > 0

    def test_tokenize_result_structure(self):
        result = tokenize("int x;")
        assert "tokens" in result
        assert "errors" in result
        assert "success" in result
        for tok in result["tokens"]:
            assert "type" in tok
            assert "value" in tok
            assert "line" in tok
            assert "column" in tok
