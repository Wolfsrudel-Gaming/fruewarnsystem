'use client';

interface CategoryCardProps {
  title: string;
  icon: string;
  score: number;
  detail?: string;
  onClick?: () => void;
}

function getScoreColor(score: number): string {
  if (score < 20) return '#22c55e';
  if (score < 40) return '#eab308';
  if (score < 60) return '#f97316';
  if (score < 80) return '#ef4444';
  return '#a855f7';
}

function hexToRgb(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

export default function CategoryCard({ title, icon, score, detail, onClick }: CategoryCardProps) {
  const color = getScoreColor(score);
  const rgb = hexToRgb(color);

  return (
    <button
      onClick={onClick}
      className={`cat-card w-full ${score >= 60 ? 'glow' : ''}`}
      style={{ background: `rgba(${rgb},.08)`, border: `1px solid rgba(${rgb},.25)` }}
      title={detail}
    >
      <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div>
      <div className="mono" style={{ fontSize: 29, fontWeight: 700, color, marginBottom: 6 }}>
        {Math.round(score)}
      </div>
      <div className="track" style={{ height: 4, marginBottom: 9 }}>
        <div
          style={{
            height: '100%',
            width: `${Math.min(100, Math.max(0, score))}%`,
            background: color,
            borderRadius: 2,
            transition: 'width 1s ease',
          }}
        />
      </div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#ccc' }}>{title}</div>
    </button>
  );
}
