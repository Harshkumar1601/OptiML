"""
compiler/parser.py — PLY-based Parser for the restricted C-like language.

Consumes the token stream from the lexer and builds an AST using the
grammar defined in docs/grammar.md. Returns a structured result dict
that is JSON-serializable for the API.

Key design decisions:
  - Operator precedence is declared via PLY's `precedence` tuple rather
    than encoding it into grammar rules, which reduces shift/reduce conflicts.
  - Every p_rule function corresponds 1:1 with a BNF production.
  - Syntax errors collect into a list (non-fatal) and set `success = False`.
  - The parser is built once at module load (parse_program caches the yacc
    object on first call) to avoid regenerating tables on every request.

Public API:
  parse(source: str) -> dict
"""

import ply.yacc as yacc
from typing import Any, Dict, List, Optional

# Import the shared lexer (tokens list + lexer builder)
from compiler.lexer import tokens, build_lexer  # noqa: F401 – `tokens` used by PLY
from compiler import ast_nodes as N

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_parser = None          # Cached PLY parser object (built once)
_parse_errors: List[Dict[str, Any]] = []   # Accumulates syntax errors


# ---------------------------------------------------------------------------
# Operator Precedence
# (lowest to highest — each tuple is one precedence level)
# ---------------------------------------------------------------------------
precedence = (
    ("left",  "OR"),
    ("left",  "AND"),
    ("left",  "EQ", "NEQ"),
    ("left",  "LT", "GT", "LE", "GE"),
    ("left",  "PLUS", "MINUS"),
    ("left",  "TIMES", "DIVIDE"),
    ("right", "UMINUS"),        # Unary minus (virtual token, highest precedence)
)


# ===========================================================================
# Grammar Rules
# Each function's docstring IS the grammar rule (PLY convention).
# Multiple alternatives for the same non-terminal use multiple functions
# with the same name prefix, separated by underscores and a counter.
# ===========================================================================

# ---------------------------------------------------------------------------
# program
# ---------------------------------------------------------------------------
def p_program(p):
    """program : function_list"""
    p[0] = N.ProgramNode(functions=p[1])


# ---------------------------------------------------------------------------
# function_list
# ---------------------------------------------------------------------------
def p_function_list_single(p):
    """function_list : function_def"""
    p[0] = [p[1]]


def p_function_list_multi(p):
    """function_list : function_list function_def"""
    p[0] = p[1] + [p[2]]


# ---------------------------------------------------------------------------
# function_def
# ---------------------------------------------------------------------------
def p_function_def_with_params(p):
    """function_def : type IDENTIFIER LPAREN param_list RPAREN block"""
    p[0] = N.FunctionDefNode(
        return_type=p[1], name=p[2], params=p[4], body=p[6],
        line=p.lineno(2),
    )


def p_function_def_no_params(p):
    """function_def : type IDENTIFIER LPAREN RPAREN block"""
    p[0] = N.FunctionDefNode(
        return_type=p[1], name=p[2], params=[], body=p[5],
        line=p.lineno(2),
    )


# ---------------------------------------------------------------------------
# param_list
# ---------------------------------------------------------------------------
def p_param_list_single(p):
    """param_list : param"""
    p[0] = [p[1]]


def p_param_list_multi(p):
    """param_list : param_list COMMA param"""
    p[0] = p[1] + [p[3]]


# ---------------------------------------------------------------------------
# param
# ---------------------------------------------------------------------------
def p_param(p):
    """param : type IDENTIFIER"""
    p[0] = N.ParamNode(param_type=p[1], name=p[2], line=p.lineno(2))


# ---------------------------------------------------------------------------
# type
# ---------------------------------------------------------------------------
def p_type_int(p):
    """type : INT"""
    p[0] = "int"


def p_type_float(p):
    """type : FLOAT"""
    p[0] = "float"


# ---------------------------------------------------------------------------
# block
# ---------------------------------------------------------------------------
def p_block_with_stmts(p):
    """block : LBRACE stmt_list RBRACE"""
    p[0] = N.BlockNode(statements=p[2], line=p.lineno(1))


def p_block_empty(p):
    """block : LBRACE RBRACE"""
    p[0] = N.BlockNode(statements=[], line=p.lineno(1))


# ---------------------------------------------------------------------------
# stmt_list
# ---------------------------------------------------------------------------
def p_stmt_list_single(p):
    """stmt_list : stmt"""
    p[0] = [p[1]]


def p_stmt_list_multi(p):
    """stmt_list : stmt_list stmt"""
    p[0] = p[1] + [p[2]]


# ---------------------------------------------------------------------------
# stmt — six statement forms
# ---------------------------------------------------------------------------
def p_stmt_declaration(p):
    """stmt : declaration SEMICOLON"""
    p[0] = p[1]


def p_stmt_assignment(p):
    """stmt : assignment SEMICOLON"""
    p[0] = p[1]


