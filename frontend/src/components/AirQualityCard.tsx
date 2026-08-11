'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface Reading {
  station_name?: string;
  pm25?: number | null;
  pm10?: number | null;
  ozone?: number | null;
  no2?: number | null;
}

// max = Skalenende für den Balken, warn/danger = Farbgrenzen (µg/m³)
const POLLUTANTS: { key: keyof Reading; label: string; max: number; warn: number; danger: number }[] = [
  { key: 'pm25',  label: 'PM 2.5', max: 50,  warn: 25,  danger: 50 },
  { key: 'pm10',  label: 'PM 10',  max: 80,  warn: 40,  danger: 80 },
  { key: 'ozone', label: 'Ozon',   max: 180, warn: 120, danger: 180 },
  { key: 'no2',   label: 'NO₂',    max: 80,  warn: 40,  danger: 80 },
];

export default function AirQualityCard() {
  const [reading, setReading] = useState<Reading | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiFetch<any>('/api/dashboard/air-quality')
      .then((d) => {
        const readings = d?.readings || [];
        // Neueste Messung mit mindestens einem Wert
        const r = readings.find((x: Reading) => x.pm25 != null || x.pm10 != null || x.ozone != null || x.no2 != null);
        setReading(r || null);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  if (!loaded) {
    return <p style={{ color: '#666', fontSize: 13 }}>Lade…</p>;
  }
  if (!reading) {
    return <p style={{ color: '#666', fontSize: 13 }}>Keine Messdaten verfügbar</p>;
  }

  return (
    <>
      {POLLUTANTS.map((p, i) => {
        const value = reading[p.key] as number | null | undefined;
        if (value == null) return null;
        const color = value >= p.danger ? '#ef4444' : value >= p.warn ? '#eab308' : '#22c55e';
        const width = Math.min(100, (value / p.max) * 100);
        return (
          <div key={p.key} style={{ marginBottom: i < POLLUTANTS.length - 1 ? 16 : 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: '#aaa' }}>{p.label}</span>
              <span className="mono" style={{ fontSize: 12, fontWeight: 600, color }}>
                {Math.round(value)} µg/m³
              </span>
            </div>
            <div className="track" style={{ height: 6 }}>
              <div style={{ height: '100%', width: `${width}%`, background: color, borderRadius: 3, transition: 'width 1s ease' }} />
            </div>
          </div>
        );
      })}
      {reading.station_name && (
        <div style={{ fontSize: 11, color: '#555', marginTop: 14 }}>{reading.station_name}</div>
      )}
    </>
  );
}
