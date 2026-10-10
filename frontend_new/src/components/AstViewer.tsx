import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { hierarchy, tree } from 'd3-hierarchy';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Search,
  X,
  ListTree,
  Braces,
  Folder,
  FileCode,
  Code2,
  Tag,
  ChevronRight,
  ChevronDown,
  Minus,
  Copy,
  Check,
  Minimize2,
  GitBranch,
} from 'lucide-react';

import {
  transformAstToTree,
  CATEGORY_STYLES,
  type TreeNodeData,
  type NodeCategory,
} from './astTransformer';

// Card and layout geometry
const CARD_WIDTH = 168;
const CARD_HEIGHT = 62;
const HORIZONTAL_SPACING = 36;
const VERTICAL_SPACING = 72;

function getNodeIcon(category: NodeCategory) {
  switch (category) {
    case 'structure':
      return <Folder size={12} color="#818cf8" />;
    case 'declaration':
      return <FileCode size={12} color="#22d3ee" />;
    case 'expression':
      return <Code2 size={12} color="#c084fc" />;
    case 'identifier':
      return <Tag size={12} color="#2dd4bf" />;
    case 'literal':
      return <Tag size={12} color="#34d399" />;
    case 'control':
      return <GitBranch size={12} color="#fbbf24" />;
    default:
      return <Tag size={12} color="#94a3b8" />;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outline View (Alternative / Fallback)
// ─────────────────────────────────────────────────────────────────────────────
function OutlineNodeRow({
  node,
  depth = 0,
  onSelect,
}: {
  node: TreeNodeData;
  depth?: number;
  onSelect: (node: TreeNodeData) => void;
}) {
  const [collapsed, setCollapsed] = useState(depth > 3);
  const style = CATEGORY_STYLES[node.category];
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div style={{ marginLeft: depth > 0 ? 16 : 0, margin: '3px 0' }}>
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 8px',
          borderRadius: 4,
          background: 'var(--bg-elevated)',
          border: `1px solid ${style.border}`,
          cursor: 'pointer',
          userSelect: 'none',
          fontSize: 12,
          margin: '2px 0',
        }}
        onClick={() => onSelect(node)}
      >
        <span
          style={{ display: 'flex', alignItems: 'center', color: 'var(--text-tertiary)', cursor: 'pointer' }}
          onClick={(e) => {
            if (hasChildren) {
              e.stopPropagation();
              setCollapsed((c) => !c);
            }
          }}
        >
          {hasChildren ? (
            collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />
          ) : (
            <Minus size={10} />
          )}
        </span>

        {node.role && (
          <span style={{ color: 'var(--text-tertiary)', fontWeight: 500, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            {node.role}:
          </span>
        )}

        {getNodeIcon(node.category)}

        <span style={{ fontWeight: 600, color: style.accent, fontFamily: 'var(--font-mono)' }}>
          {node.nodeType}
        </span>

        {node.label && (
          <span style={{ color: 'var(--text-secondary)', fontSize: 11.5 }}>
            ({node.label})
          </span>
        )}

        {node.line && (
          <span style={{ color: 'var(--text-tertiary)', fontSize: 10.5, marginLeft: 4 }}>
            L{node.line}
          </span>
        )}
      </div>

      {hasChildren && !collapsed && (
        <div style={{ borderLeft: '1px dashed var(--border-default)', marginLeft: 8, paddingLeft: 4 }}>
          {node.children.map((c) => (
            <OutlineNodeRow key={c.id} node={c} depth={depth + 1} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main AstViewer Component
// ─────────────────────────────────────────────────────────────────────────────
export function AstViewer({ ast }: { ast: Record<string, unknown> | null }) {
  const containerRef = useRef<HTMLDivElement>(null);

  // View state
  const [viewMode, setViewMode] = useState<'tree' | 'outline' | 'json'>('tree');
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  // Pan & zoom transform
  const [transform, setTransform] = useState({ x: 0, y: 40, scale: 0.95 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // Transform raw AST into rich tree model
  const treeData = useMemo(() => transformAstToTree(ast), [ast]);

  // Compute D3 tree layout
  const { layoutNodes, layoutLinks, bounds, nodeMap } = useMemo(() => {
    if (!treeData) {
      return { layoutNodes: [], layoutLinks: [], bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0 }, nodeMap: new Map<string, TreeNodeData>() };
    }

    const nMap = new Map<string, TreeNodeData>();
    function indexNodes(n: TreeNodeData) {
      nMap.set(n.id, n);
      n.children?.forEach(indexNodes);
    }
    indexNodes(treeData);

    const root = hierarchy<TreeNodeData>(treeData, (d) => {
      if (collapsedIds.has(d.id)) return undefined;
      return d.children && d.children.length > 0 ? d.children : undefined;
    });

    const treeLayout = tree<TreeNodeData>()
      .nodeSize([CARD_WIDTH + HORIZONTAL_SPACING, CARD_HEIGHT + VERTICAL_SPACING])
      .separation((a, b) => (a.parent === b.parent ? 1.05 : 1.25));

    const layoutRoot = treeLayout(root);
    const nodes = layoutRoot.descendants();
    const links = layoutRoot.links();

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    nodes.forEach((d) => {
      minX = Math.min(minX, d.x - CARD_WIDTH / 2);
      maxX = Math.max(maxX, d.x + CARD_WIDTH / 2);
      minY = Math.min(minY, d.y - CARD_HEIGHT / 2);
      maxY = Math.max(maxY, d.y + CARD_HEIGHT / 2);
    });

    return {
      layoutNodes: nodes,
      layoutLinks: links,
      bounds: { minX, maxX, minY, maxY },
      nodeMap: nMap,
    };
  }, [treeData, collapsedIds]);

  // Selected node object
  const selectedNode: TreeNodeData | null = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodeMap.get(selectedNodeId) ?? null;
  }, [selectedNodeId, nodeMap]);

  // Fit tree to container viewport
  const fitToScreen = useCallback(() => {
    if (!containerRef.current || layoutNodes.length === 0) return;
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    const bWidth = Math.max(bounds.maxX - bounds.minX, 100);
    const bHeight = Math.max(bounds.maxY - bounds.minY, 100);
    const padding = 50;

    const scaleX = (width - padding * 2) / bWidth;
    const scaleY = (height - padding * 2) / bHeight;
    const scale = Math.min(Math.max(Math.min(scaleX, scaleY), 0.25), 1.2);

    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;

    setTransform({
      x: width / 2 - centerX * scale,
      y: height / 2 - centerY * scale,
      scale,
    });
  }, [bounds, layoutNodes.length]);

  // Reset view to top-centered at 100% scale
  const resetView = useCallback(() => {
    if (!containerRef.current || layoutNodes.length === 0) return;
    const width = containerRef.current.clientWidth;
    const rootX = layoutNodes[0]?.x ?? 0;
    setTransform({
      x: width / 2 - rootX,
      y: 40,
      scale: 0.95,
    });
  }, [layoutNodes]);

  // Auto-fit on initial load, AST changes, or fullscreen toggle
  useEffect(() => {
    const timer = setTimeout(() => {
      fitToScreen();
    }, 60);
    return () => clearTimeout(timer);
  }, [treeData, isFullscreen, fitToScreen]);

  // Zoom controls
  const handleZoom = (factor: number) => {
    setTransform((prev) => {
      const newScale = Math.min(Math.max(prev.scale * factor, 0.15), 3.0);
      if (!containerRef.current) return { ...prev, scale: newScale };
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      const newX = width / 2 - (width / 2 - prev.x) * (newScale / prev.scale);
      const newY = height / 2 - (height / 2 - prev.y) * (newScale / prev.scale);
      return { x: newX, y: newY, scale: newScale };
    });
  };

  // Mouse wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setTransform((prev) => {
      const newScale = Math.min(Math.max(prev.scale * factor, 0.15), 3.0);
      const newX = mouseX - (mouseX - prev.x) * (newScale / prev.scale);
      const newY = mouseY - (mouseY - prev.y) * (newScale / prev.scale);
      return { x: newX, y: newY, scale: newScale };
    });
  };

  // Canvas pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setTransform((prev) => ({
      ...prev,
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    }));
  };

  const handleMouseUp = () => setIsDragging(false);

  // Toggle node collapse
  const toggleCollapse = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Collapse / Expand all
  const expandAll = () => setCollapsedIds(new Set());
  const collapseAll = () => {
    if (!treeData) return;
    const allIds = new Set<string>();
    function collect(n: TreeNodeData) {
      if (n.children && n.children.length > 0 && n.id !== 'root-0') {
        allIds.add(n.id);
      }
      n.children?.forEach(collect);
    }
    collect(treeData);
    setCollapsedIds(allIds);
  };

  // Center on a specific node
  const centerNode = (targetNodeId: string) => {
    const target = layoutNodes.find((d) => d.data.id === targetNodeId);
    if (!target || !containerRef.current) return;
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    setTransform((prev) => ({
      ...prev,
      x: width / 2 - target.x * prev.scale,
      y: height / 2 - target.y * prev.scale,
    }));
  };

  // Copy raw JSON
  const handleCopyJson = () => {
    if (!ast) return;
    navigator.clipboard.writeText(JSON.stringify(ast, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  if (!ast || !treeData) {
    return (
      <div className="empty-state" style={{ padding: 40, textAlign: 'center' }}>
        <GitBranch size={36} style={{ opacity: 0.3, marginBottom: 8 }} />
        <div className="empty-state-title" style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
          No AST Data Available
        </div>
        <div className="empty-state-sub" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          Run the compiler pipeline to view the Abstract Syntax Tree.
        </div>
      </div>
    );
  }

  // Filter matching nodes by search query
  const query = searchQuery.trim().toLowerCase();
  const isMatchingSearch = (nodeData: TreeNodeData) => {
    if (!query) return false;
    return (
      nodeData.nodeType.toLowerCase().includes(query) ||
      (nodeData.label && nodeData.label.toLowerCase().includes(query)) ||
      (nodeData.role && nodeData.role.toLowerCase().includes(query))
    );
  };

  return (
    <div
      style={
        isFullscreen
          ? {
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              width: '100vw',
              height: '100vh',
              zIndex: 9999,
              display: 'flex',
              flexDirection: 'column',
              background: 'var(--bg-base)',
              overflow: 'hidden',
            }
          : {
              display: 'flex',
              flexDirection: 'column',
              height: '620px',
              background: 'var(--bg-base)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              overflow: 'hidden',
              position: 'relative',
            }
      }
    >
      {/* ── Toolbar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          flexWrap: 'wrap',
          gap: 8,
          zIndex: 10,
        }}
      >
        {/* View Mode Toggle */}
        <div style={{ display: 'inline-flex', background: 'var(--bg-base)', borderRadius: 4, padding: 2, border: '1px solid var(--border-subtle)' }}>
          <button
            className={`btn btn-sm ${viewMode === 'tree' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setViewMode('tree')}
            style={{ fontSize: 11, padding: '3px 8px', borderRadius: 3, gap: 5 }}
            title="Connected Tree Diagram"
          >
            <GitBranch size={12} /> Tree Diagram
          </button>
          <button
            className={`btn btn-sm ${viewMode === 'outline' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setViewMode('outline')}
            style={{ fontSize: 11, padding: '3px 8px', borderRadius: 3, gap: 5 }}
            title="Hierarchical Outline View"
          >
            <ListTree size={12} /> Outline View
          </button>
          <button
            className={`btn btn-sm ${viewMode === 'json' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setViewMode('json')}
            style={{ fontSize: 11, padding: '3px 8px', borderRadius: 3, gap: 5 }}
            title="Raw AST JSON"
          >
            <Braces size={12} /> JSON
          </button>
        </div>

        {/* Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={12} style={{ position: 'absolute', left: 8, color: 'var(--text-tertiary)', pointerEvents: 'none' }} />
            <input
              type="text"
              placeholder="Filter node or identifier..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: 'var(--bg-base)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 4,
                padding: '3px 24px 3px 26px',
                color: 'var(--text-primary)',
                fontSize: 11,
                width: 170,
                outline: 'none',
                fontFamily: 'var(--font-mono)',
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: 4,
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-tertiary)',
                  cursor: 'pointer',
                  padding: 2,
                  display: 'flex',
                }}
              >
                <X size={11} />
              </button>
            )}
          </div>
        </div>

        {/* Tree Stats & Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginRight: 4 }}>
            {treeData.subtreeCount} nodes · {Math.round(transform.scale * 100)}%
          </span>

          {viewMode === 'tree' && (
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => handleZoom(1.2)}
                title="Zoom In"
                style={{ padding: '3px 6px', height: 26 }}
              >
                <ZoomIn size={13} />
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => handleZoom(0.8)}
                title="Zoom Out"
                style={{ padding: '3px 6px', height: 26 }}
              >
                <ZoomOut size={13} />
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={fitToScreen}
                title="Fit to Screen"
                style={{ padding: '3px 6px', height: 26 }}
              >
                <Maximize2 size={13} />
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={resetView}
                title="Reset View"
                style={{ padding: '3px 6px', height: 26 }}
              >
                <RotateCcw size={13} />
              </button>
              <div style={{ width: 1, height: 16, background: 'var(--border-subtle)', margin: '0 2px' }} />
              <button
                className="btn btn-ghost btn-sm"
                onClick={expandAll}
                title="Expand All Nodes"
                style={{ padding: '3px 7px', fontSize: 11, height: 26 }}
              >
                Expand All
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={collapseAll}
                title="Collapse All Subtrees"
                style={{ padding: '3px 7px', fontSize: 11, height: 26 }}
              >
                Collapse
              </button>
            </>
          )}

          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setIsFullscreen((f) => !f)}
            title={isFullscreen ? 'Exit Full View' : 'Expand Viewport'}
            style={{ padding: '3px 6px', height: 26 }}
          >
            {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </div>

      {/* ── Main View Content ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {viewMode === 'tree' ? (
          /* ── Interactive Tree Diagram ── */
          <div
            ref={containerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onWheel={handleWheel}
            style={{
              width: '100%',
              height: '100%',
              cursor: isDragging ? 'grabbing' : 'grab',
              userSelect: 'none',
              background: 'radial-gradient(circle, rgba(30, 41, 59, 0.25) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          >
            <svg
              style={{
                width: '100%',
                height: '100%',
                display: 'block',
                overflow: 'visible',
              }}
            >
              <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
                {/* ── Branch Connecting Lines ── */}
                <g className="ast-links">
                  {layoutLinks.map((link, idx) => {
                    const sourceX = link.source.x;
                    const sourceY = link.source.y + CARD_HEIGHT / 2;
                    const targetX = link.target.x;
                    const targetY = link.target.y - CARD_HEIGHT / 2;
                    const midY = (sourceY + targetY) / 2;

                    const pathData = `M ${sourceX} ${sourceY} C ${sourceX} ${midY}, ${targetX} ${midY}, ${targetX} ${targetY}`;
                    const role = link.target.data.role;

                    return (
                      <g key={`link-${idx}`}>
                        <path
                          d={pathData}
                          fill="none"
                          stroke="rgba(100, 116, 139, 0.45)"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                        />
                        {/* Role indicator pill on connector */}
                        {role && (
                          <g transform={`translate(${(sourceX + targetX) / 2}, ${midY})`}>
                            <rect
                              x={-((role.length * 5.5 + 8) / 2)}
                              y={-8}
                              width={role.length * 5.5 + 8}
                              height={16}
                              rx={8}
                              fill="var(--bg-elevated)"
                              stroke="var(--border-subtle)"
                              strokeWidth="1"
                            />
                            <text
                              textAnchor="middle"
                              y={3.5}
                              fill="var(--text-tertiary)"
                              fontSize="9.5"
                              fontFamily="var(--font-mono)"
                              fontWeight="500"
                            >
                              {role}
                            </text>
                          </g>
                        )}
                      </g>
                    );
                  })}
                </g>

                {/* ── AST Node Cards ── */}
                <g className="ast-nodes">
                  {layoutNodes.map((node) => {
                    const data = node.data;
                    const style = CATEGORY_STYLES[data.category];
                    const isSelected = selectedNodeId === data.id;
                    const isMatched = isMatchingSearch(data);
                    const hasChildren = data.children && data.children.length > 0;
                    const isCollapsed = collapsedIds.has(data.id);

                    return (
                      <g
                        key={data.id}
                        transform={`translate(${node.x - CARD_WIDTH / 2}, ${node.y - CARD_HEIGHT / 2})`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedNodeId(data.id);
                        }}
                        style={{ cursor: 'pointer' }}
                      >
                        <foreignObject width={CARD_WIDTH} height={CARD_HEIGHT}>
                          <div
                            style={{
                              width: '100%',
                              height: '100%',
                              borderRadius: 8,
                              background: style.bg,
                              border: `1.5px solid ${
                                isSelected
                                  ? style.borderActive
                                  : isMatched
                                  ? '#38bdf8'
                                  : style.border
                              }`,
                              boxShadow: isSelected
                                ? `0 0 12px ${style.borderActive}`
                                : isMatched
                                ? '0 0 10px rgba(56, 189, 248, 0.6)'
                                : '0 2px 6px rgba(0,0,0,0.3)',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              padding: '5px 8px',
                              boxSizing: 'border-box',
                              position: 'relative',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            {/* Card Top Row: Type & Line */}
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 5, overflow: 'hidden' }}>
                                {getNodeIcon(data.category)}
                                <span
                                  style={{
                                    fontWeight: 700,
                                    fontSize: 11.5,
                                    color: style.accent,
                                    fontFamily: 'var(--font-mono)',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                >
                                  {data.nodeType}
                                </span>
                              </div>
                              {data.line && (
                                <span
                                  style={{
                                    fontSize: 9.5,
                                    color: 'var(--text-tertiary)',
                                    fontFamily: 'var(--font-mono)',
                                    background: 'rgba(0,0,0,0.2)',
                                    padding: '1px 4px',
                                    borderRadius: 3,
                                  }}
                                >
                                  L{data.line}
                                </span>
                              )}
                            </div>

                            {/* Card Bottom Row: Label & Attributes */}
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                fontSize: 11,
                                color: 'var(--text-primary)',
                                fontFamily: 'var(--font-mono)',
                              }}
                            >
                              <span
                                style={{
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  maxWidth: CARD_WIDTH - 42,
                                  color: data.category === 'literal' ? '#34d399' : data.category === 'identifier' ? '#2dd4bf' : 'var(--text-secondary)',
                                  fontWeight: 500,
                                }}
                                title={data.label}
                              >
                                {data.label || '—'}
                              </span>

                              {/* Collapse toggle badge */}
                              {hasChildren && (
                                <button
                                  onClick={(e) => toggleCollapse(data.id, e)}
                                  title={isCollapsed ? `Expand ${data.children.length} children` : 'Collapse children'}
                                  style={{
                                    border: 'none',
                                    background: isCollapsed ? style.accent : 'rgba(255,255,255,0.08)',
                                    color: isCollapsed ? '#0f172a' : 'var(--text-secondary)',
                                    borderRadius: 3,
                                    padding: '1px 4px',
                                    fontSize: 9.5,
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 2,
                                    marginLeft: 4,
                                  }}
                                >
                                  {isCollapsed ? `+${data.children.length}` : <Minus size={9} />}
                                </button>
                              )}
                            </div>
                          </div>
                        </foreignObject>
                      </g>
                    );
                  })}
                </g>
              </g>
            </svg>
          </div>
        ) : viewMode === 'outline' ? (
          /* ── Hierarchical Outline View ── */
          <div style={{ height: '100%', overflow: 'auto', padding: 14 }}>
            <OutlineNodeRow node={treeData} onSelect={(node) => setSelectedNodeId(node.id)} />
          </div>
        ) : (
          /* ── Raw AST JSON View ── */
          <div style={{ height: '100%', overflow: 'auto', padding: 14, position: 'relative' }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleCopyJson}
              style={{ position: 'absolute', top: 12, right: 20, zIndex: 5, fontSize: 11, gap: 4 }}
            >
              {copiedJson ? <Check size={12} color="var(--accent-green)" /> : <Copy size={12} />}
              {copiedJson ? 'Copied!' : 'Copy JSON'}
            </button>
            <pre
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                lineHeight: 1.6,
                color: '#93c5fd',
                margin: 0,
              }}
            >
              {JSON.stringify(ast, null, 2)}
            </pre>
          </div>
        )}

        {/* ── Node Details Inspector Panel ── */}
        {selectedNode && (
          <div
            style={{
              position: 'absolute',
              bottom: 12,
              right: 12,
              width: 310,
              maxHeight: '75%',
              background: 'var(--bg-elevated)',
              border: `1.5px solid ${CATEGORY_STYLES[selectedNode.category].borderActive}`,
              borderRadius: 8,
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
              zIndex: 20,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Inspector Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                borderBottom: '1px solid var(--border-subtle)',
                background: 'rgba(0,0,0,0.15)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {getNodeIcon(selectedNode.category)}
                <span style={{ fontWeight: 700, fontSize: 13, color: CATEGORY_STYLES[selectedNode.category].accent, fontFamily: 'var(--font-mono)' }}>
                  {selectedNode.nodeType}
                </span>
                <span
                  style={{
                    fontSize: 9.5,
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: CATEGORY_STYLES[selectedNode.category].badgeBg,
                    color: CATEGORY_STYLES[selectedNode.category].badgeText,
                    fontWeight: 600,
                  }}
                >
                  {CATEGORY_STYLES[selectedNode.category].name}
                </span>
              </div>
              <button
                onClick={() => setSelectedNodeId(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', padding: 2 }}
              >
                <X size={13} />
              </button>
            </div>

            {/* Inspector Body */}
            <div style={{ padding: '10px 12px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
              {selectedNode.role && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Role in Parent:</span>
                  <code style={{ color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>{selectedNode.role}</code>
                </div>
              )}
              {selectedNode.line && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Source Line:</span>
                  <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>Line {selectedNode.line}</span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>Subtree Nodes:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{selectedNode.subtreeCount}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>Direct Children:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{selectedNode.children.length}</span>
              </div>

              {/* Attributes Table */}
              {Object.keys(selectedNode.attributes).length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Attributes
                  </div>
                  <div style={{ background: 'var(--bg-base)', borderRadius: 4, padding: '4px 8px', border: '1px solid var(--border-subtle)' }}>
                    {Object.entries(selectedNode.attributes).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 11 }}>
                        <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{k}:</span>
                        <code style={{ color: '#a5b4fc', fontFamily: 'var(--font-mono)' }}>{String(v)}</code>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => centerNode(selectedNode.id)}
                  style={{ flex: 1, fontSize: 11, padding: '3px 6px' }}
                >
                  Focus Node
                </button>
                {selectedNode.children.length > 0 && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => toggleCollapse(selectedNode.id)}
                    style={{ flex: 1, fontSize: 11, padding: '3px 6px', background: 'var(--accent-blue)' }}
                  >
                    {collapsedIds.has(selectedNode.id) ? 'Expand' : 'Collapse'}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Legend Footer ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 12px',
          background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: 11,
          color: 'var(--text-tertiary)',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Categories:</span>
          {(
            [
              ['structure', 'Structural'],
              ['declaration', 'Declaration'],
              ['expression', 'Expression / Op'],
              ['identifier', 'Identifier'],
              ['literal', 'Literal'],
              ['control', 'Control Flow'],
            ] as const
          ).map(([cat, label]) => {
            const st = CATEGORY_STYLES[cat];
            return (
              <span key={cat} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: st.accent }} />
                <span>{label}</span>
              </span>
            );
          })}
        </div>
        <div>
          <span>Drag to pan · Scroll to zoom · Click node for details</span>
        </div>
      </div>
    </div>
  );
}

export default AstViewer;
