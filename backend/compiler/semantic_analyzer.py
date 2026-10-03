"""
compiler/semantic_analyzer.py — Semantic analysis for the restricted C-like language.

Traverses the AST produced by parser.py and performs all semantic checks that
cannot be done at parse time. Populates the symbol table along the way.

Checks implemented:
  1.  UNDECLARED_VARIABLE    — use of a variable before declaration
  2.  DUPLICATE_DECLARATION  — re-declaring a variable in the same scope
  3.  TYPE_MISMATCH          — assigning a float expression to an int variable
  4.  UNDECLARED_FUNCTION    — calling a function not defined in the program
  5.  ARGUMENT_COUNT         — wrong number of arguments to a function call
  6.  RETURN_TYPE_MISMATCH   — returning float from an int function (or vice versa)
  7.  MISSING_RETURN         — int/float function has no return statement
  8.  CONDITION_OPERAND      — undeclared variable used in a condition
  9.  INVALID_OPERAND_TYPE   — (reserved) non-numeric operand in arithmetic

Type system (simplified):
  - Only two types: "int" and "float"
  - "float" is the wider type: int op float → float
  - Assigning float → int is a type mismatch (no implicit narrowing)
  - Assigning int → float is allowed (widening)

Public API:
  analyze(ast_node: ASTNode) -> dict
    Returns:
      {
        "symbol_table": list[dict],    # all declared symbols (JSON-safe)
        "errors":       list[dict],    # semantic error list
        "success":      bool,
      }
"""

from typing import Any, Dict, List, Optional

from compiler import ast_nodes as N
from compiler.symbol_table import SymbolTable, DuplicateDeclarationError


# ---------------------------------------------------------------------------
# Semantic error codes (human-readable, used by the frontend)
# ---------------------------------------------------------------------------
ERR_UNDECLARED_VAR      = "UNDECLARED_VARIABLE"
ERR_DUPLICATE_DECL      = "DUPLICATE_DECLARATION"
ERR_TYPE_MISMATCH       = "TYPE_MISMATCH"
ERR_UNDECLARED_FUNC     = "UNDECLARED_FUNCTION"
ERR_ARGUMENT_COUNT      = "ARGUMENT_COUNT_MISMATCH"
ERR_RETURN_TYPE         = "RETURN_TYPE_MISMATCH"
ERR_MISSING_RETURN      = "MISSING_RETURN"
ERR_CONDITION_OPERAND   = "UNDECLARED_VARIABLE_IN_CONDITION"


