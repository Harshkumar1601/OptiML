"""
compiler/ir_generator.py — Three-Address Code (TAC) generator.

Converts a semantically valid AST (ProgramNode) into a flat list of
structured TAC instructions. Each instruction is a TACInstruction
dataclass with explicit fields, making downstream optimization passes
and the ML feature extractor straightforward to implement.

─────────────────────────────────────────────
TAC Instruction Set
─────────────────────────────────────────────

  op          | dest   | arg1      | arg2      | Meaning
  ------------|--------|-----------|-----------|---------------------------
  ASSIGN      | x      | y         | —         | x = y
  BINOP       | t      | a         | b         | t = a op b  (op in field)
  UNARY       | t      | a         | —         | t = -a
  LABEL       | —      | label_str | —         | label_str:
  JUMP        | —      | label_str | —         | goto label_str
  JUMP_IF     | —      | label_str | cond_tmp  | if cond_tmp goto label_str
  JUMP_UNLESS | —      | label_str | cond_tmp  | ifFalse cond_tmp goto label_str
  COMPARE     | t      | a         | b         | t = a rel_op b  (op in field)
  AND         | t      | a         | b         | t = a && b
  OR          | t      | a         | b         | t = a || b
  NOT         | t      | a         | —         | t = !a
  PARAM       | —      | arg       | —         | param arg  (push arg for call)
  CALL        | dest   | func_name | n_args    | dest = call func, n_args
  RETURN      | —      | val       | —         | return val  (val may be None)
  FUNC_BEGIN  | —      | func_name | —         | begin function marker
  FUNC_END    | —      | func_name | —         | end function marker

─────────────────────────────────────────────
Temporary and Label Naming
─────────────────────────────────────────────
  Temporaries : t0, t1, t2, ...  (per-generator instance, reset per function)
  Labels      : L0, L1, L2, ...  (per-generator instance, global — unique program-wide)

─────────────────────────────────────────────
Public API
─────────────────────────────────────────────
  generate(program: ProgramNode) -> dict
    Returns:
      {
        "instructions": list[dict],   # each instruction as JSON-safe dict
        "text":         str,          # human-readable TAC listing
        "errors":       list[str],    # any generation errors (should be empty post-semantic)
        "success":      bool,
      }
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from compiler import ast_nodes as N


# ═══════════════════════════════════════════════════════════════════════════
# TAC Instruction dataclass
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TACInstruction:
    """
    A single three-address code instruction.

    Fields:
        op    — opcode string (see table in module docstring)
        dest  — destination variable / label / None
        arg1  — first operand or sub-opcode (e.g. '+' for BINOP), or None
        arg2  — second operand or None
        extra — auxiliary data (e.g. operator string for BINOP/COMPARE)

    Only op is always required; the rest depend on the opcode.
    """
    op:    str
    dest:  Optional[str] = None
    arg1:  Any           = None
    arg2:  Any           = None
    extra: Optional[str] = None   # operator for BINOP / COMPARE

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe dict for API serialization."""
        return {
            "op":    self.op,
            "dest":  self.dest,
            "arg1":  self.arg1,
            "arg2":  self.arg2,
            "extra": self.extra,
        }

    def to_text(self) -> str:
        """Return a human-readable TAC line for debugging and the dashboard."""
        op = self.op

        if op == "FUNC_BEGIN":
            return f"\n[function {self.arg1}]"

        if op == "FUNC_END":
            return f"[end {self.arg1}]\n"

        if op == "LABEL":
            return f"{self.arg1}:"

        if op == "JUMP":
            return f"    goto {self.arg1}"

        if op == "JUMP_IF":
            # arg1 = label, arg2 = condition temp
            return f"    if {self.arg2} goto {self.arg1}"

        if op == "JUMP_UNLESS":
            return f"    ifFalse {self.arg2} goto {self.arg1}"

        if op == "ASSIGN":
            return f"    {self.dest} = {self.arg1}"

        if op == "BINOP":
            return f"    {self.dest} = {self.arg1} {self.extra} {self.arg2}"

        if op == "UNARY":
            return f"    {self.dest} = -{self.arg1}"

        if op == "COMPARE":
            return f"    {self.dest} = {self.arg1} {self.extra} {self.arg2}"

        if op == "AND":
            return f"    {self.dest} = {self.arg1} && {self.arg2}"

        if op == "OR":
            return f"    {self.dest} = {self.arg1} || {self.arg2}"

        if op == "NOT":
            return f"    {self.dest} = !{self.arg1}"

        if op == "PARAM":
            return f"    param {self.arg1}"

        if op == "CALL":
            if self.dest:
                return f"    {self.dest} = call {self.arg1}, {self.arg2}"
            return f"    call {self.arg1}, {self.arg2}"

        if op == "RETURN":
            if self.arg1 is not None:
                return f"    return {self.arg1}"
            return "    return"

        # Fallback
        return f"    {op} {self.dest} {self.arg1} {self.arg2}"

    def __repr__(self) -> str:
        return f"TACInstruction({self.to_text().strip()})"


