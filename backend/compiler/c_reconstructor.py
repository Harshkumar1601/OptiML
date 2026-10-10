"""
compiler/c_reconstructor.py — Reconstruct clean, syntactically valid C source
code from optimized Three-Address Code (TAC) and AST/symbol table metadata.

This module addresses the core requirement:
The ML Advisor suggested code tab must display readable C code (e.g.
`int a = 15; int b = a << 1; return b + x + y;`) reflecting the ML-selected
optimizations, rather than raw TAC instructions with compiler temporaries (t0, t1, ...).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from compiler import ast_nodes as N
from compiler.ir_generator import TACInstruction


# ───────────────────────────────────────────────────────────────────────────
# Operator precedence and formatting
# ───────────────────────────────────────────────────────────────────────────

# Lower number = higher precedence (tighter binding in C)
_PRECEDENCE: Dict[str, int] = {
    "PRIMARY": 1,
    "CALL": 1,
    "UNARY": 2,
    "*": 3,
    "/": 3,
    "%": 3,
    "+": 4,
    "-": 4,
    "<<": 5,
    ">>": 5,
    "<": 6,
    "<=": 6,
    ">": 6,
    ">=": 6,
    "==": 7,
    "!=": 7,
    "&&": 11,
    "||": 12,
}


def _is_temp(name: Any) -> bool:
    """Return True if name looks like a compiler temporary (e.g. t0, t1)."""
    return isinstance(name, str) and len(name) >= 2 and name[0] == "t" and name[1:].isdigit()


def _is_numeric(s: Any) -> bool:
    if isinstance(s, (int, float)):
        return True
    if not isinstance(s, str):
        return False
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _to_ast_literal(val: Any) -> N.ASTNode:
    """Convert a numeric literal value or string to an AST node."""
    if isinstance(val, (N.IntLiteralNode, N.FloatLiteralNode, N.IdentifierNode)):
        return val

    s = str(val).strip()
    try:
        if "." in s:
            f = float(s)
            return N.FloatLiteralNode(f)
        i = int(float(s))
        return N.IntLiteralNode(i)
    except (ValueError, TypeError):
        return N.IdentifierNode(s)


def expr_to_c(node: Any, parent_prec: int = 99, is_right: bool = False) -> str:
    """
    Format an AST expression node into valid C source text with proper
    precedence and minimal redundant parentheses.
    """
    if node is None:
        return ""

    if isinstance(node, N.IntLiteralNode):
        return str(node.value)

    if isinstance(node, N.FloatLiteralNode):
        # Render floats consistently (e.g. 4.0, 1.5)
        v = node.value
        s = f"{v:g}"
        if "." not in s and "e" not in s.lower():
            s += ".0"
        return s

    if isinstance(node, N.IdentifierNode):
        return node.name

    if isinstance(node, N.FuncCallExprNode):
        args_str = ", ".join(expr_to_c(arg) for arg in node.args)
        return f"{node.name}({args_str})"

    if isinstance(node, N.UnaryOpNode):
        prec = _PRECEDENCE.get("UNARY", 2)
        inner = expr_to_c(node.operand, parent_prec=prec)
        return f"{node.op}{inner}"

    if isinstance(node, (N.BinOpNode, N.ConditionNode)):
        op = node.op
        prec = _PRECEDENCE.get(op, 8)
        left_str = expr_to_c(node.left, parent_prec=prec, is_right=False)
        right_str = expr_to_c(node.right, parent_prec=prec, is_right=True)
        res = f"{left_str} {op} {right_str}"

        # Determine if wrapping parentheses are required:
        # 1. Child operator binds looser than parent operator (higher precedence number)
        # 2. Right operand with same precedence for non-associative ops (-, /, <<)
        # 3. For bit-shift (<<), if child is binary op, wrap for human clarity and safety
        needs_parens = False
        if prec > parent_prec:
            needs_parens = True
        elif prec == parent_prec and is_right and op in ("-", "/", "<<", ">>"):
            needs_parens = True
        elif op == "<<" and parent_prec <= 5 and (isinstance(node.left, N.BinOpNode) or isinstance(node.right, N.BinOpNode)):
            needs_parens = True

        return f"({res})" if needs_parens else res

    return str(node)


# ───────────────────────────────────────────────────────────────────────────
# TAC Instruction Resolver
# ───────────────────────────────────────────────────────────────────────────

class TACFunctionContext:
    """
    Tracks temporary assignments and variable writes for a single function
    slice of optimized TAC instructions.
    """

    def __init__(self, func_name: str, instructions: List[Dict[str, Any]]) -> None:
        self.func_name = func_name
        self.instructions = instructions

        # Maps temp name (e.g. 't0') -> ASTNode expression
        self.temp_expr: Dict[str, N.ASTNode] = {}

        # Maps temp name -> source variable that stores it (for CSE reuse)
        self.temp_to_var: Dict[str, str] = {}

        # FIFO queues of resolved expressions for statements in this function:
        # Maps var_name -> list of ASTNode expressions written to this var
        self.var_writes: Dict[str, List[N.ASTNode]] = {}

        # List of returned ASTNode expressions
        self.returns: List[Optional[N.ASTNode]] = []

        # List of condition ASTNode expressions (at JUMP_UNLESS instructions)
        self.conditions: List[N.ASTNode] = []

        self._process_instructions()

    def _resolve(self, val: Any) -> N.ASTNode:
        """Resolve an operand into an ASTNode, inlining temporaries."""
        if val is None:
            return N.IdentifierNode("")

        if isinstance(val, N.ASTNode):
            return val

        s = str(val).strip()

        # Check if it is a compiler temporary
        if _is_temp(s):
            # Check if this temp was assigned to an existing source variable
            # and that variable has not been overwritten (CSE)
            if s in self.temp_to_var:
                return N.IdentifierNode(self.temp_to_var[s])

            if s in self.temp_expr:
                return self.temp_expr[s]

            return N.IdentifierNode(s)

        if _is_numeric(s):
            return _to_ast_literal(s)

        return N.IdentifierNode(s)

    def _process_instructions(self) -> None:
        pending_params: List[N.ASTNode] = []

        for instr in self.instructions:
            op = instr.get("op", "")
            dest = instr.get("dest") or instr.get("result") or ""
            a1 = instr.get("arg1")
            a2 = instr.get("arg2")
            extra = instr.get("extra")

            if op == "PARAM":
                pending_params.append(self._resolve(a1))
                continue

            elif op == "CALL":
                func_called = str(a1)
                args = list(pending_params)
                pending_params.clear()
                call_node = N.FuncCallExprNode(func_called, args)
                if dest:
                    if _is_temp(dest):
                        self.temp_expr[dest] = call_node
                    else:
                        self.var_writes.setdefault(dest, []).append(call_node)
                        self._invalidate_var(dest)
                continue

            elif op in ("ASSIGN", "="):
                resolved_rhs = self._resolve(a1)
                if _is_temp(dest):
                    self.temp_expr[dest] = resolved_rhs
                else:
                    self._invalidate_var(dest)
                    self.var_writes.setdefault(dest, []).append(resolved_rhs)
                    # If RHS was a temp, link this temp to dest for CSE
                    if _is_temp(a1) and a1 in self.temp_expr:
                        self.temp_to_var[a1] = dest

            elif op == "BINOP":
                operator = extra if extra else "+"
                left = self._resolve(a1)
                right = self._resolve(a2)
                bin_node = N.BinOpNode(operator, left, right)
                if _is_temp(dest):
                    self.temp_expr[dest] = bin_node
                else:
                    self.var_writes.setdefault(dest, []).append(bin_node)
                    self._invalidate_var(dest)

            elif op == "UNARY":
                operator = extra if extra else "-"
                operand = self._resolve(a1)
                un_node = N.UnaryOpNode(operator, operand)
                if _is_temp(dest):
                    self.temp_expr[dest] = un_node
                else:
                    self.var_writes.setdefault(dest, []).append(un_node)
                    self._invalidate_var(dest)

            elif op == "COMPARE":
                operator = extra if extra else "=="
                left = self._resolve(a1)
                right = self._resolve(a2)
                cond_node = N.ConditionNode(operator, left, right)
                if _is_temp(dest):
                    self.temp_expr[dest] = cond_node
                else:
                    self.var_writes.setdefault(dest, []).append(cond_node)
                    self._invalidate_var(dest)

            elif op == "AND":
                left = self._resolve(a1)
                right = self._resolve(a2)
                cond_node = N.ConditionNode("&&", left, right)
                if _is_temp(dest):
                    self.temp_expr[dest] = cond_node

            elif op == "OR":
                left = self._resolve(a1)
                right = self._resolve(a2)
                cond_node = N.ConditionNode("||", left, right)
                if _is_temp(dest):
                    self.temp_expr[dest] = cond_node

            elif op == "NOT":
                operand = self._resolve(a1)
                un_node = N.UnaryOpNode("!", operand)
                if _is_temp(dest):
                    self.temp_expr[dest] = un_node

            elif op in ("JUMP_UNLESS", "JUMP_IF_FALSE"):
                cond_val = a2 if a2 is not None else a1
                cond_expr = self._resolve(cond_val)
                self.conditions.append(cond_expr)

            elif op == "RETURN":
                if a1 is not None:
                    self.returns.append(self._resolve(a1))
                else:
                    self.returns.append(None)

    def _invalidate_var(self, var_name: str) -> None:
        """Invalidate temp_to_var mappings when a variable is modified."""
        to_del = [t for t, v in self.temp_to_var.items() if v == var_name]
        for t in to_del:
            del self.temp_to_var[t]

    def pop_var_write(self, var_name: str, fallback_expr: Optional[N.ASTNode] = None) -> N.ASTNode:
        writes = self.var_writes.get(var_name, [])
        if writes:
            return writes.pop(0)
        return fallback_expr if fallback_expr is not None else N.IdentifierNode(var_name)

    def pop_condition(self, fallback_cond: Optional[N.ConditionNode] = None) -> N.ASTNode:
        if self.conditions:
            return self.conditions.pop(0)
        return fallback_cond if fallback_cond is not None else N.IntLiteralNode(1)

    def pop_return(self, fallback_expr: Optional[N.ASTNode] = None) -> Optional[N.ASTNode]:
        if self.returns:
            return self.returns.pop(0)
        return fallback_expr


# ───────────────────────────────────────────────────────────────────────────
# AST-Guided C Code Generator
# ───────────────────────────────────────────────────────────────────────────

class ASTCodeReconstructor:
    """Walks the AST and formats C source code using optimized expressions."""

    def __init__(self, ast: N.ProgramNode, contexts: Dict[str, TACFunctionContext]) -> None:
        self.ast = ast
        self.contexts = contexts
        self.current_ctx: Optional[TACFunctionContext] = None
        self.lines: List[str] = []

    def generate(self) -> str:
        self.lines = []
        for i, func in enumerate(self.ast.functions):
            if i > 0:
                self.lines.append("")
            self.current_ctx = self.contexts.get(func.name)
            self._gen_function(func)

        return "\n".join(self.lines)

    def _gen_function(self, func: N.FunctionDefNode) -> None:
        params_str = ", ".join(f"{p.param_type} {p.name}" for p in func.params)
        self.lines.append(f"{func.return_type} {func.name}({params_str}) {{")
        self._gen_block(func.body, indent=4)
        self.lines.append("}")

    def _gen_block(self, block: N.BlockNode, indent: int) -> None:
        for stmt in block.statements:
            self._gen_stmt(stmt, indent)

    def _gen_stmt(self, stmt: N.ASTNode, indent: int) -> None:
        ind = " " * indent

        if isinstance(stmt, N.DeclarationNode):
            if stmt.init_expr is not None:
                if self.current_ctx:
                    opt_expr = self.current_ctx.pop_var_write(stmt.name, stmt.init_expr)
                else:
                    opt_expr = stmt.init_expr
                val_str = expr_to_c(opt_expr)
                self.lines.append(f"{ind}{stmt.var_type} {stmt.name} = {val_str};")
            else:
                self.lines.append(f"{ind}{stmt.var_type} {stmt.name};")

        elif isinstance(stmt, N.AssignmentNode):
            if self.current_ctx:
                opt_expr = self.current_ctx.pop_var_write(stmt.name, stmt.expr)
            else:
                opt_expr = stmt.expr
            val_str = expr_to_c(opt_expr)
            self.lines.append(f"{ind}{stmt.name} = {val_str};")

        elif isinstance(stmt, N.ReturnNode):
            if stmt.expr is not None:
                if self.current_ctx:
                    opt_expr = self.current_ctx.pop_return(stmt.expr)
                else:
                    opt_expr = stmt.expr
                val_str = expr_to_c(opt_expr)
                self.lines.append(f"{ind}return {val_str};")
            else:
                self.lines.append(f"{ind}return;")

        elif isinstance(stmt, N.FuncCallStmtNode):
            call_str = expr_to_c(stmt.call_expr)
            self.lines.append(f"{ind}{call_str};")

        elif isinstance(stmt, N.IfNode):
            if self.current_ctx:
                opt_cond = self.current_ctx.pop_condition(stmt.condition)
            else:
                opt_cond = stmt.condition
            cond_str = expr_to_c(opt_cond)
            self.lines.append(f"{ind}if ({cond_str}) {{")
            self._gen_block(stmt.then_block, indent + 4)
            if stmt.else_block:
                self.lines.append(f"{ind}}} else {{")
                self._gen_block(stmt.else_block, indent + 4)
            self.lines.append(f"{ind}}}")

        elif isinstance(stmt, N.WhileNode):
            if self.current_ctx:
                opt_cond = self.current_ctx.pop_condition(stmt.condition)
            else:
                opt_cond = stmt.condition
            cond_str = expr_to_c(opt_cond)
            self.lines.append(f"{ind}while ({cond_str}) {{")
            self._gen_block(stmt.body, indent + 4)
            self.lines.append(f"{ind}}}")

        elif isinstance(stmt, N.ForNode):
            # Init: can be DeclarationNode or AssignmentNode
            if isinstance(stmt.init, N.DeclarationNode):
                if stmt.init.init_expr is not None:
                    if self.current_ctx:
                        init_expr = self.current_ctx.pop_var_write(stmt.init.name, stmt.init.init_expr)
                    else:
                        init_expr = stmt.init.init_expr
                    init_str = f"{stmt.init.var_type} {stmt.init.name} = {expr_to_c(init_expr)}"
                else:
                    init_str = f"{stmt.init.var_type} {stmt.init.name}"
            elif isinstance(stmt.init, N.AssignmentNode):
                if self.current_ctx:
                    init_expr = self.current_ctx.pop_var_write(stmt.init.name, stmt.init.expr)
                else:
                    init_expr = stmt.init.expr
                init_str = f"{stmt.init.name} = {expr_to_c(init_expr)}"
            else:
                init_str = ""

            if self.current_ctx:
                opt_cond = self.current_ctx.pop_condition(stmt.condition)
            else:
                opt_cond = stmt.condition
            cond_str = expr_to_c(opt_cond)

            # Update: always an AssignmentNode
            if self.current_ctx:
                upd_expr = self.current_ctx.pop_var_write(stmt.update.name, stmt.update.expr)
            else:
                upd_expr = stmt.update.expr
            upd_str = f"{stmt.update.name} = {expr_to_c(upd_expr)}"

            self.lines.append(f"{ind}for ({init_str}; {cond_str}; {upd_str}) {{")
            self._gen_block(stmt.body, indent + 4)
            self.lines.append(f"{ind}}}")

        elif isinstance(stmt, N.BlockNode):
            self.lines.append(f"{ind}{{")
            self._gen_block(stmt, indent + 4)
            self.lines.append(f"{ind}}}")


# ───────────────────────────────────────────────────────────────────────────
# Fallback TAC-only Decompiler
# ───────────────────────────────────────────────────────────────────────────

def _decompile_tac_only(instructions: List[Dict[str, Any]]) -> str:
    """
    Decompile TAC instructions into readable C code when no AST is provided,
    collapsing temporaries (t0, t1, ...) and inferring function headers.
    """
    lines: List[str] = []
    indent = 0
    temp_expr: Dict[str, str] = {}
    declared_vars: Set[str] = set()
    pending_params: List[str] = []

    def _res(v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if _is_temp(s) and s in temp_expr:
            return temp_expr[s]
        return s

    for instr in instructions:
        op = instr.get("op", "")
        dest = str(instr.get("dest") or instr.get("result") or "")
        a1 = instr.get("arg1")
        a2 = instr.get("arg2")
        extra = str(instr.get("extra") if instr.get("extra") is not None else "")

        if op == "FUNC_BEGIN":
            lines.append(f"int {a1}() {{")
            indent = 4
            temp_expr.clear()
            declared_vars.clear()
            pending_params.clear()
            continue

        if op == "FUNC_END":
            lines.append("}")
            lines.append("")
            indent = 0
            continue

        ind = " " * indent

        if op == "LABEL":
            lines.append(f"{a1}:")
            continue

        if op == "JUMP":
            lines.append(f"{ind}goto {a1};")
            continue

        if op in ("JUMP_UNLESS", "JUMP_IF_FALSE"):
            cond = _res(a2 if a2 is not None else a1)
            target = a1 if a2 is not None else a2
            lines.append(f"{ind}if (!{cond}) goto {target};")
            continue

        if op == "JUMP_IF":
            cond = _res(a2 if a2 is not None else a1)
            target = a1 if a2 is not None else a2
            lines.append(f"{ind}if ({cond}) goto {target};")
            continue

        if op == "PARAM":
            pending_params.append(_res(a1))
            continue

        if op == "CALL":
            args_str = ", ".join(pending_params)
            pending_params.clear()
            call_str = f"{a1}({args_str})"
            if dest:
                if _is_temp(dest):
                    temp_expr[dest] = call_str
                else:
                    decl = "int " if dest not in declared_vars else ""
                    declared_vars.add(dest)
                    lines.append(f"{ind}{decl}{dest} = {call_str};")
            else:
                lines.append(f"{ind}{call_str};")
            continue

        if op in ("ASSIGN", "="):
            val = _res(a1)
            if _is_temp(dest):
                temp_expr[dest] = val
            else:
                decl = "int " if dest not in declared_vars else ""
                declared_vars.add(dest)
                lines.append(f"{ind}{decl}{dest} = {val};")
            continue

        if op == "BINOP":
            op_sym = extra if extra else "+"
            left = _res(a1)
            right = _res(a2)
            expr = f"{left} {op_sym} {right}"
            if _is_temp(dest):
                temp_expr[dest] = expr
            else:
                decl = "int " if dest not in declared_vars else ""
                declared_vars.add(dest)
                lines.append(f"{ind}{decl}{dest} = {expr};")
            continue

        if op == "UNARY":
            op_sym = extra if extra else "-"
            operand = _res(a1)
            expr = f"{op_sym}{operand}"
            if _is_temp(dest):
                temp_expr[dest] = expr
            else:
                decl = "int " if dest not in declared_vars else ""
                declared_vars.add(dest)
                lines.append(f"{ind}{decl}{dest} = {expr};")
            continue

        if op == "RETURN":
            if a1 is not None:
                lines.append(f"{ind}return {_res(a1)};")
            else:
                lines.append(f"{ind}return;")
            continue

    if not lines:
        return "// No optimized code generated"

    return "\n".join(lines).strip()


# ───────────────────────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────────────────────

def reconstruct_c_code(
    instructions: List[Any],
    ast: Optional[N.ProgramNode] = None,
    symbol_table: Optional[Any] = None,
) -> str:
    """
    Reconstruct clean, valid C source code from optimized TAC instructions.

    When `ast` is provided, the function reconstructs C code using the AST's
    exact program structure, types, and scopes, updating expressions with
    the values and operations produced by the optimization passes.

    When `ast` is None, falls back to TAC-only decompiler with temporary inlining.
    """
    # Normalize instructions to dicts
    dict_instrs: List[Dict[str, Any]] = []
    for instr in instructions:
        if isinstance(instr, dict):
            dict_instrs.append(instr)
        elif hasattr(instr, "to_dict"):
            dict_instrs.append(instr.to_dict())

    if ast is None:
        return _decompile_tac_only(dict_instrs)

    # Slice instructions by function name
    contexts: Dict[str, TACFunctionContext] = {}
    current_func: Optional[str] = None
    current_slice: List[Dict[str, Any]] = []

    for instr in dict_instrs:
        op = instr.get("op", "")
        if op == "FUNC_BEGIN":
            current_func = str(instr.get("arg1", ""))
            current_slice = []
            continue
        elif op == "FUNC_END":
            if current_func:
                contexts[current_func] = TACFunctionContext(current_func, current_slice)
            current_func = None
            current_slice = []
            continue

        if current_func is not None:
            current_slice.append(instr)

    # Reconstruct from AST
    reconstructor = ASTCodeReconstructor(ast, contexts)
    c_code = reconstructor.generate()
    return c_code.strip() if c_code.strip() else "// No code generated"
