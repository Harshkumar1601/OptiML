/**
 * astTransformer.ts — Converts raw compiler AST JSON into a rich hierarchical tree model
 * suitable for top-down diagram rendering.
 */

export type NodeCategory =
  | 'structure'
  | 'declaration'
  | 'expression'
  | 'identifier'
  | 'literal'
  | 'control'
  | 'other';

export interface TreeNodeData {
  id: string;
  nodeType: string;
  category: NodeCategory;
  label?: string;
  role?: string;
  line?: number;
  attributes: Record<string, unknown>;
  children: TreeNodeData[];
  raw: Record<string, unknown>;
  subtreeCount: number;
}

export const CATEGORY_STYLES: Record<
  NodeCategory,
  {
    name: string;
    border: string;
    borderActive: string;
    bg: string;
    accent: string;
    badgeBg: string;
    badgeText: string;
    iconColor: string;
  }
> = {
  structure: {
    name: 'Structural',
    border: 'rgba(99, 102, 241, 0.45)',
    borderActive: '#818cf8',
    bg: 'rgba(26, 34, 52, 0.95)',
    accent: '#818cf8',
    badgeBg: 'rgba(99, 102, 241, 0.15)',
    badgeText: '#a5b4fc',
    iconColor: '#818cf8',
  },
  declaration: {
    name: 'Declaration',
    border: 'rgba(6, 182, 212, 0.45)',
    borderActive: '#22d3ee',
    bg: 'rgba(18, 36, 50, 0.95)',
    accent: '#22d3ee',
    badgeBg: 'rgba(6, 182, 212, 0.15)',
    badgeText: '#67e8f9',
    iconColor: '#06b6d4',
  },
  expression: {
    name: 'Expression',
    border: 'rgba(168, 85, 247, 0.45)',
    borderActive: '#c084fc',
    bg: 'rgba(32, 26, 52, 0.95)',
    accent: '#c084fc',
    badgeBg: 'rgba(168, 85, 247, 0.15)',
    badgeText: '#d8b4fe',
    iconColor: '#a855f7',
  },
  identifier: {
    name: 'Identifier',
    border: 'rgba(20, 184, 166, 0.45)',
    borderActive: '#2dd4bf',
    bg: 'rgba(18, 38, 42, 0.95)',
    accent: '#2dd4bf',
    badgeBg: 'rgba(20, 184, 166, 0.15)',
    badgeText: '#5eead4',
    iconColor: '#14b8a6',
  },
  literal: {
    name: 'Literal',
    border: 'rgba(16, 185, 129, 0.45)',
    borderActive: '#34d399',
    bg: 'rgba(18, 38, 32, 0.95)',
    accent: '#34d399',
    badgeBg: 'rgba(16, 185, 129, 0.15)',
    badgeText: '#6ee7b7',
    iconColor: '#10b981',
  },
  control: {
    name: 'Control Flow',
    border: 'rgba(245, 158, 11, 0.45)',
    borderActive: '#fbbf24',
    bg: 'rgba(38, 32, 20, 0.95)',
    accent: '#fbbf24',
    badgeBg: 'rgba(245, 158, 11, 0.15)',
    badgeText: '#fde68a',
    iconColor: '#f59e0b',
  },
  other: {
    name: 'Other',
    border: 'rgba(100, 116, 139, 0.45)',
    borderActive: '#94a3b8',
    bg: 'rgba(28, 35, 48, 0.95)',
    accent: '#94a3b8',
    badgeBg: 'rgba(100, 116, 139, 0.15)',
    badgeText: '#cbd5e1',
    iconColor: '#94a3b8',
  },
};

export function getNodeCategory(nodeType: string): NodeCategory {
  if (['Program', 'Block'].includes(nodeType)) return 'structure';
  if (['FunctionDef', 'Declaration', 'Param'].includes(nodeType)) return 'declaration';
  if (['BinOp', 'UnaryOp', 'Condition', 'FuncCallExpr', 'FuncCallStmt'].includes(nodeType)) return 'expression';
  if (['Identifier'].includes(nodeType)) return 'identifier';
  if (['IntLiteral', 'FloatLiteral'].includes(nodeType)) return 'literal';
  if (['If', 'While', 'For', 'Return', 'Assignment'].includes(nodeType)) return 'control';
  return 'other';
}

