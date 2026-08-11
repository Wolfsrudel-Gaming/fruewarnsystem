'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface Warning {
  title: string;
  severity?: number;
}

interface WeatherCardProps {
  riskData?: { warnings?: Warning[]; climate_30d?: any };
}

interface ForecastData {
  current?: {
    temperature_2m?: number;
    apparent_temperature?: number;
    relative_humidity_2m?: number;
    precipitation?: number;
    weather_code?: number;
    wind_speed_10m?: number;
    wind_gusts_10m?: number;
  } | null;
  hourly_24h?: {
    time: string[];
    temperature_2m: number[];
    precipitation_probability: number[];
    weather_code: number[];
  } | null;
  climate_30d?: {
    hot_days?: number;
    very_hot_days?: number;
    dry_days?: number;
    max_dry_streak?: number;
    rain_sum_mm?: number;
    avg_tmax?: number;
    heat_drought_level?: number;
    heat_drought_label?: string;
  } | null;
}

function wmo(code?: number): { icon: string; text: string } {
  if (code == null) return { icon: '·', text: '' };
  if (code === 0) return { icon: '☀️', text: 'Klar' };
  if (code <= 2) return { icon: '🌤️', text: 'Leicht bewölkt' };
  if (code === 3) return { icon: '☁️', text: 'Bedeckt' };
  if (code <= 48) return { icon: '🌫️', text: 'Nebel' };
  if (code <= 57) return { icon: '🌦️', text: 'Niesel' };
  if (code <= 67) return { icon: '🌧️', text: 'Regen' };
  if (code <= 77) return { icon: '🌨️', text: 'Schnee' };
  if (code <= 82) return { icon: '🌧️', text: 'Schauer' };
  if (code <= 86) return { icon: '🌨️', text: 'Schneeschauer' };
  return { icon: '⛈️', text: 'Gewitter' };
}

const LEVEL_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#a855f7'];

export default function WeatherCard({ riskData }: WeatherCardProps) {
  const [data, setData] = useState<ForecastData | null>(null);

  useEffect(() => {
    const load = () => apiFetch<ForecastData>('/api/dashboard/weather-forecast').then(setData).catch(() => {});
    load();
    const interval = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const cur = data?.current;
  const hourly = data?.hourly_24h;
  const climate = data?.climate_30d;
  const warnings = riskData?.warnings || [];
  const curWmo = wmo(cur?.weather_code);

  // 24h in 8 x 3h-Schritten
  const slots = hourly?.time
    ? hourly.time.map((t, i) => ({
        hour: new Date(t).getHours(),
        temp: hourly.temperature_2m[i],
        rain: hourly.precipitation_probability?.[i],
        code: hourly.weather_code?.[i],
      })).filter((_, i) => i % 3 === 0).slice(0, 8)
    : [];

  const level = climate?.heat_drought_level ?? 0;
  const levelColor = LEVEL_COLORS[Math.min(4, level)];

  return (
    <>
      {/* Aktuell */}
      {cur ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
          <span style={{ fontSize: 38, lineHeight: 1 }}>{curWmo.icon}</span>
          <div>
            <span className="mono" style={{ fontSize: 30, fontWeight: 700 }}>
              {Math.round(cur.temperature_2m ?? 0)}°
            </span>
            <span style={{ fontSize: 12, color: '#888', marginLeft: 8 }}>
              gefühlt {Math.round(cur.apparent_temperature ?? 0)}°
            </span>
            <div className="mono" style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
              {curWmo.text} · {cur.relative_humidity_2m}% rF · Wind {Math.round(cur.wind_speed_10m ?? 0)} km/h
            </div>
          </div>
        </div>
      ) : (
        <p style={{ color: '#666', fontSize: 13, marginBottom: 16 }}>Lade Wetterdaten…</p>
      )}

      {/* Nächste 24h */}
      {slots.length > 0 && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 16, paddingBottom: 14, borderBottom: '1px solid #1e1e1e' }}>
          {slots.map((s, i) => (
            <div key={i} style={{ flex: 1, textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 9.5, color: '#666' }}>{String(s.hour).padStart(2, '0')}h</div>
              <div style={{ fontSize: 15, margin: '3px 0' }}>{wmo(s.code).icon}</div>
              <div className="mono" style={{ fontSize: 11, fontWeight: 600 }}>{Math.round(s.temp)}°</div>
              <div className="mono" style={{ fontSize: 9.5, color: (s.rain ?? 0) >= 50 ? '#3b82f6' : '#555' }}>
                {s.rain != null ? `${s.rain}%` : ''}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 30-Tage-Analyse */}
      {climate && (
        <div style={{ marginBottom: warnings.length ? 14 : 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: '#777' }}>
              30-Tage-Analyse
            </span>
            <span
              style={{
                fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1,
                color: levelColor, background: `${levelColor}18`, padding: '2px 8px', borderRadius: 6,
              }}
            >
              {climate.heat_drought_label}
            </span>
          </div>
          <div className="mono" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 11.5, color: '#aaa' }}>
            <span>🌡️ {climate.hot_days} Hitzetage ≥30°</span>
            <span>🔥 {climate.very_hot_days} Tage ≥35°</span>
            <span>🏜️ {climate.dry_days} Trockentage</span>
            <span>💧 nur {climate.rain_sum_mm} mm Regen</span>
          </div>
          {level >= 2 && (
            <div style={{ fontSize: 11, color: levelColor, marginTop: 8, lineHeight: 1.5 }}>
              Anhaltende Hitze/Trockenheit fließt in Waldbrand- und Dürre-Risiko ein
              (längste Trockenphase: {climate.max_dry_streak} Tage).
            </div>
          )}
        </div>
      )}

      {/* Amtliche Warnungen */}
      {warnings.length > 0 && (
        <div style={{ borderTop: '1px solid #1e1e1e', paddingTop: 10 }}>
          {warnings.slice(0, 3).map((w, i) => {
            const sev = w.severity ?? 0;
            const color = sev >= 80 ? '#ef4444' : sev >= 50 ? '#f97316' : '#eab308';
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0' }}>
                <div className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}`, flexShrink: 0 }} />
                <span style={{ fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{w.title}</span>
                <span className="mono" style={{ fontSize: 13, fontWeight: 700, color }}>{Math.round(sev)}</span>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