# ═══════════════════════════════════════════════════════════════════════════
# TAC Generator
# ═══════════════════════════════════════════════════════════════════════════

class TACGenerator:
    """
    Visitor-style AST walker that emits TACInstructions.

    State:
        _instructions  — the flat, ordered list of all emitted instructions
        _temp_counter  — monotonically increasing temp index (t0, t1, ...)
        _label_counter — monotonically increasing label index (L0, L1, ...)
        _errors        — any generation-time errors (should be empty on valid ASTs)

    A single TACGenerator instance is created per generate() call so
    counters never leak between requests.
    """

    def __init__(self) -> None:
        self._instructions: List[TACInstruction] = []
        self._temp_counter:  int = 0
        self._label_counter: int = 0
        self._errors: List[str] = []

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------
    def generate(self, program: N.ProgramNode) -> Dict[str, Any]:
        """
        Walk the ProgramNode and emit TAC for every function definition.
        Returns the standardized result dict.
        """
        for func in program.functions:
            self._gen_function(func)

        instructions_dicts = [i.to_dict() for i in self._instructions]
        text_lines = [i.to_text() for i in self._instructions]

        return {
            "instructions": instructions_dicts,
            "text":         "\n".join(text_lines),
            "errors":       self._errors,
            "success":      len(self._errors) == 0,
        }

    # -----------------------------------------------------------------------
    # Counter helpers
    # -----------------------------------------------------------------------
    def _new_temp(self) -> str:
        """Allocate the next temporary variable name."""
        name = f"t{self._temp_counter}"
        self._temp_counter += 1
        return name

    def _new_label(self) -> str:
        """Allocate the next unique label name."""
        name = f"L{self._label_counter}"
        self._label_counter += 1
        return name

    # -----------------------------------------------------------------------
    # Emit helper
    # -----------------------------------------------------------------------
    def _emit(self, **kwargs) -> TACInstruction:
        """Create and record a TACInstruction. Returns the instruction."""
        instr = TACInstruction(**kwargs)
        self._instructions.append(instr)
        return instr

    # -----------------------------------------------------------------------
    # Function definition
    # -----------------------------------------------------------------------
    def _gen_function(self, node: N.FunctionDefNode) -> None:
        self._emit(op="FUNC_BEGIN", arg1=node.name)

        # Parameters: treat as pre-assigned variables — no special TAC needed;
        # they exist as named variables in scope. We emit no PARAM instruction
        # for the definition side (only for call sites).

        # Generate body statements
        for stmt in node.body.statements:
            self._gen_stmt(stmt)

        self._emit(op="FUNC_END", arg1=node.name)

    # -----------------------------------------------------------------------
    # Statement dispatch
    # -----------------------------------------------------------------------
    def _gen_stmt(self, node: N.ASTNode) -> None:
        if isinstance(node, N.DeclarationNode):
            self._gen_declaration(node)
        elif isinstance(node, N.AssignmentNode):
            self._gen_assignment(node)
        elif isinstance(node, N.IfNode):
            self._gen_if(node)
        elif isinstance(node, N.WhileNode):
            self._gen_while(node)
        elif isinstance(node, N.ForNode):
            self._gen_for(node)
        elif isinstance(node, N.ReturnNode):
            self._gen_return(node)
        elif isinstance(node, N.FuncCallStmtNode):
            self._gen_call_stmt(node)
        elif isinstance(node, N.BlockNode):
            for s in node.statements:
                self._gen_stmt(s)
        else:
            self._errors.append(f"Unknown statement node type: {type(node).__name__}")

    # -----------------------------------------------------------------------
    # Declaration
    # -----------------------------------------------------------------------
    def _gen_declaration(self, node: N.DeclarationNode) -> None:
        if node.init_expr is not None:
            rhs = self._gen_expr(node.init_expr)
            self._emit(op="ASSIGN", dest=node.name, arg1=rhs)
        # If no initializer, no TAC is needed — the variable slot exists
        # but is uninitialized (semantic analysis already validated usage).

    # -----------------------------------------------------------------------
    # Assignment
    # -----------------------------------------------------------------------
    def _gen_assignment(self, node: N.AssignmentNode) -> None:
        rhs = self._gen_expr(node.expr)
        self._emit(op="ASSIGN", dest=node.name, arg1=rhs)

    # -----------------------------------------------------------------------
    # If / if-else
    #
    # Pattern (no else):
    #   <condition eval → cond_tmp>
    #   ifFalse cond_tmp goto L_end
    #   <then block>
    #   L_end:
    #
    # Pattern (with else):
    #   <condition eval → cond_tmp>
    #   ifFalse cond_tmp goto L_else
    #   <then block>
    #   goto L_end
    #   L_else:
    #   <else block>
    #   L_end:
    # -----------------------------------------------------------------------
    def _gen_if(self, node: N.IfNode) -> None:
        cond_tmp = self._gen_condition(node.condition)

        if node.else_block is None:
            l_end = self._new_label()
            self._emit(op="JUMP_UNLESS", arg1=l_end, arg2=cond_tmp)
            for stmt in node.then_block.statements:
                self._gen_stmt(stmt)
            self._emit(op="LABEL", arg1=l_end)
        else:
            l_else = self._new_label()
            l_end  = self._new_label()
            self._emit(op="JUMP_UNLESS", arg1=l_else, arg2=cond_tmp)
            for stmt in node.then_block.statements:
                self._gen_stmt(stmt)
            self._emit(op="JUMP", arg1=l_end)
            self._emit(op="LABEL", arg1=l_else)
            for stmt in node.else_block.statements:
                self._gen_stmt(stmt)
            self._emit(op="LABEL", arg1=l_end)

    # -----------------------------------------------------------------------
    # While
    #
    # Pattern:
    #   L_start:
    #   <condition eval → cond_tmp>
    #   ifFalse cond_tmp goto L_end
    #   <body>
    #   goto L_start
    #   L_end:
    # -----------------------------------------------------------------------
    def _gen_while(self, node: N.WhileNode) -> None:
        l_start = self._new_label()
        l_end   = self._new_label()

        self._emit(op="LABEL", arg1=l_start)
        cond_tmp = self._gen_condition(node.condition)
        self._emit(op="JUMP_UNLESS", arg1=l_end, arg2=cond_tmp)
        for stmt in node.body.statements:
            self._gen_stmt(stmt)
        self._emit(op="JUMP", arg1=l_start)
        self._emit(op="LABEL", arg1=l_end)

    # -----------------------------------------------------------------------
    # For
    #
    # Pattern:
    #   <init>
    #   L_start:
    #   <condition eval → cond_tmp>
    #   ifFalse cond_tmp goto L_end
    #   <body>
    #   <update>
    #   goto L_start
    #   L_end:
    # -----------------------------------------------------------------------
    def _gen_for(self, node: N.ForNode) -> None:
        # Init (declaration or assignment — both handled by _gen_stmt)
        self._gen_stmt(node.init)

        l_start = self._new_label()
        l_end   = self._new_label()

        self._emit(op="LABEL", arg1=l_start)
        cond_tmp = self._gen_condition(node.condition)
        self._emit(op="JUMP_UNLESS", arg1=l_end, arg2=cond_tmp)
        for stmt in node.body.statements:
            self._gen_stmt(stmt)
        # Update (always an assignment)
        self._gen_assignment(node.update)
        self._emit(op="JUMP", arg1=l_start)
        self._emit(op="LABEL", arg1=l_end)

    # -----------------------------------------------------------------------
    # Return
    # -----------------------------------------------------------------------
    def _gen_return(self, node: N.ReturnNode) -> None:
        if node.expr is not None:
            val = self._gen_expr(node.expr)
            self._emit(op="RETURN", arg1=val)
        else:
            self._emit(op="RETURN", arg1=None)

    # -----------------------------------------------------------------------
    # Function call as statement
    # -----------------------------------------------------------------------
    def _gen_call_stmt(self, node: N.FuncCallStmtNode) -> None:
        self._gen_call_expr(node.call_expr, dest=None)

    # -----------------------------------------------------------------------
    # Expression generation
    # Returns the name of the variable/temporary holding the result.
    # -----------------------------------------------------------------------
    def _gen_expr(self, node: N.ASTNode) -> str:
        if isinstance(node, N.IntLiteralNode):
            return str(node.value)

        if isinstance(node, N.FloatLiteralNode):
            # Format floats consistently: no trailing zeros but always has decimal
            return f"{node.value:g}"

        if isinstance(node, N.IdentifierNode):
            return node.name

        if isinstance(node, N.UnaryOpNode):
            operand = self._gen_expr(node.operand)
            tmp = self._new_temp()
            self._emit(op="UNARY", dest=tmp, arg1=operand)
            return tmp

        if isinstance(node, N.BinOpNode):
            left  = self._gen_expr(node.left)
            right = self._gen_expr(node.right)
            tmp   = self._new_temp()
            self._emit(op="BINOP", dest=tmp, arg1=left, arg2=right, extra=node.op)
            return tmp

        if isinstance(node, N.FuncCallExprNode):
            tmp = self._new_temp()
            self._gen_call_expr(node, dest=tmp)
            return tmp

        if isinstance(node, N.ConditionNode):
            # A condition used directly as an expression (rare but possible)
            return self._gen_condition(node)

        self._errors.append(f"Unknown expression node: {type(node).__name__}")
        return "UNKNOWN"

    # -----------------------------------------------------------------------
    # Condition generation
    # Returns the temporary holding the boolean (0/1) result.
    #
    # For simple rel-op:  t = a rel_op b  (COMPARE instruction)
    # For &&:             t_l = ...; t_r = ...; t = t_l && t_r
    # For ||:             t_l = ...; t_r = ...; t = t_l || t_r
    # -----------------------------------------------------------------------
    def _gen_condition(self, node: N.ConditionNode) -> str:
        op = node.op

        if op in ("&&", "||"):
            # Both children are ConditionNodes (guaranteed by grammar)
            left_tmp  = self._gen_condition_child(node.left)
            right_tmp = self._gen_condition_child(node.right)
            tmp = self._new_temp()
            tac_op = "AND" if op == "&&" else "OR"
            self._emit(op=tac_op, dest=tmp, arg1=left_tmp, arg2=right_tmp)
            return tmp

        # Simple relational: both sides are arithmetic expressions
        left_val  = self._gen_expr(node.left)
        right_val = self._gen_expr(node.right)
        tmp = self._new_temp()
        self._emit(op="COMPARE", dest=tmp, arg1=left_val, arg2=right_val, extra=op)
        return tmp

    def _gen_condition_child(self, node: N.ASTNode) -> str:
        """Dispatch condition child — may be a ConditionNode or an expression."""
        if isinstance(node, N.ConditionNode):
            return self._gen_condition(node)
        return self._gen_expr(node)

    # -----------------------------------------------------------------------
    # Function call (shared between expression and statement contexts)
    # -----------------------------------------------------------------------
    def _gen_call_expr(
        self, node: N.FuncCallExprNode, dest: Optional[str]
    ) -> None:
        """
        Emit PARAM instructions for each argument, then a CALL instruction.
        If dest is None the return value is discarded (call-as-statement).
        """
        # Evaluate each argument and emit a PARAM
        arg_temps = []
        for arg in node.args:
            val = self._gen_expr(arg)
            arg_temps.append(val)

        for val in arg_temps:
            self._emit(op="PARAM", arg1=val)

        self._emit(
            op="CALL",
            dest=dest,
            arg1=node.name,
            arg2=len(node.args),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Validation utilities
# ═══════════════════════════════════════════════════════════════════════════

def validate_instructions(instructions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Lightweight structural validation of a TAC instruction list.

    Checks:
      - Every instruction has an 'op' field
      - Known opcodes only
      - LABEL instructions have a non-empty arg1
      - BINOP/COMPARE instructions have dest, arg1, arg2, extra
      - No duplicate label names

    Returns:
      { "valid": bool, "issues": list[str] }
    """
    KNOWN_OPS = {
        "ASSIGN", "BINOP", "UNARY", "LABEL", "JUMP", "JUMP_IF",
        "JUMP_UNLESS", "COMPARE", "AND", "OR", "NOT", "PARAM",
        "CALL", "RETURN", "FUNC_BEGIN", "FUNC_END",
    }
    issues: List[str] = []
    seen_labels: set = set()

    for i, instr in enumerate(instructions):
        op = instr.get("op")
        if op is None:
            issues.append(f"Instruction {i}: missing 'op' field")
            continue

        if op not in KNOWN_OPS:
            issues.append(f"Instruction {i}: unknown opcode '{op}'")
            continue

        if op == "LABEL":
            label = instr.get("arg1")
            if not label:
                issues.append(f"Instruction {i}: LABEL with empty arg1")
            elif label in seen_labels:
                issues.append(f"Instruction {i}: duplicate label '{label}'")
            else:
                seen_labels.add(label)

        if op in ("BINOP", "COMPARE"):
            for fld in ("dest", "arg1", "arg2", "extra"):
                if instr.get(fld) is None:
                    issues.append(
                        f"Instruction {i} ({op}): missing field '{fld}'"
                    )

        if op == "ASSIGN":
            for fld in ("dest", "arg1"):
                if instr.get(fld) is None:
                    issues.append(
                        f"Instruction {i} (ASSIGN): missing field '{fld}'"
                    )

    return {"valid": len(issues) == 0, "issues": issues}


# ═══════════════════════════════════════════════════════════════════════════
# Module-level convenience function
# ═══════════════════════════════════════════════════════════════════════════

def generate(program: N.ProgramNode) -> Dict[str, Any]:
    """
    Generate TAC from a parsed and semantically analysed ProgramNode.

    A fresh TACGenerator is created per call so counters never leak
    between requests.

    Called by api/pipeline.py after semantic analysis succeeds.
    """
    gen = TACGenerator()
    return gen.generate(program)
