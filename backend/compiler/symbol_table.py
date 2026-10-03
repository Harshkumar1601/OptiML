"""
compiler/symbol_table.py — Scoped symbol table for the restricted C-like language.

Design:
  - Stack-based scoping: each function body and each block pushes a new scope.
  - Scopes are plain dicts keyed by variable name.
  - The global scope (scope 0) holds function signatures only.
  - lookup() walks the stack from innermost to outermost — correct shadowing semantics.
  - declare() writes only to the current (innermost) scope.

Symbol Entry Schema (dict):
  {
    "name":       str,          # variable or function name
    "kind":       str,          # "variable" | "function" | "parameter"
    "type":       str,          # "int" | "float"
    "line":       int,          # declaration line
    "scope_level": int,         # depth at declaration (0 = global)
    # For functions only:
    "return_type": str,
    "param_types": list[str],
  }

Public API:
  SymbolTable()
  .push_scope()            → None
  .pop_scope()             → None
  .declare(entry)          → None   (raises DuplicateDeclarationError)
  .lookup(name)            → dict | None
  .lookup_current(name)    → dict | None
  .current_function()      → dict | None
  .set_current_function(entry)
  .to_list()               → list[dict]   (JSON-safe flat list)
"""

from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
# Custom exceptions — caught by SemanticAnalyzer, never crash the pipeline
# ---------------------------------------------------------------------------
class DuplicateDeclarationError(Exception):
    """Raised when a name is declared twice in the same scope."""
    pass


# ---------------------------------------------------------------------------
# SymbolTable
# ---------------------------------------------------------------------------
class SymbolTable:
    """
    Stack-based scoped symbol table.

    Internal structure:
      _scopes: list of dicts, index 0 = outermost (global), last = current.
    """

    def __init__(self) -> None:
        # Start with global scope
        self._scopes: List[Dict[str, Dict[str, Any]]] = [{}]
        # Track which function we are currently inside (for return-type checking)
        self._current_function: Optional[Dict[str, Any]] = None
        # Permanent log of every symbol ever declared (scopes are popped,
        # so this is the only way to surface local vars in the final output)
        self._all_symbols: List[Dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # Scope management
    # -----------------------------------------------------------------------
    def push_scope(self) -> None:
        """Open a new inner scope (called when entering a block or function body)."""
        self._scopes.append({})

    def pop_scope(self) -> None:
        """Close the current inner scope (called when leaving a block or function body)."""
        if len(self._scopes) > 1:
            self._scopes.pop()

    @property
    def scope_level(self) -> int:
        """Return the current nesting depth (0 = global)."""
        return len(self._scopes) - 1

    # -----------------------------------------------------------------------
    # Declaration
    # -----------------------------------------------------------------------
    def declare(self, entry: Dict[str, Any]) -> None:
        """
        Insert `entry` into the current (innermost) scope.

        Raises DuplicateDeclarationError if the name already exists
        in the CURRENT scope (not outer scopes — shadowing is not an error
        in this language because all vars are function-local, but redeclaration
        in the same block is an error).
        """
        name = entry["name"]
        current = self._scopes[-1]
        if name in current:
            existing = current[name]
            raise DuplicateDeclarationError(
                f"'{name}' already declared in this scope "
                f"(first declared at line {existing['line']})"
            )
        entry.setdefault("scope_level", self.scope_level)
        current[name] = entry
        # Also append to the permanent log for serialization
        self._all_symbols.append(dict(entry))

    # -----------------------------------------------------------------------
    # Lookup
    # -----------------------------------------------------------------------
    def lookup(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Walk scopes from innermost to outermost.
        Returns the first matching symbol entry, or None if not found.
        """
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def lookup_current(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Look up `name` only in the current (innermost) scope.
        Used to detect duplicate declarations in the same block.
        """
        return self._scopes[-1].get(name)

    # -----------------------------------------------------------------------
    # Current function tracking (for return-type validation)
    # -----------------------------------------------------------------------
    def set_current_function(self, entry: Optional[Dict[str, Any]]) -> None:
        """Called when entering/leaving a function definition."""
        self._current_function = entry

    def current_function(self) -> Optional[Dict[str, Any]]:
        """Return the symbol entry of the function currently being analyzed."""
        return self._current_function

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------
    def to_list(self) -> List[Dict[str, Any]]:
        """
        Return a flat JSON-safe list of all declared symbols, including those
        whose scopes have already been popped (e.g. local function variables).
        Used by the API to show the symbol table in the dashboard.
        """
        return [dict(s) for s in self._all_symbols]