def p_stmt_if(p):
    """stmt : if_stmt"""
    p[0] = p[1]


def p_stmt_while(p):
    """stmt : while_stmt"""
    p[0] = p[1]


def p_stmt_for(p):
    """stmt : for_stmt"""
    p[0] = p[1]


def p_stmt_return(p):
    """stmt : return_stmt SEMICOLON"""
    p[0] = p[1]


def p_stmt_func_call(p):
    """stmt : func_call SEMICOLON"""
    p[0] = N.FuncCallStmtNode(call_expr=p[1], line=p[1].line)


# ---------------------------------------------------------------------------
# declaration
# ---------------------------------------------------------------------------
def p_declaration_no_init(p):
    """declaration : type IDENTIFIER"""
    p[0] = N.DeclarationNode(
        var_type=p[1], name=p[2], init_expr=None, line=p.lineno(2)
    )


def p_declaration_with_init(p):
    """declaration : type IDENTIFIER ASSIGN expr"""
    p[0] = N.DeclarationNode(
        var_type=p[1], name=p[2], init_expr=p[4], line=p.lineno(2)
    )


# ---------------------------------------------------------------------------
# assignment
# ---------------------------------------------------------------------------
def p_assignment(p):
    """assignment : IDENTIFIER ASSIGN expr"""
    p[0] = N.AssignmentNode(name=p[1], expr=p[3], line=p.lineno(1))


# ---------------------------------------------------------------------------
# if_stmt
# ---------------------------------------------------------------------------
def p_if_no_else(p):
    """if_stmt : IF LPAREN condition RPAREN block"""
    p[0] = N.IfNode(
        condition=p[3], then_block=p[5], else_block=None, line=p.lineno(1)
    )


def p_if_with_else(p):
    """if_stmt : IF LPAREN condition RPAREN block ELSE block"""
    p[0] = N.IfNode(
        condition=p[3], then_block=p[5], else_block=p[7], line=p.lineno(1)
    )


# ---------------------------------------------------------------------------
# while_stmt
# ---------------------------------------------------------------------------
def p_while_stmt(p):
    """while_stmt : WHILE LPAREN condition RPAREN block"""
    p[0] = N.WhileNode(condition=p[3], body=p[5], line=p.lineno(1))


# ---------------------------------------------------------------------------
# for_stmt
# ---------------------------------------------------------------------------
def p_for_stmt(p):
    """for_stmt : FOR LPAREN for_init SEMICOLON condition SEMICOLON for_update RPAREN block"""
    p[0] = N.ForNode(
        init=p[3], condition=p[5], update=p[7], body=p[9], line=p.lineno(1)
    )


# ---------------------------------------------------------------------------
# for_init — declaration or assignment (no trailing semicolon here)
# ---------------------------------------------------------------------------
def p_for_init_declaration(p):
    """for_init : declaration"""
    p[0] = p[1]


def p_for_init_assignment(p):
    """for_init : assignment"""
    p[0] = p[1]


# ---------------------------------------------------------------------------
# for_update — only assignment
# ---------------------------------------------------------------------------
def p_for_update(p):
    """for_update : assignment"""
    p[0] = p[1]


# ---------------------------------------------------------------------------
# return_stmt
# ---------------------------------------------------------------------------
def p_return_with_expr(p):
    """return_stmt : RETURN expr"""
    p[0] = N.ReturnNode(expr=p[2], line=p.lineno(1))


def p_return_empty(p):
    """return_stmt : RETURN"""
    p[0] = N.ReturnNode(expr=None, line=p.lineno(1))


# ---------------------------------------------------------------------------
# func_call
# ---------------------------------------------------------------------------
def p_func_call_with_args(p):
    """func_call : IDENTIFIER LPAREN arg_list RPAREN"""
    p[0] = N.FuncCallExprNode(name=p[1], args=p[3], line=p.lineno(1))


def p_func_call_no_args(p):
    """func_call : IDENTIFIER LPAREN RPAREN"""
    p[0] = N.FuncCallExprNode(name=p[1], args=[], line=p.lineno(1))


# ---------------------------------------------------------------------------
# arg_list
# ---------------------------------------------------------------------------
def p_arg_list_single(p):
    """arg_list : expr"""
    p[0] = [p[1]]


def p_arg_list_multi(p):
    """arg_list : arg_list COMMA expr"""
    p[0] = p[1] + [p[3]]


# ---------------------------------------------------------------------------
# condition — strict: always requires a relational or logical operator
# ---------------------------------------------------------------------------
def p_condition_relop(p):
    """condition : expr rel_op expr"""
    p[0] = N.ConditionNode(op=p[2], left=p[1], right=p[3], line=p.lineno(2))


def p_condition_and(p):
    """condition : condition AND condition"""
    p[0] = N.ConditionNode(op="&&", left=p[1], right=p[3], line=p.lineno(2))


