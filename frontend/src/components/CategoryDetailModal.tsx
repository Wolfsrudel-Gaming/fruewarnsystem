'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface CategoryInfo {
  key: string;
  title: string;
  icon: string;
}

interface CategoryDetailModalProps {
  category: CategoryInfo;
  riskData: any;
  onClose: () => void;
}

function scoreColor(score: number): string {
  if (score < 20) return '#22c55e';
  if (score < 40) return '#eab308';
  if (score < 60) return '#f97316';
  if (score < 80) return '#ef4444';
  return '#a855f7';
}

const ESCALATION_LABELS: Record<string, string> = {
  none: 'keine',
  low: 'niedrig',
  medium: 'mittel',
  high: 'hoch',
  critical: 'kritisch',
};

export default function CategoryDetailModal({ category, riskData, onClose }: CategoryDetailModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.75)',
        backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card"
        style={{
          width: '100%', maxWidth: 780, maxHeight: '85vh', display: 'flex',
          flexDirection: 'column', padding: 0, animation: 'slideIn .3s ease-out',
        }}
      >
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '20px 28px',
            borderBottom: '1px solid #252525', flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 24 }}>{category.icon}</span>
          <div style={{ flex: 1 }}>
            <div className="lbl">{category.title}</div>
            {riskData?.detail && (
              <div style={{ fontSize: 13, color: '#aaa', marginTop: 4 }}>{riskData.detail}</div>
            )}
          </div>
          {riskData?.score != null && (
            <span
              className="mono"
              style={{
                fontSize: 20, fontWeight: 700, color: scoreColor(riskData.score),
                background: `${scoreColor(riskData.score)}18`, padding: '4px 14px', borderRadius: 10,
              }}
            >
              {Math.round(riskData.score)}
            </span>
          )}
          <button
            onClick={onClose}
            aria-label="Schließen"
            style={{
              background: '#252525', border: 'none', color: '#aaa', width: 32, height: 32,
              borderRadius: 8, cursor: 'pointer', fontSize: 16, lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ overflowY: 'auto', padding: '20px 28px 28px' }}>
          {category.key === 'news'
            ? <NewsDetail />
            : <ContributionsDetail contributions={riskData?.contributions || []} />}
        </div>
      </div>
    </div>
  );
}

/* ---------- News: relevante und herausgefilterte Meldungen mit Begründung ---------- */

interface NewsItem {
  id: number;
  title: string;
  summary?: string;
  url?: string;
  source?: string;
  category?: string;
  relevance_score?: number;
  is_relevant?: boolean;
  ai_analysis?: {
    drk_relevance?: string;
    escalation_potential?: string;
    expected_actions?: string[];
    affected_area?: string;
    confidence?: number;
    relevance_score?: number;
  } | null;
  published_at?: string;
  created_at?: string;
}

function NewsDetail() {
  const [items, setItems] = useState<NewsItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiFetch<{ items: NewsItem[] }>('/api/dashboard/news?relevant_only=false&limit=100')
      .then((d) => setItems(d.items || []))
      .catch(() => setError(true));
  }, []);

  if (error) return <p style={{ color: '#ef4444', fontSize: 13 }}>Nachrichten konnten nicht geladen werden.</p>;
  if (!items) return <p style={{ color: '#666', fontSize: 13 }}>Lade Nachrichten…</p>;
  if (items.length === 0) return <p style={{ color: '#666', fontSize: 13 }}>Keine Nachrichten in der Datenbank.</p>;

  const relevant = items.filter((n) => n.is_relevant);
  const filtered = items.filter((n) => !n.is_relevant);

  return (
    <>
      <SectionLabel color="#ef4444">
        Als relevant eingestuft ({relevant.length})
      </SectionLabel>
      {relevant.length === 0 && (
        <p style={{ color: '#666', fontSize: 13, marginBottom: 20 }}>Derzeit keine relevanten Meldungen.</p>
      )}
      {relevant.map((n) => <NewsRow key={n.id} item={n} />)}

      <SectionLabel color="#64748b" style={{ marginTop: 28 }}>
        Herausgefiltert ({filtered.length})
      </SectionLabel>
      {filtered.length === 0 && (
        <p style={{ color: '#666', fontSize: 13 }}>Keine herausgefilterten Meldungen.</p>
      )}
      {filtered.map((n) => <NewsRow key={n.id} item={n} />)}
    </>
  );
}

function SectionLabel({ children, color, style }: { children: React.ReactNode; color: string; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase',
        color, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, ...style,
      }}
    >
      <span className="legend-dot" style={{ background: color }} />
      {children}
    </div>
  );
}

