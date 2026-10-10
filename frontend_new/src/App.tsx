import { useState, useEffect, useRef } from 'react';
import './index.css';
import {
  LayoutDashboard, Code2, Brain, ArrowLeftRight, GitBranch, ListOrdered,
  Table2, Play, Eraser, Loader2, CheckCircle2, XCircle, AlertTriangle,
  Info, Cpu, TrendingDown, Zap, Sparkles, Copy, Check,
} from 'lucide-react';

import { getHealth, getModelInfo, analyzeSource, tokenizeSource, type PipelineResponse, type ModelInfoResponse } from './api';
import { PRESETS, passDisplayName, passAbbr, FEATURE_LABELS, formatTACLines } from './utils';
import { TacComparisonChart, ConfidenceChart } from './components/Charts';
import { TacViewer } from './components/TacViewer';
import { AstViewer } from './components/AstViewer';

type Tab = 'overview' | 'ml' | 'tac' | 'ast' | 'tokens';

const NAV: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview',            icon: <LayoutDashboard size={14} /> },
  { id: 'ml',       label: 'ML Advisor',           icon: <Brain size={14} /> },
  { id: 'tac',      label: 'TAC Comparison',       icon: <ArrowLeftRight size={14} /> },
  { id: 'ast',      label: 'AST & Symbols',        icon: <GitBranch size={14} /> },
  { id: 'tokens',   label: 'Tokens',               icon: <ListOrdered size={14} /> },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [code, setCode] = useState(PRESETS.multi_pass.code);
  const [preset, setPreset] = useState('multi_pass');
  const [loading, setLoading] = useState(false);
  const [tokenizing, setTokenizing] = useState(false);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [lineCount, setLineCount] = useState(1);

  // Backend health check on mount
  useEffect(() => {
    (async () => {
      const h = await getHealth();
      const isOnline = h.status === 'online' || h.status === 'ok';
      setBackendOnline(isOnline);
      if (isOnline) {
        const info = await getModelInfo();
        setModelInfo(info);
      }
    })();
    const interval = setInterval(async () => {
      const h = await getHealth();
      setBackendOnline(h.status === 'online' || h.status === 'ok');
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // Line counter
  useEffect(() => {
    setLineCount(code.split('\n').length);
  }, [code]);

  const handlePresetChange = (key: string) => {
    setPreset(key);
    setCode(PRESETS[key].code);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await analyzeSource(code);
      setResult(res);
      if (!res.success) {
        setError(res.error ?? 'Pipeline failed');
      } else {
        setActiveTab('overview');
      }
    } catch (e) {
      setError('Cannot reach backend. Is `python app.py` running on port 5000?');
    } finally {
      setLoading(false);
    }
  };

  const handleTokenize = async () => {
    if (!code.trim()) return;
    setTokenizing(true);
    setError(null);
    try {
      const res = await tokenizeSource(code);
      setResult(res);
      setActiveTab('tokens');
    } catch {
      setError('Tokenization failed — backend unreachable.');
    } finally {
      setTokenizing(false);
    }
  };

  const stats = result?.stats;
  const phases = result?.phases;

  return (
    <div className="app-layout">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-logo">
          <div className="header-logo-icon">
            <Cpu size={15} />
          </div>
          <span className="header-title">Compiler Optimization Advisor</span>
        </div>
        <div className="header-sep" />
        <span className="header-badge badge-surface" style={{ fontSize: 11 }}>
          PCD Assignment · ML-Powered
        </span>
        <div className="ml-auto flex items-center gap-2">
          {backendOnline ? (
            <span className="header-badge badge-green">
              <span className="status-dot online" /> Backend Online
            </span>
          ) : (
            <span className="header-badge badge-red">
              <span className="status-dot offline" /> Backend Offline
            </span>
          )}
          {modelInfo && (
            <span className="header-badge badge-purple">
              <Brain size={10} /> RF Model · HL {modelInfo.metrics?.hamming_loss ?? '—'}
            </span>
          )}
        </div>
      </header>

      {/* ── Body ── */}
      <div className="app-body">
        {/* Sidebar */}
        <aside className="app-sidebar">
          <div className="sidebar-section-label">Analysis Views</div>
          {NAV.map((item) => (
            <div
              key={item.id}
              className={`sidebar-nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              {item.icon}
              {item.label}
              {item.id === 'tokens' && phases?.tokens && (
                <span className="sidebar-count">{phases.tokens.length}</span>
              )}
              {item.id === 'ast' && phases?.symbol_table && (
                <span className="sidebar-count">{phases.symbol_table.length}</span>
              )}
            </div>
          ))}

          <div className="sidebar-sep" />
          <div className="sidebar-section-label">Pipeline Info</div>
          {result?.success && stats && (
            <>
              <div style={{ padding: '4px 14px 4px', fontSize: 11.5 }}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 3 }}>Instructions</div>
                <div style={{ color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--accent-red)' }}>{stats.instructions_before}</span>
                  {' → '}
                  <span style={{ color: 'var(--accent-green)' }}>{stats.instructions_after}</span>
                </div>
              </div>
              <div style={{ padding: '4px 14px', fontSize: 11.5 }}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 3 }}>Reduction</div>
                <div style={{ color: 'var(--accent-green)', fontWeight: 600 }}>
                  {stats.reduction_count} ({stats.reduction_percent}%)
                </div>
              </div>
              <div style={{ padding: '4px 14px 8px', fontSize: 11.5 }}>
                <div style={{ color: 'var(--text-tertiary)', marginBottom: 3 }}>Passes Applied</div>
                <div style={{ color: 'var(--text-primary)' }}>
                  {stats.passes_applied.length} / 5
                </div>
              </div>
            </>
          )}
          {!result?.success && (
            <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
              Run the pipeline to see stats here.
            </div>
          )}

          <div className="sidebar-sep" />
          <div className="sidebar-section-label">ML Model</div>
          <div style={{ padding: '4px 14px 8px', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Architecture:</span> MultiOutput RF</div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Training:</span> {modelInfo?.training_samples ?? 480} programs</div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Threshold:</span> 0.50 (50%)</div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Hamming Loss:</span>{' '}
              <span style={{ color: 'var(--accent-green)' }}>{modelInfo?.metrics?.hamming_loss ?? '—'}</span>
            </div>
          </div>
        </aside>

        {/* ── Content area ── */}
        <main className="app-content">
          {/* Top split: Editor (left) + Results panel (right) */}
          <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

            {/* ── Left: Code Editor ── */}
            <div style={{
              width: 420,
              flexShrink: 0,
              display: 'flex',
              flexDirection: 'column',
              borderRight: '1px solid var(--border-subtle)',
              background: 'var(--bg-surface)',
            }}>
              {/* Editor toolbar */}
              <div className="toolbar">
                <Code2 size={13} style={{ color: 'var(--text-secondary)' }} />
                <span style={{ fontWeight: 600, fontSize: 12.5 }}>Source Code</span>
                <div className="toolbar-spacer" />
                <select value={preset} onChange={(e) => handlePresetChange(e.target.value)} style={{ fontSize: 11.5 }}>
                  {Object.entries(PRESETS).map(([k, v]) => (
                    <option key={k} value={k}>{v.label}</option>
                  ))}
                </select>
              </div>

              {/* Editor body with line numbers */}
              <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
                <div
                  style={{
                    width: 38,
                    background: 'var(--bg-base)',
                    borderRight: '1px solid var(--border-subtle)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12,
                    lineHeight: '21px',
                    color: 'var(--text-tertiary)',
                    textAlign: 'right',
                    padding: '10px 6px 10px 0',
                    userSelect: 'none',
                    overflowY: 'hidden',
                    flexShrink: 0,
                  }}
                >
                  {Array.from({ length: lineCount }, (_, i) => (
                    <div key={i + 1}>{i + 1}</div>
                  ))}
                </div>
                <textarea
                  ref={textareaRef}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  spellCheck={false}
                  style={{
                    flex: 1,
                    background: 'var(--bg-base)',
                    color: '#a5b4fc',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12.5,
                    lineHeight: '21px',
                    padding: '10px 14px',
                    border: 'none',
                    outline: 'none',
                    resize: 'none',
                    whiteSpace: 'pre',
                    tabSize: 4,
                    overflowY: 'auto',
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Tab') {
                      e.preventDefault();
                      const { selectionStart, selectionEnd, value } = e.currentTarget;
                      const newValue = value.substring(0, selectionStart) + '    ' + value.substring(selectionEnd);
                      setCode(newValue);
                      setTimeout(() => {
                        e.currentTarget.selectionStart = e.currentTarget.selectionEnd = selectionStart + 4;
                      }, 0);
                    }
                  }}
                />
              </div>

              {/* Editor actions */}
              <div style={{
                padding: '10px 12px',
                borderTop: '1px solid var(--border-subtle)',
                display: 'flex',
                gap: 8,
              }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => { setCode(''); setError(null); }}
                  title="Clear editor"
                >
                  <Eraser size={12} /> Clear
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={handleTokenize}
                  disabled={tokenizing || !code.trim()}
                >
                  {tokenizing ? <Loader2 size={12} className="spinner" /> : <ListOrdered size={12} />}
                  Tokenize Only
                </button>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                  onClick={handleAnalyze}
                  disabled={loading || !code.trim()}
                >
                  {loading ? (
                    <><Loader2 size={12} className="spinner" /> Analyzing…</>
                  ) : (
                    <><Play size={12} /> Run Pipeline</>
                  )}
                </button>
              </div>

              {/* Error alert */}
              {error && (
                <div style={{
                  margin: '0 10px 10px',
                  padding: '10px 12px',
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 11.5,
                  color: '#fca5a5',
                  lineHeight: 1.5,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontWeight: 600 }}>
                    <AlertTriangle size={12} /> {error}
                  </div>
                  {result?.errors?.slice(0, 3).map((e, i) => (
                    <div key={i} style={{ color: '#fca5a5', fontSize: 11, paddingLeft: 18 }}>
                      {e.line ? `[L${e.line}] ` : ''}{e.message ?? String(e)}
                    </div>
                  ))}
                </div>
              )}

              {/* Language scope card */}
              <div style={{
                margin: '0 10px 10px',
                padding: '8px 12px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11,
                color: 'var(--text-tertiary)',
              }}>
                <div style={{ fontWeight: 600, marginBottom: 5, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 5 }}>
                  <Info size={11} /> Restricted C-Subset
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {['int', 'float', 'if/else', 'while', 'for', 'functions', '+ - * /', '== != < >'].map((t) => (
                    <code key={t} style={{
                      background: 'var(--bg-base)',
                      border: '1px solid var(--border-subtle)',
                      padding: '1px 5px',
                      borderRadius: 3,
                      fontSize: 10.5,
                      color: '#c7d2fe',
                    }}>{t}</code>
                  ))}
                </div>
              </div>
            </div>

            {/* ── Right: Results Panel ── */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* Tabs */}
              <div className="panel-tabs">
                {NAV.map((item) => (
                  <button
                    key={item.id}
                    className={`panel-tab ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    {item.icon} {item.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div style={{ flex: 1, overflow: 'auto' }}>
                {activeTab === 'overview' && (
                  <OverviewTab result={result} modelInfo={modelInfo} />
                )}
                {activeTab === 'ml' && (
                  <MLTab result={result} modelInfo={modelInfo} onApplyCode={(c) => setCode(c)} />
                )}
                {activeTab === 'tac' && (
                  <TACTab result={result} />
                )}
                {activeTab === 'ast' && (
                  <ASTTab result={result} />
                )}
                {activeTab === 'tokens' && (
                  <TokensTab result={result} />
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────
function OverviewTab({ result, modelInfo: _modelInfo }: { result: PipelineResponse | null; modelInfo: ModelInfoResponse | null }) {
  if (!result?.success || !result.stats) {
    return (
      <div className="empty-state">
        <LayoutDashboard size={36} style={{ opacity: 0.3 }} />
        <div className="empty-state-title">No Results Yet</div>
        <div className="empty-state-sub">
          Select a preset or write C-like code, then click <strong>Run Pipeline</strong> to analyze.
        </div>
      </div>
    );
  }

  const { stats, ml } = result;

  return (
    <div className="panel-fill">
      {/* Stat cards row */}
      <div className="grid-4">
        <div className="stat-card">
          <div className="stat-label">TAC Before</div>
          <div className="stat-value" style={{ color: 'var(--accent-red)' }}>{stats.instructions_before}</div>
          <div className="stat-sub">instructions</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">TAC After</div>
          <div className="stat-value" style={{ color: 'var(--accent-green)' }}>{stats.instructions_after}</div>
          <div className="stat-sub">instructions <span className="header-badge badge-green" style={{ marginLeft: 4 }}>MEASURED</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Reduction</div>
          <div className="stat-value" style={{ color: stats.reduction_count > 0 ? 'var(--accent-green)' : 'var(--text-secondary)' }}>
            {stats.reduction_count}
          </div>
          <div className="stat-sub">{stats.reduction_percent}% fewer instructions</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Passes Applied</div>
          <div className="stat-value">{stats.passes_applied.length}<span style={{ fontSize: 14, color: 'var(--text-secondary)', fontWeight: 400 }}> / 5</span></div>
          <div className="stat-sub">
            ML recommended {stats.passes_recommended.length}{' '}
            <span className="header-badge badge-blue" style={{ marginLeft: 2 }}>ESTIMATED</span>
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title"><TrendingDown size={13} /> TAC Instruction Count</span>
            <span className="header-badge badge-green">MEASURED</span>
          </div>
          <div style={{ height: 200, padding: '12px 16px' }}>
            <TacComparisonChart before={stats.instructions_before} after={stats.instructions_after} />
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title"><Brain size={13} /> ML Confidence per Pass</span>
            <span className="header-badge badge-blue">ESTIMATED</span>
          </div>
          <div style={{ height: 200, padding: '12px 16px' }}>
            {ml?.recommendations && <ConfidenceChart recommendations={ml.recommendations} />}
          </div>
        </div>
      </div>

      {/* Pass summary table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title"><Zap size={13} /> Optimization Pass Summary</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>ML acts as gatekeeper — only recommended passes run</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Pass</th>
              <th>Abbr.</th>
              <th>ML Confidence</th>
              <th>ML Decision</th>
              <th>Applied to TAC</th>
              <th>Result Type</th>
            </tr>
          </thead>
          <tbody>
            {ml?.recommendations?.map((rec) => (
              <tr key={rec.pass}>
                <td style={{ fontWeight: 500 }}>{passDisplayName(rec.pass)}</td>
                <td><code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-cyan)' }}>{passAbbr(rec.pass)}</code></td>
                <td>
                  <div className="conf-bar-wrap">
                    <div className="conf-bar" style={{ maxWidth: 100 }}>
                      <div
                        className="conf-bar-fill"
                        style={{
                          width: `${Math.round(rec.confidence * 100)}%`,
                          background: rec.recommended ? 'var(--accent-green)' : 'var(--border-strong)',
                        }}
                      />
                    </div>
                    <span className="conf-pct">{Math.round(rec.confidence * 100)}%</span>
                  </div>
                </td>
                <td>
                  {rec.recommended
                    ? <span className="header-badge badge-green"><CheckCircle2 size={9} /> Recommended</span>
                    : <span className="header-badge badge-surface">Skipped (below 50%)</span>
                  }
                </td>
                <td>
                  {rec.applied
                    ? <span className="header-badge badge-green">✓ Applied</span>
                    : <span className="header-badge badge-surface">Not Applied</span>
                  }
                </td>
                <td>
                  <span className="header-badge badge-blue">ESTIMATED</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── ML Advisor Tab ───────────────────────────────────────────────────────────
function MLTab({
  result,
  modelInfo,
  onApplyCode,
}: {
  result: PipelineResponse | null;
  modelInfo: ModelInfoResponse | null;
  onApplyCode?: (code: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'c' | 'tac'>('c');

  if (!result?.success || !result.ml) {
    return (
      <div className="empty-state">
        <Brain size={36} style={{ opacity: 0.3 }} />
        <div className="empty-state-title">Run the Pipeline First</div>
        <div className="empty-state-sub">ML features and recommendations will appear here.</div>
      </div>
    );
  }

  const { features, recommendations } = result.ml;
  const optimizedC = result.phases?.optimized_c_code || result.phases?.optimized_code || '';
  const tacAfter = result.phases?.tac_after || [];
  const optimizedTacText = result.phases?.optimized_tac || result.phases?.tac_after_text || formatTACLines(tacAfter).join('\n');
  const currentCode = viewMode === 'c' ? optimizedC : optimizedTacText;

  const handleCopy = () => {
    if (!currentCode) return;
    navigator.clipboard.writeText(currentCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="panel-fill">
      {/* ── ✨ Suggested Optimized Code Card ── */}
      <div className="card" style={{ border: '1px solid rgba(59, 130, 246, 0.35)', background: 'var(--bg-surface)' }}>
        <div className="card-header" style={{ background: 'rgba(59, 130, 246, 0.08)', flexWrap: 'wrap', gap: 8 }}>
          <span className="card-title" style={{ color: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={14} /> Suggested Optimized Code (ML Output)
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'inline-flex', background: 'var(--bg-base)', borderRadius: 4, padding: 2, border: '1px solid var(--border-subtle)' }}>
              <button
                className={`btn btn-sm ${viewMode === 'c' ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setViewMode('c')}
                style={{ fontSize: 11, padding: '2px 8px', borderRadius: 3 }}
              >
                Suggested C Code
              </button>
              <button
                className={`btn btn-sm ${viewMode === 'tac' ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setViewMode('tac')}
                style={{ fontSize: 11, padding: '2px 8px', borderRadius: 3 }}
              >
                Optimized TAC
              </button>
            </div>
            {currentCode && (
              <>
                <button className="btn btn-ghost btn-sm" onClick={handleCopy} style={{ fontSize: 11, gap: 4 }}>
                  {copied ? <Check size={12} color="var(--accent-green)" /> : <Copy size={12} />}
                  {copied ? 'Copied!' : 'Copy Code'}
                </button>
                {onApplyCode && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => onApplyCode(currentCode)}
                    style={{ fontSize: 11, gap: 4, background: 'var(--accent-blue)' }}
                    title={viewMode === 'c' ? 'Apply optimized C source code to editor' : 'Apply optimized TAC to editor'}
                  >
                    {viewMode === 'c' ? 'Apply to Editor' : 'Apply TAC to Editor'}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
        <div style={{ padding: 14, background: 'var(--bg-base)', minHeight: 120, maxHeight: 300, overflowY: 'auto' }}>
          {viewMode === 'c' ? (
            <pre
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12.5,
                lineHeight: 1.6,
                color: '#a5b4fc',
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {optimizedC || '// Run pipeline to generate suggested optimized C code'}
            </pre>
          ) : (
            <TacViewer instructions={tacAfter} label="Optimized TAC Instructions" />
          )}
        </div>
      </div>

      {/* Model info bar */}
      <div className="card">
        <div className="card-header">
          <span className="card-title"><Cpu size={13} /> Trained ML Model Info</span>
          <span className="header-badge badge-green">RandomForest · Multi-label</span>
        </div>
        <div style={{ padding: '10px 16px', display: 'flex', gap: 32, flexWrap: 'wrap', fontSize: 12 }}>
          {[
            ['Architecture', 'MultiOutputClassifier(RandomForest)'],
            ['Training Programs', String(modelInfo?.training_samples ?? 480)],
            ['Test Programs', '120 (never seen in training)'],
            ['Confidence Threshold', '0.50 (50%)'],
            ['Hamming Loss', String(modelInfo?.metrics?.hamming_loss ?? '0.0217')],
            ['Exact Match Ratio', String(modelInfo?.metrics?.exact_match_ratio ?? '0.90')],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{k}</span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 15 Features grid */}
      <div className="card">
        <div className="card-header">
          <span className="card-title"><Table2 size={13} /> Extracted Structural Features (15)</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Source: AST + TAC · No data leakage</span>
        </div>
        <div style={{ padding: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))', gap: 8 }}>
          {features && Object.entries(features).map(([key, val], idx) => (
            <div key={key} className="feature-chip">
              <span className="feature-chip-name">F{idx + 1}: {FEATURE_LABELS[key] ?? key}</span>
              <span className="feature-chip-val">{val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Pass explanations */}
      <div className="card">
        <div className="card-header">
          <span className="card-title"><Brain size={13} /> Pass Explanations & Reasoning</span>
          <span className="header-badge badge-blue">ESTIMATED</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {recommendations?.map((rec) => (
            <div key={rec.pass} className={`exp-card ${rec.applied ? 'applied' : 'skipped'}`} style={{ margin: '0 12px 8px', borderRadius: 'var(--radius-sm)' }}>
              <div className="exp-card-header">
                <span style={{ fontWeight: 600, fontSize: 12.5, color: 'var(--text-primary)', flex: 1 }}>
                  {passDisplayName(rec.pass)}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', marginRight: 8 }}>
                  {Math.round(rec.confidence * 100)}% confidence
                </span>
                {rec.applied
                  ? <span className="header-badge badge-green"><CheckCircle2 size={9} /> Applied</span>
                  : <span className="header-badge badge-surface"><XCircle size={9} /> Skipped</span>
                }
              </div>
              <div className="exp-card-body">{rec.explanation}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── TAC Comparison Tab ───────────────────────────────────────────────────────
function TACTab({ result }: { result: PipelineResponse | null }) {
  if (!result?.success || !result.phases) {
    return (
      <div className="empty-state">
        <ArrowLeftRight size={36} style={{ opacity: 0.3 }} />
        <div className="empty-state-title">No TAC Available</div>
        <div className="empty-state-sub">Run the pipeline to see the before/after TAC comparison.</div>
      </div>
    );
  }

  const { tac_before = [], tac_after = [] } = result.phases;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', height: '100%', overflow: 'hidden' }}>
      <div style={{ borderRight: '1px solid var(--border-subtle)', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <TacViewer instructions={tac_before} label="Unoptimized TAC (Before)" />
      </div>
      <div style={{ overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <TacViewer instructions={tac_after} label="Optimized TAC (After) · MEASURED" />
      </div>
    </div>
  );
}

// ─── AST + Symbol Table Tab ───────────────────────────────────────────────────
function ASTTab({ result }: { result: PipelineResponse | null }) {
  if (!result?.phases) {
    return (
      <div className="empty-state">
        <GitBranch size={36} style={{ opacity: 0.3 }} />
        <div className="empty-state-title">No AST Available</div>
        <div className="empty-state-sub">Run the pipeline to view the abstract syntax tree and symbol table.</div>
      </div>
    );
  }

  const { ast, symbol_table = [], semantic_errors = [] } = result.phases;

  return (
    <div className="panel-fill">
      {/* Symbol Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title"><Table2 size={13} /> Symbol Table</span>
          <span className="header-badge badge-surface">{symbol_table.length} symbols</span>
        </div>
        <div style={{ overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Identifier</th>
                <th>Category</th>
                <th>Type</th>
                <th>Value</th>
                <th>Scope</th>
                <th>Function</th>
                <th>Line</th>
              </tr>
            </thead>
            <tbody>
              {symbol_table.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>No symbols declared.</td></tr>
              ) : symbol_table.map((sym, i) => (
                <tr key={i}>
                  <td><code className="mono">{sym.name}</code></td>
                  <td>
                    <span className={`header-badge ${(sym.category || (sym as any).kind) === 'function' ? 'badge-purple' : 'badge-surface'}`}>
                      {sym.category || (sym as any).kind || 'variable'}
                    </span>
                  </td>
                  <td><code className="mono">{sym.type}</code></td>
                  <td><code className="mono" style={{ color: '#a5b4fc' }}>{(sym as any).value ?? '—'}</code></td>
                  <td style={{ color: 'var(--text-secondary)' }}>Level {sym.scope_level}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{sym.enclosing_function ?? 'global'}</td>
                  <td style={{ color: 'var(--text-tertiary)' }}>L{sym.line}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Semantic Errors (if any) */}
      {semantic_errors.length > 0 && (
        <div className="card" style={{ border: '1px solid rgba(239,68,68,0.3)' }}>
          <div className="card-header">
            <span className="card-title" style={{ color: 'var(--accent-red)' }}>
              <AlertTriangle size={13} /> Semantic Errors ({semantic_errors.length})
            </span>
          </div>
          <div style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {semantic_errors.map((err, i) => (
              <div key={i} style={{ fontSize: 12, color: '#fca5a5', fontFamily: 'var(--font-mono)' }}>
                {(err as any).line ? `[L${(err as any).line}] ` : ''}{(err as any).message ?? String(err)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AST Tree */}
      <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="card-header">
          <span className="card-title"><GitBranch size={13} /> Abstract Syntax Tree</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Top-down graphical AST diagram • Pan, zoom & click to inspect</span>
        </div>
        <div style={{ padding: 12, flex: 1 }}>
          <AstViewer ast={ast as Record<string, unknown> ?? null} />
        </div>
      </div>
    </div>
  );
}

// ─── Tokens Tab ───────────────────────────────────────────────────────────────
function TokensTab({ result }: { result: PipelineResponse | null }) {
  const tokens = result?.phases?.tokens ?? (result as any)?.tokens ?? [];

  if (tokens.length === 0) {
    return (
      <div className="empty-state">
        <ListOrdered size={36} style={{ opacity: 0.3 }} />
        <div className="empty-state-title">No Tokens Available</div>
        <div className="empty-state-sub">Click "Tokenize Only" or run the full pipeline.</div>
      </div>
    );
  }

  const TOKEN_COLORS: Record<string, string> = {
    INT: 'badge-purple', FLOAT: 'badge-purple', IDENTIFIER: 'badge-cyan', INTEGER_LITERAL: 'badge-amber',
    FLOAT_LITERAL: 'badge-amber', IF: 'badge-blue', ELSE: 'badge-blue', WHILE: 'badge-blue',
    FOR: 'badge-blue', RETURN: 'badge-blue', PLUS: 'badge-surface', MINUS: 'badge-surface',
    TIMES: 'badge-surface', DIVIDE: 'badge-surface', ASSIGN: 'badge-surface',
  };

  return (
    <div className="panel-fill">
      <div className="card" style={{ flex: 1 }}>
        <div className="card-header">
          <span className="card-title"><ListOrdered size={13} /> Token Stream</span>
          <span className="header-badge badge-surface">{tokens.length} tokens</span>
        </div>
        <div style={{ overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Token Type</th>
                <th>Lexeme</th>
                <th>Line</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((tok: { type: string; value: string; line: number }, i: number) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-tertiary)', width: 48 }}>{i + 1}</td>
                  <td>
                    <span className={`header-badge ${TOKEN_COLORS[tok.type] ?? 'badge-surface'}`}>
                      {tok.type}
                    </span>
                  </td>
                  <td><code className="mono">{tok.value}</code></td>
                  <td style={{ color: 'var(--text-tertiary)' }}>L{tok.line}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
