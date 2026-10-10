"""
compiler/optimizer.py — Five TAC-level optimization passes.

This module accepts a list of TACInstruction objects and a list of
pass names selected by the ML model. It applies only the recommended
passes, in the fixed safe order defined in config.PASS_APPLICATION_ORDER.

──────────────────────────────────────────────────────────────────────────
Pass Descriptions
──────────────────────────────────────────────────────────────────────────

1. CONSTANT_FOLDING (CF)
   Pre-condition: A BINOP whose arg1 AND arg2 are both numeric literals.
   Action       : Replace the BINOP with an ASSIGN of the computed result.
   Example      : t0 = 2 + 3  →  t0 = 5

2. CONSTANT_PROPAGATION (CP)
   Pre-condition: An ASSIGN of the form  x = <literal>  where the literal
                  is a constant and x is not redefined before its next use.
   Action       : Replace every subsequent use of x (as arg1/arg2) with
                  the literal value, until x is reassigned.
   Example      : x = 5 ; t0 = x + 1  →  x = 5 ; t0 = 5 + 1

3. COMMON SUBEXPRESSION ELIMINATION (CSE)
   Pre-condition: A BINOP/UNARY whose (op, arg1, arg2/None) triple has
                  appeared before and whose operands have not been
                  modified since the previous occurrence.
   Action       : Replace the duplicate computation with an ASSIGN from
                  the temporary that already holds the result.
   Example      : t0 = a + b ; t1 = a + b  →  t0 = a + b ; t1 = t0

4. DEAD CODE ELIMINATION (DCE)
   Pre-condition: A temporary or variable is written (ASSIGN / BINOP /
                  UNARY / COMPARE / CALL) but never subsequently read as
                  arg1, arg2, or RETURN value before it is overwritten or
                  the function ends.
   Action       : Remove that write instruction.
   Note         : User-declared variable names (non-temporaries) are kept
                  even if unused, to avoid silently removing intentional
                  side effects; only pure temporary variables (tN) are
                  eliminated.

5. STRENGTH REDUCTION (SR)
   Pre-condition: A BINOP of the form  t = x * C  or  t = C * x  where C
                  is a power of 2 (2, 4, 8, 16, …).
   Action       : Replace the multiplication with a left-shift BINOP.
   Example      : t0 = x * 4  →  t0 = x << 2
   Also handles : t = x * 1  →  t = x  (ASSIGN, not shift)
                  t = x * 0  →  t = 0  (ASSIGN constant)

──────────────────────────────────────────────────────────────────────────
Public API
──────────────────────────────────────────────────────────────────────────
  apply(
      instructions : list[TACInstruction],
      passes       : list[str],           # ML-recommended pass names
  ) -> OptimizationResult

  OptimizationResult (dataclass):
      .instructions_before : list[dict]   # original TAC as JSON-safe dicts
      .instructions_after  : list[dict]   # optimized TAC as JSON-safe dicts
      .text_before         : str
      .text_after          : str
      .passes_applied      : list[str]    # passes that actually changed something
      .passes_recommended  : list[str]    # passes the ML model requested
      .changes_per_pass    : dict[str, int]  # instruction-count change per pass
      .stats               : dict         # measured before/after stats
      .to_dict()           : dict         # full JSON-safe result
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from compiler.ir_generator import TACInstruction
import config


# ═══════════════════════════════════════════════════════════════════════════
# Result dataclass
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OptimizationResult:
    """Holds measured before/after TAC and metadata about applied passes."""

    instructions_before: List[Dict[str, Any]]
    instructions_after:  List[Dict[str, Any]]
    text_before:         str
    text_after:          str
    passes_recommended:  List[str]
    passes_applied:      List[str]
    changes_per_pass:    Dict[str, int]   # instructions eliminated per pass

    @property
    def stats(self) -> Dict[str, Any]:
        n_before = _count_real(self.instructions_before)
        n_after  = _count_real(self.instructions_after)
        reduction = n_before - n_after
        pct = round(reduction / n_before * 100, 1) if n_before > 0 else 0.0
        return {
            "instructions_before": n_before,
            "instructions_after":  n_after,
            "reduction_count":     reduction,
            "reduction_percent":   pct,
            "passes_recommended":  self.passes_recommended,
            "passes_applied":      self.passes_applied,
            "result_type":         "MEASURED",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tac_before":        self.instructions_before,
            "tac_after":         self.instructions_after,
            "text_before":       self.text_before,
            "text_after":        self.text_after,
            "optimized_code":    reconstruct_c_code(self.instructions_after),
            "passes_recommended": self.passes_recommended,
            "passes_applied":    self.passes_applied,
            "changes_per_pass":  self.changes_per_pass,
            "stats":             self.stats,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def reconstruct_c_code(instructions: List[Dict[str, Any]]) -> str:
    """Reconstruct clean C-like source code representation from TAC instructions."""
    lines = []
    indent = 0
    pending_params: List[str] = []

    for instr in instructions:
        op = instr.get("op", "")
        dest = instr.get("dest") or instr.get("result") or ""
        a1 = str(instr.get("arg1") if instr.get("arg1") is not None else "")
        a2 = str(instr.get("arg2") if instr.get("arg2") is not None else "")
        extra = str(instr.get("extra") if instr.get("extra") is not None else "")

        if op == "FUNC_BEGIN":
            lines.append(f"int {a1}() {{")
            indent = 4
            continue
        elif op == "FUNC_END":
            lines.append("}")
            lines.append("")
            indent = 0
            continue

        ind = " " * indent

        if op == "LABEL":
            lines.append(f"{a1}:")
        elif op == "JUMP":
            lines.append(f"{ind}goto {a1};")
        elif op in ("JUMP_UNLESS", "JUMP_IF_FALSE"):
            cond = a2 if a2 else a1
            target = a1 if a2 else a2
            lines.append(f"{ind}if (!{cond}) goto {target};")
        elif op == "JUMP_IF":
            lines.append(f"{ind}if ({a2}) goto {a1};")
        elif op in ("ASSIGN", "="):
            lines.append(f"{ind}{dest} = {a1};")
        elif op == "BINOP":
            operator = extra if extra else "+"
            lines.append(f"{ind}{dest} = {a1} {operator} {a2};")
        elif op == "UNARY":
            operator = extra if extra else "-"
            lines.append(f"{ind}{dest} = {operator}{a1};")
        elif op == "COMPARE":
            operator = extra if extra else "=="
            lines.append(f"{ind}{dest} = {a1} {operator} {a2};")
        elif op == "AND":
            lines.append(f"{ind}{dest} = {a1} && {a2};")
        elif op == "OR":
            lines.append(f"{ind}{dest} = {a1} || {a2};")
        elif op == "NOT":
            lines.append(f"{ind}{dest} = !{a1};")
        elif op == "PARAM":
            pending_params.append(a1)
        elif op == "CALL":
            args_str = ", ".join(pending_params)
            pending_params = []
            if dest:
                lines.append(f"{ind}{dest} = {a1}({args_str});")
            else:
                lines.append(f"{ind}{a1}({args_str});")
        elif op == "RETURN":
            if a1:
                lines.append(f"{ind}return {a1};")
            else:
                lines.append(f"{ind}return;")
        else:
            if dest and a1 and extra and a2:
                lines.append(f"{ind}{dest} = {a1} {extra} {a2};")
            elif dest and a1:
                lines.append(f"{ind}{dest} = {a1};")

    if not lines:
        return "// No optimized code generated"

    return "\n".join(lines).strip()

def _count_real(instructions: List[Dict[str, Any]]) -> int:
    """Count instructions that are not structural markers (FUNC_BEGIN/END/LABEL)."""
    skip = {"FUNC_BEGIN", "FUNC_END", "LABEL"}
    return sum(1 for i in instructions if i["op"] not in skip)


def _instrs_to_text(instructions: List[TACInstruction]) -> str:
    return "\n".join(i.to_text() for i in instructions)


def _is_numeric(s: Any) -> bool:
    """Return True if s is a string representation of an int or float literal."""
    if not isinstance(s, str):
        return False
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _to_number(s: str):
    """Convert a literal string to int or float."""
    try:
        return int(s)
    except ValueError:
        return float(s)


def _num_to_str(v) -> str:
    """Serialize a number back to a consistent string."""
    if isinstance(v, float) and v == int(v):
        return f"{v:g}"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _is_temp(name: str) -> bool:
    """Return True if name looks like a TAC temporary (t0, t1, …)."""
    return isinstance(name, str) and len(name) >= 2 and name[0] == "t" and name[1:].isdigit()


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _log2(n: int) -> int:
    return int(math.log2(n))


def _clone(instrs: List[Any]) -> List[TACInstruction]:
    """Deep-copy instruction list so each pass works on a fresh mutable copy.
    Supports both TACInstruction objects and dicts.
    """
    res = []
    for i in instrs:
        if isinstance(i, dict):
            res.append(TACInstruction(
                op=i["op"],
                dest=i.get("dest"),
                arg1=i.get("arg1"),
                arg2=i.get("arg2"),
                extra=i.get("extra")
            ))
        else:
            res.append(copy.copy(i))
    return res


# ═══════════════════════════════════════════════════════════════════════════
# Pass 1 — Constant Folding
# ═══════════════════════════════════════════════════════════════════════════

def _pass_constant_folding(
    instrs: List[TACInstruction],
) -> Tuple[List[TACInstruction], int]:
    """
    Fold BINOP instructions where both operands are numeric literals.
    Also fold UNARY (negation) of a numeric literal.
    Returns (new_instructions, count_folded).
    """
    result: List[TACInstruction] = []
    folded = 0

    for instr in instrs:
        if instr.op == "BINOP" and _is_numeric(instr.arg1) and _is_numeric(instr.arg2):
            a = _to_number(instr.arg1)
            b = _to_number(instr.arg2)
            op = instr.extra
            try:
                if op == "+":
                    val = a + b
                elif op == "-":
                    val = a - b
                elif op == "*":
                    val = a * b
                elif op == "/":
                    if b == 0:
                        result.append(instr)   # do not fold division by zero
                        continue
                    val = a / b if isinstance(a, float) or isinstance(b, float) else a // b
                else:
                    result.append(instr)
                    continue
                result.append(TACInstruction(op="ASSIGN", dest=instr.dest, arg1=_num_to_str(val)))
                folded += 1
                continue
            except Exception:
                pass  # fallthrough to append original

        elif instr.op == "UNARY" and _is_numeric(instr.arg1):
            val = -_to_number(instr.arg1)
            result.append(TACInstruction(op="ASSIGN", dest=instr.dest, arg1=_num_to_str(val)))
            folded += 1
            continue

        result.append(instr)

    return result, folded


# ═══════════════════════════════════════════════════════════════════════════
# Pass 2 — Constant Propagation
# ═══════════════════════════════════════════════════════════════════════════

def _pass_constant_propagation(
    instrs: List[TACInstruction],
) -> Tuple[List[TACInstruction], int]:
    """
    Forward-propagate known constant values into subsequent uses.

    Maintains a map: variable_name → literal_string.
    Whenever a variable is assigned a literal (ASSIGN where arg1 is numeric),
    record it. Whenever the variable is assigned something non-literal,
    evict its entry. Replace occurrences of known variables in arg1/arg2
    of other instructions.

    Propagation stops at control-flow boundaries (LABEL, JUMP*) because
    we do not perform data-flow analysis — this is a conservative,
    single-pass approach that is correct but not maximal.
    """
    const_map: Dict[str, str] = {}   # var → literal string
    result: List[TACInstruction] = []
    replaced = 0

    def _sub(v: Optional[Any]) -> Any:
        """Substitute a known constant for a variable name."""
        nonlocal replaced
        if isinstance(v, str) and v in const_map:
            replaced += 1
            return const_map[v]
        return v

    for instr in instrs:
        op = instr.op

        # At control-flow boundaries, conservatively flush the map because
        # different paths may assign different values to the same variable.
        if op in ("LABEL", "JUMP", "JUMP_IF", "JUMP_UNLESS"):
            const_map.clear()
            result.append(instr)
            continue

        # At function boundaries reset everything
        if op in ("FUNC_BEGIN", "FUNC_END"):
            const_map.clear()
            result.append(instr)
            continue

        # Substitute known constants into operands BEFORE updating the map
        new_instr = copy.copy(instr)
        if op in ("BINOP", "COMPARE", "AND", "OR"):
            new_instr.arg1 = _sub(instr.arg1)
            new_instr.arg2 = _sub(instr.arg2)
        elif op in ("ASSIGN", "UNARY", "PARAM", "RETURN"):
            new_instr.arg1 = _sub(instr.arg1)
        elif op == "CALL":
            pass   # PARAM instructions handle argument substitution

        # Update the constant map based on what this instruction writes
        if op == "ASSIGN" and _is_numeric(new_instr.arg1):
            const_map[new_instr.dest] = new_instr.arg1
        elif op in ("ASSIGN", "BINOP", "UNARY", "COMPARE", "CALL", "AND", "OR"):
            # The destination is now non-constant (or unknown)
            if new_instr.dest and new_instr.dest in const_map:
                del const_map[new_instr.dest]

        result.append(new_instr)

    return result, replaced


# ═══════════════════════════════════════════════════════════════════════════
# Pass 3 — Common Subexpression Elimination (CSE)
# ═══════════════════════════════════════════════════════════════════════════

def _pass_cse(
    instrs: List[TACInstruction],
) -> Tuple[List[TACInstruction], int]:
    """
    Replace repeated computations of the same expression with the
    temporary that already holds the result.

    A subexpression is keyed by (op, arg1, arg2, extra):
      - For BINOP/COMPARE/AND/OR: (op, arg1, arg2, extra)
      - For UNARY: (op, arg1, None, None)

    The cache is invalidated when any operand variable is redefined.
    Control-flow boundaries flush the cache conservatively.
    """
    # Map from expression key → dest temp that holds the result
    expr_cache: Dict[Tuple, str] = {}
    # Map from variable name → set of expression keys that use it
    var_to_keys: Dict[str, Set[Tuple]] = {}
    result: List[TACInstruction] = []
    eliminated = 0

    def _register(key: Tuple, dest: str) -> None:
        expr_cache[key] = dest
        for operand in (key[1], key[2]):
            if isinstance(operand, str) and not _is_numeric(operand):
                var_to_keys.setdefault(operand, set()).add(key)

    def _invalidate(var: str) -> None:
        """Remove all cached expressions that use this variable."""
        for key in list(var_to_keys.get(var, [])):
            expr_cache.pop(key, None)
        var_to_keys.pop(var, None)

    def _flush() -> None:
        expr_cache.clear()
        var_to_keys.clear()

    for instr in instrs:
        op = instr.op

        if op in ("LABEL", "JUMP", "JUMP_IF", "JUMP_UNLESS", "FUNC_BEGIN", "FUNC_END"):
            _flush()
            result.append(instr)
            continue

        if op in ("BINOP", "COMPARE", "AND", "OR"):
            key = (op, instr.arg1, instr.arg2, instr.extra)
            if key in expr_cache:
                # Replace with ASSIGN from cached temp
                result.append(TACInstruction(
                    op="ASSIGN", dest=instr.dest, arg1=expr_cache[key]
                ))
                eliminated += 1
                continue
            else:
                _register(key, instr.dest)
                # Invalidate dest in case it was used as an operand before
                _invalidate(instr.dest)
                _register(key, instr.dest)   # re-register after invalidation

        elif op == "UNARY":
            key = ("UNARY", instr.arg1, None, None)
            if key in expr_cache:
                result.append(TACInstruction(
                    op="ASSIGN", dest=instr.dest, arg1=expr_cache[key]
                ))
                eliminated += 1
                continue
            else:
                _register(key, instr.dest)

        elif op == "ASSIGN":
            # An assignment invalidates any expression that used dest as operand
            _invalidate(instr.dest)

        elif op in ("CALL",):
            # Calls may have side effects — flush everything
            _flush()

        result.append(instr)

    return result, eliminated


# ═══════════════════════════════════════════════════════════════════════════
# Pass 4 — Dead Code Elimination (DCE)
# ═══════════════════════════════════════════════════════════════════════════

def _pass_dce(
    instrs: List[TACInstruction],
) -> Tuple[List[TACInstruction], int]:
    """
    Remove instructions that write to a temporary (tN) that is never
    subsequently read before it is overwritten or the function ends.

    Algorithm (single backward scan):
      1. Walk backwards through instructions.
      2. Maintain a 'live' set of variables that are needed.
      3. When we see a use (arg1, arg2, RETURN val), add it to live.
      4. When we see a definition (dest) of a TEMPORARY that is NOT live,
         mark that instruction for removal.
      5. When we see a definition of any variable, remove it from live.

    Only pure temporaries (tN names) are candidates for elimination.
    User-declared variable names are always kept — removing them could
    change observable program behavior (they may be read later or returned).
    """
    # Collect all writes to temporaries and user variables
    def _defs(instr: TACInstruction) -> Optional[str]:
        if instr.op in ("ASSIGN", "BINOP", "UNARY", "COMPARE", "AND", "OR", "NOT", "CALL"):
            return instr.dest
        return None

    def _uses(instr: TACInstruction) -> List[str]:
        used = []
        for v in (instr.arg1, instr.arg2):
            if isinstance(v, str) and not _is_numeric(v) and v is not None:
                used.append(v)
        return used

    # Backward liveness pass
    live: Set[str] = set()
    keep: List[bool] = [True] * len(instrs)

    for idx in range(len(instrs) - 1, -1, -1):
        instr = instrs[idx]

        # Add uses to live set
        for v in _uses(instr):
            live.add(v)

        # Check if this instruction's destination is a dead temporary
        dest = _defs(instr)
        if dest is not None:
            if _is_temp(dest) and dest not in live:
                keep[idx] = False
            else:
                live.discard(dest)

    result = [instr for instr, k in zip(instrs, keep) if k]
    eliminated = sum(1 for k in keep if not k)
    return result, eliminated


# ═══════════════════════════════════════════════════════════════════════════
# Pass 5 — Strength Reduction (SR)
# ═══════════════════════════════════════════════════════════════════════════

def _pass_strength_reduction(
    instrs: List[TACInstruction],
) -> Tuple[List[TACInstruction], int]:
    """
    Replace expensive operations with cheaper equivalents:

    x * 1   →  ASSIGN(x)          (no operation at all)
    x * 0   →  ASSIGN(0)          (constant zero)
    x * 2^k →  x << k   (BINOP with op='<<')
    1 * x   →  ASSIGN(x)
    0 * x   →  ASSIGN(0)
    2^k * x →  x << k

    Division:
    x / 1   →  ASSIGN(x)

    Note: x << k is emitted as a BINOP with extra='<<' and arg2=str(k).
    The text renderer will display it correctly. Only integer powers of 2
    are reduced (not floats, since bit-shifts on floats are undefined).
    """
    result: List[TACInstruction] = []
    reduced = 0

    for instr in instrs:
        if instr.op != "BINOP":
            result.append(instr)
            continue

        op   = instr.extra
        a1   = instr.arg1
        a2   = instr.arg2
        dest = instr.dest

        # Determine which side (if any) is an integer literal
        a1_num = _is_numeric(a1)
        a2_num = _is_numeric(a2)

        if op == "*":
            # x * C  or  C * x
            if a2_num and not _is_numeric(a2.replace("-", "")):
                pass  # negative literal — skip
            elif a1_num and not _is_numeric(a1.replace("-", "")):
                pass
            else:
                const_side = None
                var_side   = None

                if a2_num:
                    try:
                        c = int(float(a2))
                        if str(c) == a2 or f"{float(a2):g}" == a2:
                            const_side = c
                            var_side   = a1
                    except (ValueError, TypeError):
                        pass
                elif a1_num:
                    try:
                        c = int(float(a1))
                        if str(c) == a1 or f"{float(a1):g}" == a1:
                            const_side = c
                            var_side   = a2
                    except (ValueError, TypeError):
                        pass

                if const_side is not None and var_side is not None:
                    if const_side == 0:
                        result.append(TACInstruction(op="ASSIGN", dest=dest, arg1="0"))
                        reduced += 1
                        continue
                    elif const_side == 1:
                        result.append(TACInstruction(op="ASSIGN", dest=dest, arg1=var_side))
                        reduced += 1
                        continue
                    elif _is_power_of_two(const_side):
                        shift = _log2(const_side)
                        result.append(TACInstruction(
                            op="BINOP", dest=dest,
                            arg1=var_side, arg2=str(shift), extra="<<"
                        ))
                        reduced += 1
                        continue

        elif op == "/":
            # x / 1  →  x
            if a2_num:
                try:
                    c = int(float(a2))
                    if c == 1 and (str(c) == a2 or f"{float(a2):g}" == a2):
                        result.append(TACInstruction(op="ASSIGN", dest=dest, arg1=a1))
                        reduced += 1
                        continue
                except (ValueError, TypeError):
                    pass

        result.append(instr)

    return result, reduced


# ═══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

# Map pass name → pass function
_PASS_FUNCTIONS = {
    "CONSTANT_FOLDING":      _pass_constant_folding,
    "CONSTANT_PROPAGATION":  _pass_constant_propagation,
    "CSE":                   _pass_cse,
    "DEAD_CODE_ELIMINATION": _pass_dce,
    "STRENGTH_REDUCTION":    _pass_strength_reduction,
}


def apply(
    instructions: List[TACInstruction],
    passes: List[str],
) -> OptimizationResult:
    """
    Apply the requested optimization passes to `instructions` in the fixed
    safe order (config.PASS_APPLICATION_ORDER).

    Only passes present in `passes` are run. If a pass's pre-condition is
    not met (i.e. it makes zero changes), it is NOT counted in passes_applied.

    Args:
        instructions : raw TACInstruction list from the IR generator
        passes       : list of pass name strings recommended by the ML model

    Returns:
        OptimizationResult with measured before/after counts
    """
    # Snapshot the original TAC before any changes
    original = _clone(instructions)
    text_before = _instrs_to_text(original)
    before_dicts = [i.to_dict() for i in original]

    # Work on a mutable copy
    current = _clone(instructions)

    passes_applied: List[str] = []
    changes_per_pass: Dict[str, int] = {}

    # Apply passes in the fixed safe order, skipping unrequested ones
    for pass_name in config.PASS_APPLICATION_ORDER:
        if pass_name not in passes:
            continue

        fn = _PASS_FUNCTIONS.get(pass_name)
        if fn is None:
            continue

        current, n_changed = fn(current)
        changes_per_pass[pass_name] = n_changed
        if n_changed > 0:
            passes_applied.append(pass_name)

    text_after = _instrs_to_text(current)
    after_dicts = [i.to_dict() for i in current]

    return OptimizationResult(
        instructions_before=before_dicts,
        instructions_after=after_dicts,
        text_before=text_before,
        text_after=text_after,
        passes_recommended=list(passes),
        passes_applied=passes_applied,
        changes_per_pass=changes_per_pass,
    )
