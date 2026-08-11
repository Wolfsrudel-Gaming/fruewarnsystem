'use client';

import { apiFetch } from '@/lib/api';

interface Alert {
  id: number;
  category: string;
  score: number;
  title: string;
  description: string;
  escalation_level: number;
  acknowledged: boolean;
  triggered_at: string;
}

interface AlertListProps {
  alerts: Alert[];
  onAcknowledge?: (id: number) => void;
}

const categoryIcons: Record<string, string> = {
  water: '🌊',
  weather: '⛈️',
  fire: '🔥',
  traffic: '🚗',
  manv: '🚑',
  air_quality: '💨',
  news: '📰',
  official_warning: '⚠️',
};

export default function AlertList({ alerts, onAcknowledge }: AlertListProps) {
  if (alerts.length === 0) {
    return (
      <div className="card text-center text-dark-400 py-8">
        Keine aktiven Alarme
      </div>
    );
  }

  const handleAck = async (id: number) => {
    await apiFetch(`/api/dashboard/alerts/${id}/acknowledge`, { method: 'POST' });
    onAcknowledge?.(id);
  };

  return (
    <div className="space-y-2">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={`card flex items-start gap-3 ${alert.score >= 70 ? 'alert-glow border-red-500/50' : ''}`}
        >
          <span className="text-2xl mt-0.5">
            {categoryIcons[alert.category] || '⚠️'}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-medium text-sm truncate">{alert.title}</h4>
              <span className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-bold ${
                alert.score >= 70 ? 'bg-red-500/20 text-red-400' :
                alert.score >= 40 ? 'bg-orange-500/20 text-orange-400' :
                'bg-yellow-500/20 text-yellow-400'
              }`}>
                {Math.round(alert.score)}
              </span>
            </div>
            <p className="text-xs text-dark-400 mb-2">{alert.description}</p>
            <div className="flex items-center gap-3 text-xs text-dark-500">
              <span>
                {new Date(alert.triggered_at).toLocaleString('de-DE', {
                  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                })}
              </span>
              <span>Eskalation: {alert.escalation_level}</span>
              {!alert.acknowledged && (
                <button
                  onClick={() => handleAck(alert.id)}
                  className="px-2 py-0.5 bg-drk-600 hover:bg-drk-500 rounded text-white transition-colors"
                >
                  Quittieren
                </button>
              )}
              {alert.acknowledged && (
                <span className="text-green-500">✓ Quittiert</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
