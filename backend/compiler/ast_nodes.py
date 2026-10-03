"""
compiler/ast_nodes.py — AST Node class hierarchy for the restricted C-like language.

Every node class:
  - Stores positional info (line number) for error reporting in later phases.
  - Implements to_dict() for JSON serialization to the frontend.
  - Has a __repr__ for clean debugging output.

Node hierarchy:
  ASTNode (base)
  ├── ProgramNode
  ├── FunctionDefNode
  ├── ParamNode
  ├── BlockNode
  ├── statements/
  │   ├── DeclarationNode
  │   ├── AssignmentNode
  │   ├── IfNode
  │   ├── WhileNode
  │   ├── ForNode
  │   ├── ReturnNode
  │   └── FuncCallStmtNode
  ├── expressions/
  │   ├── BinOpNode
  │   ├── UnaryOpNode
  │   ├── IdentifierNode
  │   ├── IntLiteralNode
  │   ├── FloatLiteralNode
  │   └── FuncCallExprNode
  └── ConditionNode
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Base node
# ---------------------------------------------------------------------------
class ASTNode:
    """Abstract base for all AST nodes."""

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict representation of this node."""
        raise NotImplementedError(f"{self.__class__.__name__}.to_dict() not implemented")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()})"


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
class ProgramNode(ASTNode):
    """Root node — holds all function definitions."""

    def __init__(self, functions: List[FunctionDefNode]) -> None:
        self.functions = functions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": "Program",
            "functions": [f.to_dict() for f in self.functions],
        }


class FunctionDefNode(ASTNode):
    """A function definition: `type name(params) { body }`."""

    def __init__(
        self,
        return_type: str,
        name: str,
        params: List[ParamNode],
        body: BlockNode,
        line: int = 0,
    ) -> None:
        self.return_type = return_type
        self.name = name
        self.params = params
        self.body = body
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":        "FunctionDef",
            "return_type": self.return_type,
            "name":        self.name,
            "params":      [p.to_dict() for p in self.params],
            "body":        self.body.to_dict(),
            "line":        self.line,
        }


class ParamNode(ASTNode):
    """A single function parameter: `type name`."""

    def __init__(self, param_type: str, name: str, line: int = 0) -> None:
        self.param_type = param_type
        self.name = name
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":  "Param",
            "type":  self.param_type,
            "name":  self.name,
            "line":  self.line,
        }


class BlockNode(ASTNode):
    """A `{ statement* }` block."""

    def __init__(self, statements: List[ASTNode], line: int = 0) -> None:
        self.statements = statements
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":       "Block",
            "statements": [s.to_dict() for s in self.statements],
            "line":       self.line,
        }


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------
class DeclarationNode(ASTNode):
    """Variable declaration: `type name;` or `type name = expr;`."""

    def __init__(
        self,
        var_type: str,
        name: str,
        init_expr: Optional[ASTNode] = None,
        line: int = 0,
    ) -> None:
        self.var_type = var_type
        self.name = name
        self.init_expr = init_expr
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":      "Declaration",
            "var_type":  self.var_type,
            "name":      self.name,
            "init_expr": self.init_expr.to_dict() if self.init_expr else None,
            "line":      self.line,
        }


class AssignmentNode(ASTNode):
    """Assignment: `name = expr;`."""

    def __init__(self, name: str, expr: ASTNode, line: int = 0) -> None:
        self.name = name
        self.expr = expr
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": "Assignment",
            "name": self.name,
            "expr": self.expr.to_dict(),
            "line": self.line,
        }


class IfNode(ASTNode):
    """If / if-else statement."""

    def __init__(
        self,
        condition: ConditionNode,
        then_block: BlockNode,
        else_block: Optional[BlockNode] = None,
        line: int = 0,
    ) -> None:
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":       "If",
            "condition":  self.condition.to_dict(),
            "then_block": self.then_block.to_dict(),
            "else_block": self.else_block.to_dict() if self.else_block else None,
            "line":       self.line,
        }


