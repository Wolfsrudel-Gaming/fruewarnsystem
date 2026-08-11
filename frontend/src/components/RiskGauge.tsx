'use client';

interface RiskGaugeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

function getScoreColor(score: number): string {
  if (score < 20) return '#22c55e';
  if (score < 40) return '#eab308';
  if (score < 60) return '#f97316';
  if (score < 80) return '#ef4444';
  return '#a855f7';
}

function getScoreLabel(score: number): string {
  if (score < 20) return 'NORMAL';
  if (score < 40) return 'ERHÖHT';
  if (score < 60) return 'HOCH';
  if (score < 80) return 'SEHR HOCH';
  return 'EXTREM';
}

export default function RiskGauge({ score, size = 'lg', label }: RiskGaugeProps) {
  const scale = { sm: 0.6, md: 0.8, lg: 1 }[size];
  const width = 200 * scale;
  const height = 120 * scale;
  const color = getScoreColor(score);
  const circumference = Math.PI * 80;
  const progress = (Math.min(100, Math.max(0, score)) / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={width} height={height} viewBox="0 0 200 120">
        <path
          d="M 12 100 A 80 80 0 0 1 188 100"
          fill="none"
          stroke="#1e1e1e"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d="M 12 100 A 80 80 0 0 1 188 100"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${progress.toFixed(1)} ${circumference.toFixed(1)}`}
          style={{
            filter: `drop-shadow(0 0 12px ${color})`,
            transition: 'stroke-dasharray 1.5s cubic-bezier(.4,0,.2,1), stroke .8s ease',
          }}
        />
        <text
          className="mono"
          x="100"
          y="88"
          textAnchor="middle"
          fill={color}
          style={{ fontSize: 44, fontWeight: 800 }}
        >
          {Math.round(score)}
        </text>
      </svg>
      <div style={{ fontSize: 14, fontWeight: 700, marginTop: 16, letterSpacing: '1.5px', color }}>
        {label || getScoreLabel(score)}
      </div>
    </div>
  );
}
