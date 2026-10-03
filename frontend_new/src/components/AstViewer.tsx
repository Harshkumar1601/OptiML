import { useState } from 'react';
import { ChevronRight, ChevronDown, Minus } from 'lucide-react';

interface AstNode {
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

function AstNodeRow({ node, depth = 0 }: { node: AstNode; depth?: number }) {
  const [collapsed, setCollapsed] = useState(depth > 2);

  const childKeys = Object.keys(node).filter((k) => {
    if (['type', 'node_type', 'name', 'value', 'op', 'var_type', 'return_type', 'line'].includes(k)) return false;
    const val = node[k];
    if (Array.isArray(val)) return val.some((v) => v && typeof v === 'object' && (v.type || v.node_type));
    return val && typeof val === 'object' && ((val as AstNode).type || (val as AstNode).node_type);
  });

  const hasChildren = childKeys.length > 0;
  const nodeType = node.type || node.node_type || 'ASTNode';

  const attrs: string[] = [];
  if (node.name) attrs.push(`"${node.name}"`);
  if (node.value !== undefined) attrs.push(String(node.value));
  if (node.op) attrs.push(`op:${node.op}`);
  if (node.var_type) attrs.push(`type:${node.var_type}`);
  if (node.return_type) attrs.push(`ret:${node.return_type}`);

  return (
    <div className="ast-node">
      <div
        className="ast-node-header"
        onClick={() => hasChildren && setCollapsed((c) => !c)}
      >
        <span className="ast-node-toggle">
          {hasChildren ? (
            collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />
          ) : (
            <Minus size={12} />
          )}
        </span>
        <span className="ast-node-type">{nodeType}</span>
        {attrs.length > 0 && (
          <span className="ast-node-attr">({attrs.join(', ')})</span>
        )}
        {node.line && <span className="ast-node-line-num">L{node.line}</span>}
      </div>

      {hasChildren && !collapsed && (
        <div className="ast-children">
          {childKeys.map((key) => {
            const child = node[key];
            if (Array.isArray(child)) {
              return child
                .filter((c) => c && typeof c === 'object' && (c.type || c.node_type))
                .map((c: AstNode, i: number) => (
                  <AstNodeRow key={`${key}-${i}`} node={c} depth={depth + 1} />
                ));
            }
            if (child && typeof child === 'object' && ((child as AstNode).type || (child as AstNode).node_type)) {
              return <AstNodeRow key={key} node={child as AstNode} depth={depth + 1} />;
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
    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 1.8, padding: 12 }}>
      <AstNodeRow node={ast as AstNode} />
    </div>
  );
}

export default AstViewer;
