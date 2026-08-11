'use client';

interface Warning {
  title: string;
  severity?: number;
  region?: string;
  area?: string;
}

interface WeatherWarningsCardProps {
  riskData?: { warnings?: Warning[]; detail?: string };
}

function severityColor(sev: number): string {
  if (sev >= 80) return '#ef4444';
  if (sev >= 50) return '#f97316';
  return '#eab308';
}

export default function WeatherWarningsCard({ riskData }: WeatherWarningsCardProps) {
  const warnings = riskData?.warnings || [];

  if (warnings.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0' }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 10px #22c55e', flexShrink: 0 }} />
        <div style={{ fontSize: 13, fontWeight: 600, color: '#22c55e' }}>Keine Wetterwarnungen aktiv</div>
      </div>
    );
  }

  return (
    <>
      {warnings.slice(0, 5).map((w, i) => {
        const sev = w.severity ?? 0;
        const color = severityColor(sev);
        return (
          <div
            key={i}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0',
              borderBottom: i < Math.min(warnings.length, 5) - 1 ? '1px solid #1e1e1e' : 'none',
            }}
          >
            <div
              className="pulse-dot"
              style={{ width: 10, height: 10, borderRadius: '50%', background: color, boxShadow: `0 0 10px ${color}`, flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {w.title}
              </div>
              <div className="mono" style={{ fontSize: 11, color: '#666' }}>
                {w.region || w.area || 'Rhein-Sieg-Kreis'}
              </div>
            </div>
            <div className="mono" style={{ fontSize: 17, fontWeight: 700, color }}>{Math.round(sev)}</div>
          </div>
        );
      })}
    </>
  );
}
