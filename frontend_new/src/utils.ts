// Preset demo programs
export const PRESETS: Record<string, { label: string; code: string }> = {
  constant_folding: {
    label: '1. Constant Folding',
    code: `// Demo: Constant Folding
// CF evaluates constant arithmetic at compile time
int main() {
    int a = 100 + 200 * 3;
    float b = 1.5 + 2.5;
    int c = 4 * 8 - 2;
    return a;
}`,
  },
  constant_propagation: {
    label: '2. Constant Propagation',
    code: `// Demo: Constant Propagation
// CP substitutes known constant values forward
int main() {
    int x = 10;
    int y = 20;
    int z = x + y + 5;
    return z;
}`,
  },
  cse: {
    label: '3. Common Subexpression Elim.',
    code: `// Demo: Common Subexpression Elimination (CSE)
// CSE reuses already-computed subexpressions
int main() {
    int a = 5;
    int b = 10;
    int x = a + b;
    int y = a + b;
    int z = x + y;
    return z;
}`,
  },
  dead_code: {
    label: '4. Dead Code Elimination',
    code: `// Demo: Dead Code Elimination (DCE)
// DCE removes assigned-but-never-used variables
int main() {
    int active = 42;
    int unused1 = 100;
    int unused2 = unused1 + 50;
    return active;
}`,
  },
  strength_reduction: {
    label: '5. Strength Reduction',
    code: `// Demo: Strength Reduction (SR)
// SR replaces expensive mul with cheaper shift
int main() {
    int val = 8;
    int mult4 = val * 4;
    int mult8 = val * 8;
    return mult4 + mult8;
}`,
  },
  multi_pass: {
    label: '6. Multi-Pass (All Passes)',
    code: `// Demo: Multi-Pass Comprehensive
// All 5 optimization passes may activate
int main() {
    int a = 10 + 5;
    int b = a * 2;
    int x = a * 4;
    int y = a * 4;
    int dead_var = 999;
    return b + x + y;
}`,
  },
  function_call: {
    label: '7. Functions & Loops',
    code: `// Demo: Functions + Control Flow
int add(int a, int b) {
    return a + b;
}

int main() {
    int x = 10;
    int y = 20;
    int sum = add(x, y);
    int i = 0;
    while (i < 5) {
        sum = sum + i;
        i = i + 1;
    }
    return sum;
}`,
  },
};

// Format TAC instructions from pipeline response
export function formatTACLines(instructions: unknown[]): string[] {
  return instructions.map((instr) => {
    if (typeof instr === 'string') return instr;
    const i = instr as Record<string, string>;
    const op = i.op || '';
    const dest = i.dest || i.result || '';
    const dst = dest ? `${dest} = ` : '';
    const arg1 = i.arg1 != null ? String(i.arg1) : '';
    const arg2 = i.arg2 != null ? ` ${i.arg2}` : '';
    const extra = i.extra || '';

    if (op === 'FUNC_BEGIN')    return `[function ${arg1}]`;
    if (op === 'FUNC_END')      return `[end ${arg1}]`;
    if (op === 'LABEL')         return `${arg1}:`;
    if (op === 'JUMP')          return `goto ${arg1}`;
    if (op === 'JUMP_UNLESS' || op === 'JUMP_IF_FALSE') return `ifFalse ${i.arg2 || arg1} goto ${i.arg1 || arg2}`.trim();
    if (op === 'JUMP_IF')       return `if ${i.arg2 || arg1} goto ${i.arg1 || arg2}`.trim();
    if (op === 'RETURN')        return arg1 ? `return ${arg1}` : 'return';
    if (op === 'PARAM')         return `param ${arg1}`;
    if (op === 'CALL')          return `${dst}call ${arg1},${arg2}`;
    if (op === 'ASSIGN' || op === '=') return `${dst}${arg1}`;
    if (op === 'BINOP' || op === 'COMPARE') return `${dst}${arg1} ${extra || op}${arg2}`.trim();
    if (op === 'UNARY')         return `${dst}${extra || '-'}${arg1}`;
    return `${dst}${arg1} ${op}${arg2}`.trim();
  });
}

// Human-readable pass name
export function passDisplayName(pass: string): string {
  const map: Record<string, string> = {
    CONSTANT_FOLDING: 'Constant Folding',
    CONSTANT_PROPAGATION: 'Constant Propagation',
    CSE: 'Common Subexpression Elimination',
    DEAD_CODE_ELIMINATION: 'Dead Code Elimination',
    STRENGTH_REDUCTION: 'Strength Reduction',
  };
  return map[pass] ?? pass;
}

// Pass abbreviation
export function passAbbr(pass: string): string {
  const map: Record<string, string> = {
    CONSTANT_FOLDING: 'CF',
    CONSTANT_PROPAGATION: 'CP',
    CSE: 'CSE',
    DEAD_CODE_ELIMINATION: 'DCE',
    STRENGTH_REDUCTION: 'SR',
  };
  return map[pass] ?? pass.slice(0, 3);
}

// Feature display names
export const FEATURE_LABELS: Record<string, string> = {
  num_loops: 'Loops',
  loop_depth_max: 'Max Loop Depth',
  num_functions: 'Functions',
  num_assignments: 'Assignments',
  num_branches: 'Branches',
  tac_total_instructions: 'TAC Total',
  temp_var_count: 'Temps',
  const_literal_count: 'Constants',
  add_op_count: 'Additions',
  mul_op_count: 'Multiplications',
  div_op_count: 'Divisions',
  num_unique_vars: 'Unique Vars',
  repeated_rhs_count: 'Repeated RHS',
  mul_by_power_of_2: 'Mul by 2^n',
  single_use_temp_count: 'Single-Use Temps',
};

export function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}
