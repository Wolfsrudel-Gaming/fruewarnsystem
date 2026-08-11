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
  seismic: '🌍',
  radiation: '☢️',
  health: '🏥',
};

function scoreColor(score: number): string {
  if (score >= 70) return '#ef4444';
  if (score >= 40) return '#f97316';
  return '#eab308';
}

export default function AlertList({ alerts, onAcknowledge }: AlertListProps) {
  if (alerts.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0' }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 10px #22c55e', flexShrink: 0 }} />
        <div style={{ fontSize: 13, fontWeight: 600, color: '#22c55e' }}>Keine aktiven Alarme</div>
      </div>
    );
  }

  const handleAck = async (id: number) => {
    await apiFetch(`/api/dashboard/alerts/${id}/acknowledge`, { method: 'POST' });
    onAcknowledge?.(id);
  };

  return (
    <div>
      {alerts.map((alert, i) => {
        const color = scoreColor(alert.score);
        return (
          <div
            key={alert.id}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 14, padding: '14px 0',
              borderBottom: i < alerts.length - 1 ? '1px solid #1e1e1e' : 'none',
            }}
          >
            <span style={{ fontSize: 22, lineHeight: 1.2 }}>
              {categoryIcons[alert.category] || '⚠️'}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {alert.title}
                </span>
                <span
                  className="mono"
                  style={{
                    flexShrink: 0, fontSize: 12, fontWeight: 700, color,
                    background: `${color}22`, padding: '1px 8px', borderRadius: 6,
                  }}
                >
                  {Math.round(alert.score)}
                </span>
              </div>
              <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>{alert.description}</p>
              <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 11, color: '#555' }}>
                <span>
                  {new Date(alert.triggered_at).toLocaleString('de-DE', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                  })}
                </span>
                <span>Eskalation {alert.escalation_level}</span>
                {!alert.acknowledged ? (
                  <button
                    onClick={() => handleAck(alert.id)}
                    style={{
                      padding: '2px 10px', background: '#e81e1e', color: '#fff',
                      borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600,
                    }}
                  >
                    Quittieren
                  </button>
                ) : (
                  <span style={{ color: '#22c55e' }}>✓ Quittiert</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
