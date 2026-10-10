import { useState } from 'react';
import { ChevronRight, ChevronDown, Minus, Code2, Folder, FileCode, Tag } from 'lucide-react';

interface AstNode {
  node?: string;
  type?: string;
  node_type?: string;
  name?: string;
  value?: unknown;
  op?: string;
  var_type?: string;
  return_type?: string;
  line?: number;
  [key: string]: unknown;
}

function isAstNode(val: unknown): val is AstNode {
  return (
    !!val &&
    typeof val === 'object' &&
    ('node' in val || 'type' in val || 'node_type' in val)
  );
}

const IGNORE_KEYS = [
  'node',
  'type',
  'node_type',
  'name',
  'value',
  'op',
  'var_type',
  'return_type',
  'line',
  'param_type',
];

function getNodeIcon(nodeType: string) {
  if (['Program', 'FunctionDef'].includes(nodeType)) return <Folder size={12} style={{ color: '#8b5cf6' }} />;
  if (['Declaration', 'Assignment'].includes(nodeType)) return <FileCode size={12} style={{ color: '#3b82f6' }} />;
  if (['BinOp', 'UnaryOp', 'Condition'].includes(nodeType)) return <Code2 size={12} style={{ color: '#f59e0b' }} />;
  if (['IntLiteral', 'FloatLiteral', 'Identifier'].includes(nodeType)) return <Tag size={12} style={{ color: '#10b981' }} />;
  return <Tag size={12} style={{ color: '#64748b' }} />;
}

function AstNodeRow({
  node,
  labelKey,
  depth = 0,
}: {
  node: AstNode;
  labelKey?: string;
  depth?: number;
}) {
  const [collapsed, setCollapsed] = useState(depth > 4);

  const childKeys = Object.keys(node).filter((k) => {
    if (IGNORE_KEYS.includes(k)) return false;
    const val = node[k];
    if (Array.isArray(val)) return val.some(isAstNode);
    return isAstNode(val);
  });

  const hasChildren = childKeys.length > 0;
  const nodeType = (node.node || node.type || node.node_type || 'ASTNode') as string;

  const attrs: string[] = [];
  if (node.name) attrs.push(`"${node.name}"`);
  if (node.var_type) attrs.push(`type: ${node.var_type}`);
  if (node.return_type) attrs.push(`returns: ${node.return_type}`);
  if (node.op) attrs.push(`op: '${node.op}'`);
  if (node.value !== undefined) attrs.push(`val: ${String(node.value)}`);

  return (
    <div className="ast-node" style={{ marginLeft: depth > 0 ? 16 : 0, marginTop: 3, marginBottom: 3 }}>
      <div
        className="ast-node-header"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '2px 8px',
          borderRadius: 4,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-subtle)',
          cursor: hasChildren ? 'pointer' : 'default',
          userSelect: 'none',
          fontSize: 12,
        }}
        onClick={() => hasChildren && setCollapsed((c) => !c)}
      >
        <span className="ast-node-toggle" style={{ display: 'flex', alignItems: 'center', color: 'var(--text-tertiary)' }}>
          {hasChildren ? (
            collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />
          ) : (
            <Minus size={10} />
          )}
        </span>

        {labelKey && (
          <span style={{ color: 'var(--text-tertiary)', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
            {labelKey}:
          </span>
        )}

        {getNodeIcon(nodeType)}

        <span className="ast-node-type" style={{ fontWeight: 600, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
          {nodeType}
        </span>

        {attrs.length > 0 && (
          <span className="ast-node-attr" style={{ color: 'var(--text-secondary)', fontSize: 11.5 }}>
            ({attrs.join(', ')})
          </span>
        )}

        {node.line !== undefined && node.line > 0 && (
          <span className="ast-node-line-num" style={{ color: 'var(--text-tertiary)', fontSize: 10.5, marginLeft: 4 }}>
            L{node.line}
          </span>
        )}
      </div>

      {hasChildren && !collapsed && (
        <div className="ast-children" style={{ borderLeft: '1px dashed var(--border-default)', marginLeft: 8, paddingLeft: 4 }}>
          {childKeys.map((key) => {
            const child = node[key];
            if (Array.isArray(child)) {
              const astChildren = child.filter(isAstNode);
              if (astChildren.length === 0) return null;
              return (
                <div key={key} style={{ marginLeft: 12, marginTop: 2 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
                    {key} [{astChildren.length}]:
                  </div>
                  {astChildren.map((c: AstNode, i: number) => (
                    <AstNodeRow key={`${key}-${i}`} node={c} depth={depth + 1} />
                  ))}
                </div>
              );
            }
            if (isAstNode(child)) {
              return <AstNodeRow key={key} node={child} labelKey={key} depth={depth + 1} />;
            }
            return null;
          })}
        </div>
      )}
    </div>
  );
}

export function AstViewer({ ast }: { ast: Record<string, unknown> | null }) {
  if (!ast) {
    return (
      <div className="empty-state">
        <div className="empty-state-sub">No AST data available.</div>
      </div>
    );
  }
  return (
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 1.8, padding: '4px 8px' }}>
      <AstNodeRow node={ast as AstNode} />
    </div>
  );
}

export default AstViewer;

