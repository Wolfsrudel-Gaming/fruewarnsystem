'use client';

interface CategoryCardProps {
  title: string;
  icon: string;
  score: number;
  detail: string;
  onClick?: () => void;
}

function getScoreColor(score: number): string {
  if (score < 20) return 'text-green-400';
  if (score < 40) return 'text-yellow-400';
  if (score < 60) return 'text-orange-400';
  if (score < 80) return 'text-red-400';
  return 'text-purple-400';
}

function getScoreBg(score: number): string {
  if (score < 20) return 'bg-green-500/10 border-green-500/30';
  if (score < 40) return 'bg-yellow-500/10 border-yellow-500/30';
  if (score < 60) return 'bg-orange-500/10 border-orange-500/30';
  if (score < 80) return 'bg-red-500/10 border-red-500/30';
  return 'bg-purple-500/10 border-purple-500/30';
}

function getScoreBar(score: number): string {
  if (score < 20) return 'bg-green-500';
  if (score < 40) return 'bg-yellow-500';
  if (score < 60) return 'bg-orange-500';
  if (score < 80) return 'bg-red-500';
  return 'bg-purple-500';
}

export default function CategoryCard({ title, icon, score, detail, onClick }: CategoryCardProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full p-4 rounded-lg border transition-all hover:scale-[1.02] ${getScoreBg(score)} ${score >= 70 ? 'alert-glow' : ''}`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <span className="font-medium text-dark-200">{title}</span>
        </div>
        <span className={`text-2xl font-bold ${getScoreColor(score)}`}>
          {Math.round(score)}
        </span>
      </div>
      <div className="w-full bg-dark-800 rounded-full h-2 mb-2">
        <div
          className={`h-2 rounded-full transition-all duration-1000 ${getScoreBar(score)}`}
          style={{ width: `${Math.min(100, score)}%` }}
        />
      </div>
      <p className="text-xs text-dark-400 text-left">{detail}</p>
    </button>
  );
}
