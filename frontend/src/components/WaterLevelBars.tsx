'use client';

interface Station {
  station: string;
  river: string;
  level: number | null;
  trend?: string;
  condition?: string;
  warning_level?: string;
  score?: number;
}

interface WaterLevelBarsProps {
  stations: Station[];
}

// Spiegelt RIVER_THRESHOLDS aus backend/app/collectors/water/pegel_collector.py
const RIVER_THRESHOLDS: Record<string, { lowExtreme: number; lowWarn: number; lowNormal: number; normal: number; warn: number; max: number }> = {
  rhein:     { lowExtreme: 80, lowWarn: 150, lowNormal: 200, normal: 600, warn: 700, max: 850 },
  sieg:      { lowExtreme: 15, lowWarn: 30,  lowNormal: 50,  normal: 300, warn: 400, max: 500 },
  agger:     { lowExtreme: 10, lowWarn: 20,  lowNormal: 35,  normal: 200, warn: 280, max: 350 },
  pleisbach: { lowExtreme: 5,  lowWarn: 10,  lowNormal: 20,  normal: 100, warn: 150, max: 200 },
  swistbach: { lowExtreme: 5,  lowWarn: 10,  lowNormal: 20,  normal: 80,  warn: 120, max: 160 },
};

interface Classification {
  key: string;
  text: string;
  color: string;
  side: 'low' | 'mid' | 'high';
}

// Klassifikation 1:1 nach classify_water_level() im Backend
function classify(level: number, t: (typeof RIVER_THRESHOLDS)['rhein']): Classification {
  if (level <= t.lowExtreme) return { key: 'drought',       text: 'Trockenheit',           color: '#92400e', side: 'low' };
  if (level <= t.lowWarn)    return { key: 'niedrigwasser', text: 'Niedrigwasser',         color: '#d97706', side: 'low' };
  if (level <= t.lowNormal)  return { key: 'below_normal',  text: 'Unterdurchschnittlich', color: '#64748b', side: 'low' };
  if (level <= t.normal)     return { key: 'normal',        text: 'Normal',                color: '#3b82f6', side: 'mid' };
  if (level <= t.warn)       return { key: 'hochwasser',    text: 'Hochwasser',            color: '#f97316', side: 'high' };
  if (level <= t.max)        return { key: 'starkes',       text: 'Starkes Hochwasser',    color: '#ef4444', side: 'high' };
  return                            { key: 'extrem',        text: 'Extremhochwasser',      color: '#a855f7', side: 'high' };
}

function thresholdsFor(river: string) {
  const key = Object.keys(RIVER_THRESHOLDS).find(k => river.toLowerCase().includes(k));
  return RIVER_THRESHOLDS[key || 'sieg'];
}

const WAVE_PATH =
  'M0 6Q25 0 50 6Q75 12 100 6Q125 0 150 6Q175 12 200 6Q225 0 250 6Q275 12 300 6Q325 0 350 6Q375 12 400 6Q425 0 450 6Q475 12 500 6Q525 0 550 6Q575 12 600 6';

const LEGEND = [
  { color: '#92400e', label: 'Trockenheit' },
  { color: '#d97706', label: 'Niedrigwasser' },
  { color: '#64748b', label: 'Unterdurchschnittlich' },
  { color: '#3b82f6', label: 'Normal' },
  { color: '#f97316', label: 'Hochwasser' },
  { color: '#ef4444', label: 'Starkes Hochwasser' },
  { color: '#a855f7', label: 'Extremhochwasser' },
];

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

export default function WaterLevelBars({ stations }: WaterLevelBarsProps) {
  // API kann dieselbe Station mehrfach liefern (mehrere Messzeitpunkte) — erste = neueste behalten.
  const unique: Station[] = [];
  const seen = new Set<string>();
  for (const s of stations || []) {
    const key = `${s.station}|${s.river}`;
    if (!seen.has(key) && s.level != null) {
      seen.add(key);
      unique.push(s);
    }
  }

  if (unique.length === 0) {
    return <p style={{ color: '#666', fontSize: 13 }}>Keine Pegeldaten verfügbar</p>;
  }

  return (
    <>
      <div className="bars">
        {unique.slice(0, 6).map((s) => {
          const t = thresholdsFor(s.river || '');
          const level = s.level as number;
          const c = classify(level, t);
          const denom = t.max * 1.1;
          const pct = Math.min(94, Math.max(6, (level / denom) * 100));
          const marks = [t.max, t.warn, t.normal, t.lowWarn];
          const markColors = ['#a855f7', '#ef4444', '#f97316', '#d97706'];
          const markOpacity = [0.45, 0.45, 0.4, 0.5];
          const glowClass =
            c.key === 'starkes' || c.key === 'extrem' ? 'glow'
            : c.key === 'drought' || c.key === 'niedrigwasser' ? 'glow-low'
            : '';
          const rising = s.trend === 'rising';
          const falling = s.trend === 'falling';
          const arrow = rising ? '▲' : falling ? '▼' : '■';
          const worse = (c.side === 'low' && falling) || (c.side === 'high' && rising);
          const better = (c.side === 'low' && rising) || (c.side === 'high' && falling);
          const trendColor = worse ? '#ef4444' : better ? '#22c55e' : '#777';
          // Wellengeschwindigkeit steigt mit dem Füllstand
          const waveDuration = Math.max(1.5, 3 - (pct / 100) * 1.5);

          return (
            <div className="bar" key={`${s.station}|${s.river}`}>
              <div className={`tube ${glowClass}`}>
                {marks.map((m, i) => (
                  <div
                    key={i}
                    className="tube-mark"
                    style={{
                      bottom: `${((m / denom) * 100).toFixed(1)}%`,
                      background: markColors[i],
                      opacity: markOpacity[i],
                    }}
                  />
                ))}
                <div
                  className="tube-fill"
                  style={{
                    height: `${pct.toFixed(1)}%`,
                    background: `linear-gradient(to top, ${c.color}ee, ${c.color}77)`,
                    boxShadow: `0 -4px 22px ${c.color}55`,
                  }}
                >
                  <div className="tube-wave">
                    <svg viewBox="0 0 600 12" preserveAspectRatio="none" style={{ animationDuration: `${waveDuration.toFixed(2)}s` }}>
                      <path d={WAVE_PATH} fill="none" stroke={c.color} strokeWidth="2.5" opacity=".7" />
                    </svg>
                  </div>
                </div>
                <div className="tube-val">
                  <div className="tube-num mono">{Math.round(level)}</div>
                  <div className="tube-unit mono">cm</div>
                </div>
              </div>
              <div className="bar-cond" style={{ color: c.color }}>{c.text}</div>
              <div className="bar-trend" style={{ color: trendColor }}>{arrow}</div>
              <div className="bar-sname">{titleCase(s.station || '')}</div>
              <div className="bar-sriver mono">{s.river}</div>
            </div>
          );
        })}
      </div>

      <div className="bars-legend">
        {LEGEND.map((l) => (
          <span key={l.label}>
            <i className="legend-dot" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
    </>
  );
}