def p_condition_or(p):
    """condition : condition OR condition"""
    p[0] = N.ConditionNode(op="||", left=p[1], right=p[3], line=p.lineno(2))


def p_condition_paren(p):
    """condition : LPAREN condition RPAREN"""
    p[0] = p[2]


# ---------------------------------------------------------------------------
# rel_op — returns the operator string
# ---------------------------------------------------------------------------
def p_rel_op(p):
    """rel_op : LT
              | GT
              | LE
              | GE
              | EQ
              | NEQ"""
    p[0] = p[1]


# ---------------------------------------------------------------------------
# expr — arithmetic expression
# ---------------------------------------------------------------------------
def p_expr_binop_plus(p):
    """expr : expr PLUS term"""
    p[0] = N.BinOpNode(op="+", left=p[1], right=p[3], line=p.lineno(2))


def p_expr_binop_minus(p):
    """expr : expr MINUS term"""
    p[0] = N.BinOpNode(op="-", left=p[1], right=p[3], line=p.lineno(2))


def p_expr_term(p):
    """expr : term"""
    p[0] = p[1]


# ---------------------------------------------------------------------------
# term — multiplication / division
# ---------------------------------------------------------------------------
def p_term_binop_times(p):
    """term : term TIMES factor"""
    p[0] = N.BinOpNode(op="*", left=p[1], right=p[3], line=p.lineno(2))


def p_term_binop_divide(p):
    """term : term DIVIDE factor"""
    p[0] = N.BinOpNode(op="/", left=p[1], right=p[3], line=p.lineno(2))


def p_term_factor(p):
    """term : factor"""
    p[0] = p[1]


# ---------------------------------------------------------------------------
# factor — leaves of the expression tree
# ---------------------------------------------------------------------------
def p_factor_paren(p):
    """factor : LPAREN expr RPAREN"""
    p[0] = p[2]


def p_factor_uminus(p):
    """factor : MINUS factor %prec UMINUS"""
    p[0] = N.UnaryOpNode(op="-", operand=p[2], line=p.lineno(1))


def p_factor_identifier(p):
    """factor : IDENTIFIER"""
    p[0] = N.IdentifierNode(name=p[1], line=p.lineno(1))


def p_factor_int_literal(p):
    """factor : INTEGER_LITERAL"""
    p[0] = N.IntLiteralNode(value=p[1], line=p.lineno(1))


def p_factor_float_literal(p):
    """factor : FLOAT_LITERAL"""
    p[0] = N.FloatLiteralNode(value=p[1], line=p.lineno(1))


def p_factor_func_call(p):
    """factor : func_call"""
    p[0] = p[1]


# ---------------------------------------------------------------------------
# Syntax error handler
# ---------------------------------------------------------------------------
def p_error(p):
    """Called by PLY on a syntax error. Appends to module-level error list."""
    if p is None:
        _parse_errors.append({
            "message": "Unexpected end of input",
            "line":    None,
            "token":   None,
        })
    else:
        _parse_errors.append({
            "message": f"Syntax error at token '{p.value}' (type: {p.type})",
            "line":    p.lineno,
            "token":   str(p.value),
        })
        # Resume parsing: PLY 3.11 passes a raw LexToken to p_error (no .parser attr),
        # so we call errok() on the cached parser object directly.
        parser_obj = _get_parser()
        if parser_obj is not None:
            parser_obj.errok()


# ---------------------------------------------------------------------------
# Internal: build parser tables once
# ---------------------------------------------------------------------------
def _get_parser():
    """Build and cache the PLY parser on first call."""
    global _parser
    if _parser is None:
        _parser = yacc.yacc(
            debug=False,
            write_tables=False,
            outputdir=".",
            errorlog=yacc.NullLogger(),   # suppress PLY's own stderr noise
        )
    return _parser


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse(source: str) -> Dict[str, Any]:
    """
    Parse `source` and return a result dict:

      {
        "ast":     dict | None,    # AST as a nested dict (JSON-safe), or None on error
        "errors":  list[dict],     # syntax error list (may be non-empty even if ast is not None)
        "success": bool,
      }

    The parser uses error recovery, so it continues after a syntax error
    where possible. `success` is False if any syntax error was encountered.
    """
    global _parse_errors
    _parse_errors = []     # reset error list for this call

    lexer = build_lexer()
    lexer.source = source
    lexer.input(source)

    parser = _get_parser()
    ast = parser.parse(source, lexer=lexer, tracking=True)

    # Combine lexer errors + parser errors
    all_errors = lexer.errors + _parse_errors

    ast_dict = ast.to_dict() if ast is not None else None

    return {
        "ast":      ast_dict,
        "ast_node": ast,
        "errors":   all_errors,
        "success":  len(all_errors) == 0 and ast is not None,
    }