class WhileNode(ASTNode):
    """While loop."""

    def __init__(self, condition: ConditionNode, body: BlockNode, line: int = 0) -> None:
        self.condition = condition
        self.body = body
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":      "While",
            "condition": self.condition.to_dict(),
            "body":      self.body.to_dict(),
            "line":      self.line,
        }


class ForNode(ASTNode):
    """For loop: `for(init; condition; update) { body }`."""

    def __init__(
        self,
        init: ASTNode,            # DeclarationNode or AssignmentNode
        condition: ConditionNode,
        update: AssignmentNode,
        body: BlockNode,
        line: int = 0,
    ) -> None:
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":      "For",
            "init":      self.init.to_dict(),
            "condition": self.condition.to_dict(),
            "update":    self.update.to_dict(),
            "body":      self.body.to_dict(),
            "line":      self.line,
        }


class ReturnNode(ASTNode):
    """Return statement: `return expr;` or `return;`."""

    def __init__(self, expr: Optional[ASTNode] = None, line: int = 0) -> None:
        self.expr = expr
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": "Return",
            "expr": self.expr.to_dict() if self.expr else None,
            "line": self.line,
        }


class FuncCallStmtNode(ASTNode):
    """A function call used as a statement: `foo(a, b);`."""

    def __init__(self, call_expr: "FuncCallExprNode", line: int = 0) -> None:
        self.call_expr = call_expr
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":      "FuncCallStmt",
            "call_expr": self.call_expr.to_dict(),
            "line":      self.line,
        }


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
class BinOpNode(ASTNode):
    """Binary arithmetic expression: `left op right`."""

    def __init__(self, op: str, left: ASTNode, right: ASTNode, line: int = 0) -> None:
        self.op = op
        self.left = left
        self.right = right
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":  "BinOp",
            "op":    self.op,
            "left":  self.left.to_dict(),
            "right": self.right.to_dict(),
            "line":  self.line,
        }


class UnaryOpNode(ASTNode):
    """Unary minus: `-expr`."""

    def __init__(self, op: str, operand: ASTNode, line: int = 0) -> None:
        self.op = op          # always "-" for now
        self.operand = operand
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":    "UnaryOp",
            "op":      self.op,
            "operand": self.operand.to_dict(),
            "line":    self.line,
        }


class IdentifierNode(ASTNode):
    """A variable reference: `x`."""

    def __init__(self, name: str, line: int = 0) -> None:
        self.name = name
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {"node": "Identifier", "name": self.name, "line": self.line}


class IntLiteralNode(ASTNode):
    """An integer literal: `42`."""

    def __init__(self, value: int, line: int = 0) -> None:
        self.value = value
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {"node": "IntLiteral", "value": self.value, "line": self.line}


class FloatLiteralNode(ASTNode):
    """A float literal: `3.14`."""

    def __init__(self, value: float, line: int = 0) -> None:
        self.value = value
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {"node": "FloatLiteral", "value": self.value, "line": self.line}


class FuncCallExprNode(ASTNode):
    """A function call used as an expression: `add(a, b)`."""

    def __init__(self, name: str, args: List[ASTNode], line: int = 0) -> None:
        self.name = name
        self.args = args
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": "FuncCallExpr",
            "name": self.name,
            "args": [a.to_dict() for a in self.args],
            "line": self.line,
        }


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------
class ConditionNode(ASTNode):
    """
    A condition expression used in if/while/for.

    Simple form:   `left rel_op right`      (op is one of <, >, <=, >=, ==, !=)
    Compound form: `left && right`  or  `left || right`
    """

    def __init__(
        self,
        op: str,
        left: ASTNode,
        right: ASTNode,
        line: int = 0,
    ) -> None:
        self.op = op
        self.left = left
        self.right = right
        self.line = line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node":  "Condition",
            "op":    self.op,
            "left":  self.left.to_dict(),
            "right": self.right.to_dict(),
            "line":  self.line,
        }
