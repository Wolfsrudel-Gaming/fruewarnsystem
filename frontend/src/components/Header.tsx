'use client';

import { useEffect, useState } from 'react';

interface HeaderProps {
  isConnected: boolean;
  lastUpdated: string | null;
}

export default function Header({ isConnected, lastUpdated }: HeaderProps) {
  const [clock, setClock] = useState('–:–:–');

  useEffect(() => {
    const tick = () =>
      setClock(new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="slide-in flex items-center justify-between mb-8">
      <div className="flex items-center gap-4">
        <div
          className="flex items-center justify-center text-white font-black"
          style={{
            width: 48, height: 48, background: '#e81e1e', borderRadius: 12,
            fontSize: 24, boxShadow: '0 0 30px rgba(232,30,30,.4)',
          }}
        >
          ✚
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-.5px' }}>DRK Troisdorf</div>
          <div style={{ fontSize: 13, color: '#888', fontWeight: 500, letterSpacing: 2, textTransform: 'uppercase' }}>
            Frühwarnsystem
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2.5">
        <div
          className="pulse-dot"
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: isConnected ? '#22c55e' : '#ef4444',
            boxShadow: `0 0 12px ${isConnected ? '#22c55e' : '#ef4444'}`,
          }}
        />
        <span style={{ fontSize: 12, color: '#888', fontWeight: 600, letterSpacing: 1 }}>
          {isConnected ? 'LIVE' : 'OFFLINE'}
        </span>
        <span className="mono" style={{ fontSize: 12, color: '#666', marginLeft: 6 }} title={lastUpdated ? `Aktualisiert: ${new Date(lastUpdated).toLocaleTimeString('de-DE')}` : undefined}>
          {clock}
        </span>
      </div>
    </div>
  );
}
