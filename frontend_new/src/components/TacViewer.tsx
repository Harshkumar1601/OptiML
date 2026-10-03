import { formatTACLines } from '../utils';

interface TacViewerProps {
  instructions: unknown[];
  label: string;
  headerClass?: string;
}

export function TacViewer({ instructions, label, headerClass = '' }: TacViewerProps) {
  const lines = formatTACLines(instructions);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '8px 14px',
          fontSize: 11,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'var(--bg-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
        className={headerClass}
      >
        <span>{label}</span>
        <span style={{ color: 'var(--text-tertiary)' }}>{lines.length} instructions</span>
      </div>
      <div className="code-view" style={{ flex: 1 }}>
        {lines.length === 0 ? (
          <div style={{ padding: 16, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 12.5 }}>
            // No instructions
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="code-line">
              <span className="line-num">{i + 1}</span>
              <span className="line-content">{line}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
