'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface FireDangerCardProps {
  riskData?: { score?: number; detail?: string };
}

const LEVEL_META = [
  { color: '#22c55e', label: 'Sehr gering' },
  { color: '#eab308', label: 'Gering' },
  { color: '#f97316', label: 'Mittel' },
  { color: '#ef4444', label: 'Hoch' },
  { color: '#a855f7', label: 'Sehr hoch' },
];

export default function FireDangerCard({ riskData }: FireDangerCardProps) {
  const [dwdIndex, setDwdIndex] = useState<number | null>(null);

  useEffect(() => {
    apiFetch<any>('/api/dashboard/fire')
      .then((d) => {
        const risks = d?.risks || [];
        // Neuester Eintrag der offiziellen DWD-WBI-Quelle (nicht Satellit)
        const dwd = risks.find((r: any) => r.source === 'dwd_fire_index' && r.risk_index != null);
        if (dwd) {
          setDwdIndex(Math.min(5, Math.max(1, Math.round(dwd.risk_index))));
        }
      })
      .catch(() => {});
  }, []);

  const score = riskData?.score ?? 0;
  // DWD-Index bevorzugt; sonst Stufe aus dem Risiko-Score ableiten
  const level = dwdIndex ?? Math.min(5, Math.max(1, Math.ceil(score / 20) || 1));
  const meta = LEVEL_META[level - 1];

  return (
    <>
      <div style={{ display: 'flex', gap: 6 }}>
        {LEVEL_META.map((m, i) => {
          const active = i < level;
          const isTop = i === level - 1;
          return (
            <div
              key={i}
              className={`seg ${active ? (isTop ? 'pulse-dot' : '') : 'seg-off'}`}
              style={active ? { background: m.color, boxShadow: `0 0 18px ${m.color}55` } : undefined}
            />
          );
        })}
      </div>
      <div className="seg-labels mono">
        <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span>
      </div>
      <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #252525' }}>
        <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>
          {riskData?.detail || 'Wahner Heide · DWD-Index'}
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: meta.color }}>
          Stufe {level} · {meta.label}
        </div>
      </div>
    </>
  );
}
