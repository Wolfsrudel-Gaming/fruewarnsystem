'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface ConnectInfo {
  name: string;
  sync_url: string;
  api_url: string;
  ws_url: string;
  hint: string;
}

export default function AppConnectCard() {
  const [info, setInfo] = useState<ConnectInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiFetch<ConnectInfo>('/api/system/app-connect').then(setInfo).catch(() => {});
  }, []);

  const copy = async () => {
    if (!info) return;
    try {
      await navigator.clipboard.writeText(info.sync_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback für ältere Browser / http
      const ta = document.createElement('textarea');
      ta.value = info.sync_url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  if (!info) return null;

  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      }}
    >
      <span style={{ fontSize: 28 }}>📱</span>
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 2 }}>Mobile App verbinden</div>
        <div style={{ fontSize: 11.5, color: '#888', lineHeight: 1.5 }}>
          Diesen Link in der App unter <strong style={{ color: '#aaa' }}>Einstellungen → Server-Verbindung</strong> eintragen
          und speichern — Lagebild, Alarme und Live-Updates werden dann synchronisiert.
        </div>
      </div>
      <div
        className="mono"
        style={{
          display: 'flex', alignItems: 'center', gap: 10, background: '#111',
          border: '1px solid #2a2a2a', borderRadius: 12, padding: '10px 14px',
        }}
      >
        <a href={info.sync_url} style={{ fontSize: 13, textDecoration: 'none' }}>
          {info.sync_url}
        </a>
        <button
          onClick={copy}
          style={{
            background: copied ? '#22c55e' : '#e81e1e', color: '#fff', border: 'none',
            borderRadius: 8, padding: '5px 12px', fontSize: 11.5, fontWeight: 700,
            cursor: 'pointer', transition: 'background .2s', whiteSpace: 'nowrap',
          }}
        >
          {copied ? '✓ Kopiert' : 'Kopieren'}
        </button>
      </div>
    </div>
  );
}