# ---------------------------------------------------------------------------
# SemanticAnalyzer
# ---------------------------------------------------------------------------
class SemanticAnalyzer:
    """
    Visitor-style AST traversal.

    Each visit_* method handles one AST node type. Methods return the
    inferred type string ("int" | "float" | None) for expression nodes,
    and None for statement nodes.

    Errors are appended to self._errors — the analyzer never raises an
    exception to the caller (the pipeline always gets a result dict).
    """

    def __init__(self) -> None:
        self._symtab = SymbolTable()
        self._errors: List[Dict[str, Any]] = []
        self._has_return: bool = False   # tracks return inside current function

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------
    def analyze(self, program: N.ProgramNode) -> Dict[str, Any]:
        """
        Run full semantic analysis on a ProgramNode.
        Returns the standardized result dict.
        """
        self._register_functions(program)
        for func in program.functions:
            self._visit_function_def(func)

        return {
            "symbol_table": self._symtab.to_list(),
            "errors":       self._errors,
            "success":      len(self._errors) == 0,
        }

    # -----------------------------------------------------------------------
    # Pass 1: Register all function signatures into the global scope
    # This allows mutual/forward calls between functions.
    # -----------------------------------------------------------------------
    def _register_functions(self, program: N.ProgramNode) -> None:
        """
        Pre-populate the global scope with all function definitions before
        analyzing any function bodies. This enables forward references.
        """
        for func in program.functions:
            entry = {
                "name":        func.name,
                "kind":        "function",
                "type":        func.return_type,
                "return_type": func.return_type,
                "param_types": [p.param_type for p in func.params],
                "param_names": [p.name for p in func.params],
                "line":        func.line,
            }
            try:
                self._symtab.declare(entry)
            except DuplicateDeclarationError as e:
                self._error(ERR_DUPLICATE_DECL, func.name, func.line, str(e))

    # -----------------------------------------------------------------------
    # Function definition
    # -----------------------------------------------------------------------
    def _visit_function_def(self, node: N.FunctionDefNode) -> None:
        func_entry = self._symtab.lookup(node.name)
        self._symtab.set_current_function(func_entry)
        self._has_return = False

        # Open function scope and declare parameters
        self._symtab.push_scope()
        for param in node.params:
            self._declare_variable(
                name=param.name,
                kind="parameter",
                var_type=param.param_type,
                line=param.line,
            )

        # Analyze body (pass the inner block's statements directly,
        # without pushing another scope, so params live in the function scope)
        for stmt in node.body.statements:
            self._visit_stmt(stmt)

        self._symtab.pop_scope()

        # Check for missing return in non-void functions
        if node.return_type in ("int", "float") and not self._has_return:
            self._error(
                ERR_MISSING_RETURN,
                node.name,
                node.line,
                f"Function '{node.name}' (returns {node.return_type}) "
                f"has no return statement",
            )

        self._symtab.set_current_function(None)

    # -----------------------------------------------------------------------
    # Statement dispatch
    # -----------------------------------------------------------------------
    def _visit_stmt(self, node: N.ASTNode) -> None:
        if isinstance(node, N.DeclarationNode):
            self._visit_declaration(node)
        elif isinstance(node, N.AssignmentNode):
            self._visit_assignment(node)
        elif isinstance(node, N.IfNode):
            self._visit_if(node)
        elif isinstance(node, N.WhileNode):
            self._visit_while(node)
        elif isinstance(node, N.ForNode):
            self._visit_for(node)
        elif isinstance(node, N.ReturnNode):
            self._visit_return(node)
        elif isinstance(node, N.FuncCallStmtNode):
            self._visit_func_call_expr(node.call_expr)
        elif isinstance(node, N.BlockNode):
            self._visit_block(node)

    # -----------------------------------------------------------------------
    # Block (opens a new scope)
    # -----------------------------------------------------------------------
    def _visit_block(self, node: N.BlockNode) -> None:
        self._symtab.push_scope()
        for stmt in node.statements:
            self._visit_stmt(stmt)
        self._symtab.pop_scope()

    # -----------------------------------------------------------------------
    # Declaration
    # -----------------------------------------------------------------------
    def _visit_declaration(self, node: N.DeclarationNode) -> None:
        # Evaluate initializer expression first (before declaring the variable,
        # so `int x = x;` correctly reports x as undeclared in the init)
        init_type = None
        if node.init_expr is not None:
            init_type = self._visit_expr(node.init_expr)

        # Type-check the initializer
        if init_type is not None:
            self._check_assignment_types(
                target_type=node.var_type,
                expr_type=init_type,
                name=node.name,
                line=node.line,
            )

        # Declare the variable in the current scope
        self._declare_variable(
            name=node.name,
            kind="variable",
            var_type=node.var_type,
            line=node.line,
        )

    # -----------------------------------------------------------------------
    # Assignment
    # -----------------------------------------------------------------------
    def _visit_assignment(self, node: N.AssignmentNode) -> None:
        # Look up the target variable
        symbol = self._symtab.lookup(node.name)
        if symbol is None:
            self._error(
                ERR_UNDECLARED_VAR, node.name, node.line,
                f"Assignment to undeclared variable '{node.name}'",
            )
            self._visit_expr(node.expr)   # still analyse rhs for further errors
            return

        # Evaluate RHS
        expr_type = self._visit_expr(node.expr)

        # Type-check assignment
        if expr_type is not None:
            self._check_assignment_types(
                target_type=symbol["type"],
                expr_type=expr_type,
                name=node.name,
                line=node.line,
            )

    # -----------------------------------------------------------------------
    # If / if-else
    # -----------------------------------------------------------------------
    def _visit_if(self, node: N.IfNode) -> None:
        self._visit_condition(node.condition)
        self._visit_block(node.then_block)
        if node.else_block is not None:
            self._visit_block(node.else_block)

    # -----------------------------------------------------------------------
    # While
    # -----------------------------------------------------------------------
    def _visit_while(self, node: N.WhileNode) -> None:
        self._visit_condition(node.condition)
        self._visit_block(node.body)

    # -----------------------------------------------------------------------
    # For
    # -----------------------------------------------------------------------
    def _visit_for(self, node: N.ForNode) -> None:
        # The for-loop creates its own scope so the init variable is scoped to it
        self._symtab.push_scope()

        if isinstance(node.init, N.DeclarationNode):
            self._visit_declaration(node.init)
        elif isinstance(node.init, N.AssignmentNode):
            self._visit_assignment(node.init)

        self._visit_condition(node.condition)
        self._visit_assignment(node.update)

        # Body is a block — open its own nested scope
        self._visit_block(node.body)

        self._symtab.pop_scope()

    # -----------------------------------------------------------------------
    # Return
    # -----------------------------------------------------------------------
    def _visit_return(self, node: N.ReturnNode) -> None:
        self._has_return = True
        func = self._symtab.current_function()

        if node.expr is None:
            # `return;` — only valid if function returns void (not in our language)
            # We allow bare return but flag it if the function expects a value
            if func is not None and func["return_type"] in ("int", "float"):
                self._error(
                    ERR_RETURN_TYPE,
                    func["name"],
                    node.line,
                    f"Function '{func['name']}' expects return type "
                    f"'{func['return_type']}' but has bare 'return'",
                )
            return

        expr_type = self._visit_expr(node.expr)

        if func is not None and expr_type is not None:
            expected = func["return_type"]
            # float returned from int function is a mismatch
            if expected == "int" and expr_type == "float":
                self._error(
                    ERR_RETURN_TYPE,
                    func["name"],
                    node.line,
                    f"Function '{func['name']}' returns 'int' "
                    f"but return expression has type 'float'",
                )
            # int returned from float function is allowed (widening)

    # -----------------------------------------------------------------------
    # Condition
    # -----------------------------------------------------------------------
    def _visit_condition(self, node: N.ConditionNode) -> None:
        """
        Conditions can be compound (&&, ||) or simple (relop).
        Both sides of a compound condition are themselves ConditionNodes.
        Both sides of a relop condition are expressions.
        """
        if node.op in ("&&", "||"):
            # Both children are ConditionNodes
            if isinstance(node.left, N.ConditionNode):
                self._visit_condition(node.left)
            else:
                self._visit_expr(node.left)
            if isinstance(node.right, N.ConditionNode):
                self._visit_condition(node.right)
            else:
                self._visit_expr(node.right)
        else:
            # Simple relational: both sides are expressions
            self._visit_expr(node.left)
            self._visit_expr(node.right)

    # -----------------------------------------------------------------------
    # Expression type inference
    # Returns: "int" | "float" | None (None means an error was already logged)
    # -----------------------------------------------------------------------
    def _visit_expr(self, node: N.ASTNode) -> Optional[str]:
        if isinstance(node, N.IntLiteralNode):
            return "int"

        elif isinstance(node, N.FloatLiteralNode):
            return "float"

        elif isinstance(node, N.IdentifierNode):
            symbol = self._symtab.lookup(node.name)
            if symbol is None:
                self._error(
                    ERR_UNDECLARED_VAR, node.name, node.line,
                    f"Undeclared variable '{node.name}'",
                )
                return None
            return symbol["type"]

        elif isinstance(node, N.UnaryOpNode):
            operand_type = self._visit_expr(node.operand)
            return operand_type   # unary minus preserves type

        elif isinstance(node, N.BinOpNode):
            left_type  = self._visit_expr(node.left)
            right_type = self._visit_expr(node.right)
            return self._wider_type(left_type, right_type)

        elif isinstance(node, N.FuncCallExprNode):
            return self._visit_func_call_expr(node)

        elif isinstance(node, N.ConditionNode):
            # Shouldn't appear as a pure expression in our grammar,
            # but handle gracefully
            self._visit_condition(node)
            return "int"  # conditions evaluate to 0 or 1 conceptually

        return None

    # -----------------------------------------------------------------------
    # Function call (used from both expression and statement contexts)
    # -----------------------------------------------------------------------
    def _visit_func_call_expr(self, node: N.FuncCallExprNode) -> Optional[str]:
        symbol = self._symtab.lookup(node.name)

        if symbol is None or symbol["kind"] != "function":
            self._error(
                ERR_UNDECLARED_FUNC, node.name, node.line,
                f"Call to undeclared function '{node.name}'",
            )
            # Still type-check arguments for further error discovery
            for arg in node.args:
                self._visit_expr(arg)
            return None

        # Check argument count
        expected_count = len(symbol["param_types"])
        actual_count   = len(node.args)
        if actual_count != expected_count:
            self._error(
                ERR_ARGUMENT_COUNT, node.name, node.line,
                f"Function '{node.name}' expects {expected_count} argument(s) "
                f"but got {actual_count}",
            )

        # Type-check each argument against the corresponding parameter type
        for i, arg in enumerate(node.args):
            arg_type = self._visit_expr(arg)
            if i < expected_count and arg_type is not None:
                param_type = symbol["param_types"][i]
                # float arg to int param is a mismatch
                if param_type == "int" and arg_type == "float":
                    self._error(
                        ERR_TYPE_MISMATCH, node.name, node.line,
                        f"Argument {i+1} of '{node.name}': "
                        f"expected 'int', got 'float'",
                    )

        return symbol["return_type"]

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _declare_variable(
        self,
        name: str,
        kind: str,
        var_type: str,
        line: int,
    ) -> None:
        """Declare a variable/parameter in the current scope, recording any error."""
        entry = {
            "name":  name,
            "kind":  kind,
            "type":  var_type,
            "line":  line,
        }
        try:
            self._symtab.declare(entry)
        except DuplicateDeclarationError as e:
            self._error(ERR_DUPLICATE_DECL, name, line, str(e))

    def _check_assignment_types(
        self,
        target_type: str,
        expr_type: str,
        name: str,
        line: int,
    ) -> None:
        """
        Report a TYPE_MISMATCH if assigning a float expression to an int variable.
        int → float (widening) is allowed and not flagged.
        """
        if target_type == "int" and expr_type == "float":
            self._error(
                ERR_TYPE_MISMATCH, name, line,
                f"Cannot assign 'float' expression to 'int' variable '{name}'",
            )

    @staticmethod
    def _wider_type(
        left: Optional[str], right: Optional[str]
    ) -> Optional[str]:
        """
        Return the wider of two types.
          int  op int   → int
          int  op float → float
          float op int  → float
          float op float→ float
          None anywhere → None  (error already reported)
        """
        if left is None or right is None:
            return None
        if left == "float" or right == "float":
            return "float"
        return "int"

    def _error(
        self,
        code: str,
        name: str,
        line: Optional[int],
        message: str,
    ) -> None:
        """Append a structured error dict."""
        self._errors.append({
            "code":    code,
            "name":    name,
            "line":    line,
            "message": message,
        })


# ---------------------------------------------------------------------------
# Module-level convenience function (matches the pipeline's calling convention)
# ---------------------------------------------------------------------------
def analyze(program: N.ProgramNode) -> Dict[str, Any]:
    """
    Run semantic analysis on `program` and return the result dict.

    This is the function called by api/pipeline.py.
    A fresh SemanticAnalyzer is created per call so state never leaks
    between requests.
    """
    analyzer = SemanticAnalyzer()
    return analyzer.analyze(program)