function isAstNode(val: unknown): val is Record<string, unknown> {
  return (
    !!val &&
    typeof val === 'object' &&
    !Array.isArray(val) &&
    ('node' in val || 'type' in val || 'node_type' in val)
  );
}

let nextId = 0;

export function transformAstToTree(rawAst: Record<string, unknown> | null): TreeNodeData | null {
  if (!rawAst) return null;
  nextId = 0;
  return buildNode(rawAst, undefined, 'root');
}

function buildNode(
  raw: Record<string, unknown>,
  role?: string,
  idPrefix = 'n'
): TreeNodeData {
  const currentId = `${idPrefix}-${nextId++}`;
  const nodeType = String(raw.node || raw.type || raw.node_type || 'ASTNode');
  const category = getNodeCategory(nodeType);
  const line = typeof raw.line === 'number' && raw.line > 0 ? raw.line : undefined;

  const attributes: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(raw)) {
    if (!['node', 'type', 'node_type'].includes(k) && !isAstNode(v) && !Array.isArray(v)) {
      attributes[k] = v;
    }
  }

  let label: string | undefined;
  const children: TreeNodeData[] = [];

  switch (nodeType) {
    case 'Program': {
      const funcs = Array.isArray(raw.functions) ? raw.functions.filter(isAstNode) : [];
      label = `${funcs.length} function${funcs.length === 1 ? '' : 's'}`;
      funcs.forEach((fn, idx) => {
        children.push(buildNode(fn, funcs.length > 1 ? `fn ${idx + 1}` : 'function', currentId));
      });
      break;
    }

    case 'FunctionDef': {
      const name = String(raw.name || 'func');
      const retType = String(raw.return_type || 'void');
      label = `${name}() → ${retType}`;
      attributes.name = name;
      attributes.return_type = retType;

      const params = Array.isArray(raw.params) ? raw.params.filter(isAstNode) : [];
      params.forEach((param) => {
        children.push(buildNode(param, 'param', currentId));
      });

      if (isAstNode(raw.body)) {
        children.push(buildNode(raw.body, 'body', currentId));
      }
      break;
    }

    case 'Param': {
      const name = String(raw.name || 'arg');
      const pType = String(raw.type || raw.param_type || 'int');
      label = `${name} : ${pType}`;
      attributes.name = name;
      attributes.type = pType;
      break;
    }

    case 'Block': {
      const stmts = Array.isArray(raw.statements) ? raw.statements.filter(isAstNode) : [];
      label = `${stmts.length} statement${stmts.length === 1 ? '' : 's'}`;
      stmts.forEach((stmt, idx) => {
        children.push(buildNode(stmt, `stmt ${idx + 1}`, currentId));
      });
      break;
    }

    case 'Declaration': {
      const name = String(raw.name || '');
      const varType = String(raw.var_type || 'int');
      label = `${name} : ${varType}`;
      attributes.name = name;
      attributes.var_type = varType;

      // Add child identifier representing the declared name
      children.push({
        id: `${currentId}-name`,
        nodeType: 'Identifier',
        category: 'identifier',
        label: name,
        role: 'name',
        line,
        attributes: { name },
        children: [],
        raw: { node: 'Identifier', name, line },
        subtreeCount: 1,
      });

      if (isAstNode(raw.init_expr)) {
        children.push(buildNode(raw.init_expr, 'init', currentId));
      }
      break;
    }

    case 'Assignment': {
      const name = String(raw.name || '');
      label = `${name} =`;
      attributes.name = name;

      children.push({
        id: `${currentId}-target`,
        nodeType: 'Identifier',
        category: 'identifier',
        label: name,
        role: 'target',
        line,
        attributes: { name },
        children: [],
        raw: { node: 'Identifier', name, line },
        subtreeCount: 1,
      });

      if (isAstNode(raw.expr)) {
        children.push(buildNode(raw.expr, 'value', currentId));
      }
      break;
    }

    case 'BinOp': {
      const op = String(raw.op || '+');
      label = `operator: ${op}`;
      attributes.op = op;

      if (isAstNode(raw.left)) {
        children.push(buildNode(raw.left, 'left', currentId));
      }
      if (isAstNode(raw.right)) {
        children.push(buildNode(raw.right, 'right', currentId));
      }
      break;
    }

    case 'UnaryOp': {
      const op = String(raw.op || '-');
      label = `operator: ${op}`;
      attributes.op = op;

      if (isAstNode(raw.operand)) {
        children.push(buildNode(raw.operand, 'operand', currentId));
      }
      break;
    }

    case 'Condition': {
      const op = String(raw.op || '==');
      label = `operator: ${op}`;
      attributes.op = op;

      if (isAstNode(raw.left)) {
        children.push(buildNode(raw.left, 'left', currentId));
      }
      if (isAstNode(raw.right)) {
        children.push(buildNode(raw.right, 'right', currentId));
      }
      break;
    }

    case 'Identifier': {
      const name = String(raw.name || '');
      label = name;
      attributes.name = name;
      break;
    }

    case 'IntLiteral': {
      const val = raw.value !== undefined ? String(raw.value) : '0';
      label = val;
      attributes.value = raw.value;
      break;
    }

    case 'FloatLiteral': {
      const val = raw.value !== undefined ? String(raw.value) : '0.0';
      label = val;
      attributes.value = raw.value;
      break;
    }

    case 'Return': {
      label = raw.expr ? 'return expr' : 'return;';
      if (isAstNode(raw.expr)) {
        children.push(buildNode(raw.expr, 'expr', currentId));
      }
      break;
    }

    case 'If': {
      label = raw.else_block ? 'if-else' : 'if';
      if (isAstNode(raw.condition)) {
        children.push(buildNode(raw.condition, 'cond', currentId));
      }
      if (isAstNode(raw.then_block)) {
        children.push(buildNode(raw.then_block, 'then', currentId));
      }
      if (isAstNode(raw.else_block)) {
        children.push(buildNode(raw.else_block, 'else', currentId));
      }
      break;
    }

    case 'While': {
      label = 'while-loop';
      if (isAstNode(raw.condition)) {
        children.push(buildNode(raw.condition, 'cond', currentId));
      }
      if (isAstNode(raw.body)) {
        children.push(buildNode(raw.body, 'body', currentId));
      }
      break;
    }

    case 'For': {
      label = 'for-loop';
      if (isAstNode(raw.init)) {
        children.push(buildNode(raw.init, 'init', currentId));
      }
      if (isAstNode(raw.condition)) {
        children.push(buildNode(raw.condition, 'cond', currentId));
      }
      if (isAstNode(raw.update)) {
        children.push(buildNode(raw.update, 'update', currentId));
      }
      if (isAstNode(raw.body)) {
        children.push(buildNode(raw.body, 'body', currentId));
      }
      break;
    }

    case 'FuncCallStmt': {
      const call = isAstNode(raw.call_expr) ? raw.call_expr : null;
      label = `${call?.name || 'call'}();`;
      if (call) {
        children.push(buildNode(call, 'call', currentId));
      }
      break;
    }

    case 'FuncCallExpr': {
      const name = String(raw.name || 'func');
      const args = Array.isArray(raw.args) ? raw.args.filter(isAstNode) : [];
      label = `${name}(${args.length})`;
      attributes.name = name;
      args.forEach((arg, i) => {
        children.push(buildNode(arg, `arg ${i + 1}`, currentId));
      });
      break;
    }

    default: {
      // General fallback
      for (const [key, val] of Object.entries(raw)) {
        if (['node', 'type', 'node_type', 'line'].includes(key)) continue;
        if (isAstNode(val)) {
          children.push(buildNode(val, key, currentId));
        } else if (Array.isArray(val)) {
          const arrNodes = val.filter(isAstNode);
          arrNodes.forEach((child, i) => {
            children.push(buildNode(child, arrNodes.length > 1 ? `${key} ${i + 1}` : key, currentId));
          });
        }
      }
      break;
    }
  }

  const subtreeCount = 1 + children.reduce((acc, c) => acc + c.subtreeCount, 0);

  return {
    id: currentId,
    nodeType,
    category,
    label,
    role,
    line,
    attributes,
    children,
    raw,
    subtreeCount,
  };
}
