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
  if (score < 20) return 'Normal';
  if (score < 40) return 'Erhöht';
  if (score < 60) return 'Hoch';
  if (score < 80) return 'Sehr Hoch';
  return 'Extrem';
}

export default function RiskGauge({ score, size = 'lg', label }: RiskGaugeProps) {
  const dims = { sm: 100, md: 160, lg: 240 }[size];
  const strokeWidth = { sm: 8, md: 12, lg: 16 }[size];
  const radius = (dims - strokeWidth) / 2;
  const circumference = Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = getScoreColor(score);
  const textSize = { sm: 'text-lg', md: 'text-3xl', lg: 'text-5xl' }[size];
  const labelSize = { sm: 'text-xs', md: 'text-sm', lg: 'text-base' }[size];

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: dims, height: dims / 2 + 20 }}>
        <svg width={dims} height={dims / 2 + 20} viewBox={`0 0 ${dims} ${dims / 2 + 20}`}>
          <path
            d={`M ${strokeWidth / 2} ${dims / 2} A ${radius} ${radius} 0 0 1 ${dims - strokeWidth / 2} ${dims / 2}`}
            fill="none"
            stroke="#333"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          <path
            d={`M ${strokeWidth / 2} ${dims / 2} A ${radius} ${radius} 0 0 1 ${dims - strokeWidth / 2} ${dims / 2}`}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
            style={{ filter: `drop-shadow(0 0 8px ${color}40)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className={`${textSize} font-bold`} style={{ color }}>
            {Math.round(score)}
          </span>
          <span className={`${labelSize} text-dark-400`}>
            {label || getScoreLabel(score)}
          </span>
        </div>
      </div>
    </div>
  );
}
