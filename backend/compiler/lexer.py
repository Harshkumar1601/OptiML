"""
compiler/lexer.py — PLY-based Lexer for the restricted C-like language.

Tokenizes source code into a flat list of typed tokens. Handles:
  - Keywords: int, float, if, else, while, for, return
  - Identifiers
  - Integer and float literals
  - All arithmetic, relational, logical, and assignment operators
  - Delimiters: ( ) { } ; ,
  - Single-line comments (//) and block comments (/* */)
  - Illegal character detection with line-number reporting

Design notes:
  - This module is completely independent of Flask, ML, and the parser.
  - Call `tokenize(source)` to get a list of Token dicts (JSON-safe).
  - Call `build_lexer()` to get a raw PLY lexer object (used by the parser).
  - PLY generates a `lexer.out` debug file in the working directory; this
    is normal and can be ignored.
"""

import ply.lex as lex
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# 1. Reserved keywords
#    Maps keyword string → token type name.
#    PLY convention: token types must be uppercase.
# ---------------------------------------------------------------------------
RESERVED: Dict[str, str] = {
    "int":    "INT",
    "float":  "FLOAT",
    "if":     "IF",
    "else":   "ELSE",
    "while":  "WHILE",
    "for":    "FOR",
    "return": "RETURN",
}

# ---------------------------------------------------------------------------
# 2. Token list
#    Every token type used anywhere in the grammar must appear here.
#    PLY requires this variable to be named exactly `tokens`.
# ---------------------------------------------------------------------------
tokens: tuple = (
    # Literals
    "INTEGER_LITERAL",
    "FLOAT_LITERAL",
    # Identifier (also catches keywords — resolved below)
    "IDENTIFIER",
    # Arithmetic operators
    "PLUS",
    "MINUS",
    "TIMES",
    "DIVIDE",
    # Relational operators
    "LT",      # <
    "GT",      # >
    "LE",      # <=
    "GE",      # >=
    "EQ",      # ==
    "NEQ",     # !=
    # Logical operators
    "AND",     # &&
    "OR",      # ||
    # Assignment
    "ASSIGN",  # =
    # Delimiters
    "LPAREN",  "RPAREN",   # ( )
    "LBRACE",  "RBRACE",   # { }
    "SEMICOLON",
    "COMMA",
) + tuple(RESERVED.values())  # INT, FLOAT, IF, ELSE, WHILE, FOR, RETURN

# ---------------------------------------------------------------------------
# 3. Simple single-character token rules
#    PLY uses the longest match: longer regex strings take priority.
# ---------------------------------------------------------------------------
t_PLUS       = r"\+"
t_MINUS      = r"-"
t_TIMES      = r"\*"
t_DIVIDE     = r"/"
t_LPAREN     = r"\("
t_RPAREN     = r"\)"
t_LBRACE     = r"\{"
t_RBRACE     = r"\}"
t_SEMICOLON  = r";"
t_COMMA      = r","
t_ASSIGN     = r"="        # must come AFTER == rule (longer match wins)

# ---------------------------------------------------------------------------
# 4. Multi-character operator rules (functions, so they run before string rules)
# ---------------------------------------------------------------------------
def t_LE(t):
    r"""<="""
    return t

def t_GE(t):
    r""">="""
    return t

def t_EQ(t):
    r"""==""" 
    return t

def t_NEQ(t):
    r"""!=""" 
    return t

def t_LT(t):
    r"""<"""
    return t

def t_GT(t):
    r""">"""
    return t

def t_AND(t):
    r"""&&"""
    return t

def t_OR(t):
    r"""\|\|"""
    return t

# ---------------------------------------------------------------------------
# 5. Comment rules (discarded — no token returned)
# ---------------------------------------------------------------------------
def t_BLOCK_COMMENT(t):
    r"""/\*(.|\n)*?\*/"""
    # Count newlines inside block comments to keep line numbers accurate
    t.lexer.lineno += t.value.count("\n")
    # Returning nothing discards the token

def t_LINE_COMMENT(t):
    r"""//[^\n]*"""
    # Single-line comment — consumed silently, no token returned

# ---------------------------------------------------------------------------
# 6. Float literal  (must be defined before INTEGER_LITERAL)
#    Matches digits . digits, e.g. 3.14, 0.5
# ---------------------------------------------------------------------------
def t_FLOAT_LITERAL(t):
    r"""\d+\.\d+"""
    t.value = float(t.value)
    return t

# ---------------------------------------------------------------------------
# 7. Integer literal
# ---------------------------------------------------------------------------
def t_INTEGER_LITERAL(t):
    r"""\d+"""
    t.value = int(t.value)
    return t

# ---------------------------------------------------------------------------
# 8. Identifier / keyword disambiguation
#    PLY matches identifiers first, then we check the reserved dict.
# ---------------------------------------------------------------------------
def t_IDENTIFIER(t):
    r"""[a-zA-Z_][a-zA-Z0-9_]*"""
    t.type = RESERVED.get(t.value, "IDENTIFIER")
    return t

# ---------------------------------------------------------------------------
# 9. Newlines — update line counter, discard token
# ---------------------------------------------------------------------------
def t_newline(t):
    r"""\n+"""
    t.lexer.lineno += len(t.value)

# ---------------------------------------------------------------------------
# 10. Whitespace — ignored
# ---------------------------------------------------------------------------
t_ignore = " \t\r"

# ---------------------------------------------------------------------------
# 11. Illegal character handler
#     Records the error but continues tokenizing so all errors are reported.
# ---------------------------------------------------------------------------
def t_error(t):
    t.lexer.errors.append({
        "message": f"Illegal character '{t.value[0]}'",
        "line":    t.lexer.lineno,
        "column":  _find_column(t.lexer.source, t),
    })
    t.lexer.skip(1)

# ---------------------------------------------------------------------------
# Helper: compute 1-based column number for error reporting
# ---------------------------------------------------------------------------
def _find_column(source: str, token) -> int:
    """Return the 1-based column of a token within its source line."""
    line_start = source.rfind("\n", 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_lexer():
    """
    Build and return a fresh PLY lexer instance.
    Called by the parser (parser.py) to share the same token definitions.
    The lexer instance is extended with `.errors` and `.source` attributes.
    """
    lexer = lex.lex()
    lexer.errors = []
    lexer.source = ""
    return lexer


def tokenize(source: str) -> Dict[str, Any]:
    """
    Tokenize `source` and return a result dict:

      {
        "tokens":  [ {"type": str, "value": any, "line": int, "column": int}, ... ],
        "errors":  [ {"message": str, "line": int, "column": int}, ... ],
        "success": bool,   # True if no lexer errors
      }

    Token values:
      - INTEGER_LITERAL: Python int
      - FLOAT_LITERAL:   Python float
      - All others:      the matched string (e.g. "int", "+", "myVar")
    """
    lexer = build_lexer()
    lexer.source = source
    lexer.input(source)

    token_list: List[Dict[str, Any]] = []

    for tok in lexer:
        token_list.append({
            "type":   tok.type,
            "value":  tok.value,
            "line":   tok.lineno,
            "column": _find_column(source, tok),
        })

    return {
        "tokens":  token_list,
        "errors":  lexer.errors,
        "success": len(lexer.errors) == 0,
    }