function NewsRow({ item }: { item: NewsItem }) {
  const [open, setOpen] = useState(false);
  const score = item.relevance_score ?? 0;
  const pct = Math.round(score * 100);
  const color = item.is_relevant ? (score >= 0.6 ? '#ef4444' : '#f97316') : '#64748b';
  const ai = item.ai_analysis;
  const date = item.published_at || item.created_at;

  return (
    <div style={{ borderBottom: '1px solid #1e1e1e', padding: '12px 0' }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer' }}
      >
        <span
          className="mono"
          title="Relevanz-Score (Schwelle: 30)"
          style={{
            flexShrink: 0, fontSize: 13, fontWeight: 700, color,
            background: `${color}22`, padding: '2px 9px', borderRadius: 6, minWidth: 42, textAlign: 'center',
          }}
        >
          {pct}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.4 }}>{item.title}</div>
          <div className="mono" style={{ fontSize: 11, color: '#666', marginTop: 3 }}>
            {item.source}
            {item.category ? ` · ${item.category}` : ''}
            {date ? ` · ${new Date(date).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}` : ''}
          </div>
        </div>
        <span style={{ color: '#555', fontSize: 12, flexShrink: 0, transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }}>▶</span>
      </div>

      {open && (
        <div
          style={{
            marginTop: 10, marginLeft: 54, padding: '12px 16px', background: '#111',
            border: '1px solid #222', borderRadius: 12, fontSize: 12.5, lineHeight: 1.6, color: '#bbb',
          }}
        >
          {ai?.drk_relevance ? (
            <>
              <DetailRow label="KI-Einschätzung">{ai.drk_relevance}</DetailRow>
              {ai.escalation_potential && (
                <DetailRow label="Eskalationspotenzial">
                  {ESCALATION_LABELS[ai.escalation_potential] || ai.escalation_potential}
                </DetailRow>
              )}
              {ai.affected_area && <DetailRow label="Betroffenes Gebiet">{ai.affected_area}</DetailRow>}
              {ai.expected_actions && ai.expected_actions.length > 0 && (
                <DetailRow label="Mögliche DRK-Maßnahmen">{ai.expected_actions.join(' · ')}</DetailRow>
              )}
              {ai.confidence != null && (
                <DetailRow label="Konfidenz">{Math.round(ai.confidence * 100)} %</DetailRow>
              )}
            </>
          ) : (
            <DetailRow label="Bewertung">
              Nur Keyword-Filter (keine KI-Analyse verfügbar). Score {pct} von 100 —{' '}
              {item.is_relevant
                ? 'über der Relevanz-Schwelle von 30.'
                : 'unter der Relevanz-Schwelle von 30, daher herausgefiltert.'}
            </DetailRow>
          )}
          {item.summary && <DetailRow label="Zusammenfassung">{item.summary}</DetailRow>}
          {item.url && (
            <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12 }}>
              Zur Originalmeldung →
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <span style={{ color: '#777', fontSize: 10.5, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', display: 'block' }}>
        {label}
      </span>
      {children}
    </div>
  );
}

/* ---------- Andere Kategorien: Score-Beiträge mit Begründung ---------- */

interface Contribution {
  value?: string;
  points?: number;
  reason?: string;
  source?: string;
  timestamp?: string;
  source_type?: string;
}

function ContributionsDetail({ contributions }: { contributions: Contribution[] }) {
  // Overview kann identische Beiträge mehrfach liefern (mehrere Messzeitpunkte)
  const unique: Contribution[] = [];
  const seen = new Set<string>();
  for (const c of contributions) {
    const key = `${c.reason}|${c.source}|${c.value}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(c);
    }
  }

  if (unique.length === 0) {
    return (
      <p style={{ color: '#666', fontSize: 13 }}>
        Keine Einzelbeiträge — der Score dieser Kategorie ist derzeit 0 oder es liegen keine Detaildaten vor.
      </p>
    );
  }

  return (
    <>
      <SectionLabel color="#888">Score-Beiträge ({unique.length})</SectionLabel>
      {unique.map((c, i) => {
        const pts = c.points ?? 0;
        const color = scoreColor(pts);
        return (
          <div
            key={i}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 0',
              borderBottom: i < unique.length - 1 ? '1px solid #1e1e1e' : 'none',
            }}
          >
            <span
              className="mono"
              title="Punkte-Beitrag zum Score"
              style={{
                flexShrink: 0, fontSize: 13, fontWeight: 700, color,
                background: `${color}22`, padding: '2px 9px', borderRadius: 6, minWidth: 42, textAlign: 'center',
              }}
            >
              {Math.round(pts)}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.4 }}>{c.reason || '—'}</div>
              <div className="mono" style={{ fontSize: 11, color: '#666', marginTop: 3 }}>
                {c.value ? `${c.value} · ` : ''}
                {c.source || 'unbekannte Quelle'}
                {c.timestamp ? ` · ${new Date(c.timestamp).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}` : ''}
              </div>
            </div>
          </div>
        );
      })}
    </>
  );
}
