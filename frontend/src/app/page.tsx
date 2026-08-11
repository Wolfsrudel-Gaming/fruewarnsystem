'use client';

import { useEffect, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import Header from '@/components/Header';
import RiskGauge from '@/components/RiskGauge';
import CategoryCard from '@/components/CategoryCard';
import AlertList from '@/components/AlertList';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDashboardStore } from '@/store/dashboard';
import { apiFetch } from '@/lib/api';

const MapView = dynamic(() => import('@/components/MapView'), { ssr: false });

const CATEGORIES = [
  { key: 'water', title: 'Hochwasser', icon: '🌊' },
  { key: 'weather', title: 'Wetter', icon: '⛈️' },
  { key: 'fire', title: 'Waldbrand', icon: '🔥' },
  { key: 'official_warning', title: 'Behörden', icon: '⚠️' },
  { key: 'traffic', title: 'Verkehr', icon: '🚗' },
  { key: 'air_quality', title: 'Luftqualität', icon: '💨' },
  { key: 'news', title: 'Nachrichten', icon: '📰' },
];

export default function Dashboard() {
  const store = useDashboardStore();
  const [refreshKey, setRefreshKey] = useState(0);

  const onWsMessage = useCallback((msg: any) => {
    if (msg.type === 'update' && msg.scores) {
      store.updateScores(msg.scores);
    }
  }, []);

  const { isConnected } = useWebSocket(onWsMessage);

  const fetchOverview = async () => {
    try {
      const data = await apiFetch<any>('/api/dashboard/overview');
      store.setOverview(data);
    } catch (e) {
      console.error('Failed to fetch overview:', e);
      store.setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Header isConnected={isConnected} lastUpdated={store.lastUpdated} />

      <main className="flex-1 p-4 lg:p-6 space-y-6 max-w-[1920px] mx-auto w-full">
        {/* Top Row: Gauge + Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Risk Gauge */}
          <div className="card flex flex-col items-center justify-center py-6">
            <h2 className="text-sm font-medium text-dark-400 mb-4">GESAMTRISIKO</h2>
            <RiskGauge score={store.overallScore} size="lg" />
          </div>

          {/* Active Alerts */}
          <div className="lg:col-span-2">
            <h2 className="text-sm font-medium text-dark-400 mb-3">AKTIVE ALARME</h2>
            <div className="max-h-[300px] overflow-y-auto">
              <AlertList
                alerts={store.activeAlerts}
                onAcknowledge={() => setRefreshKey(k => k + 1)}
              />
            </div>
          </div>
        </div>

        {/* Category Cards */}
        <div>
          <h2 className="text-sm font-medium text-dark-400 mb-3">GEFAHRENKATEGORIEN</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            {CATEGORIES.map(cat => {
              const data = store.riskScores[cat.key];
              return (
                <CategoryCard
                  key={cat.key}
                  title={cat.title}
                  icon={cat.icon}
                  score={data?.score ?? 0}
                  detail={data?.detail ?? 'Lädt...'}
                />
              );
            })}
          </div>
        </div>

        {/* Map + Details */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Map */}
          <div className="card p-0 overflow-hidden">
            <div className="p-3 border-b border-dark-700">
              <h2 className="text-sm font-medium text-dark-400">LAGEKARTE</h2>
            </div>
            <div className="h-[500px]">
              <MapView />
            </div>
          </div>

          {/* Right panel: Water + Weather */}
          <div className="space-y-4">
            {/* Water Levels */}
            <div className="card">
              <h3 className="text-sm font-medium text-dark-400 mb-3">PEGELSTÄNDE</h3>
              <WaterLevelWidget riskData={store.riskScores.water} />
            </div>

            {/* Weather Warnings */}
            <div className="card">
              <h3 className="text-sm font-medium text-dark-400 mb-3">WETTERWARNUNGEN</h3>
              <WeatherWidget riskData={store.riskScores.weather} />
            </div>

            {/* System Status */}
            <div className="card">
              <h3 className="text-sm font-medium text-dark-400 mb-3">SYSTEMSTATUS</h3>
              <SystemStatusWidget />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function WaterLevelWidget({ riskData }: { riskData: any }) {
  if (!riskData?.stations) {
    return <p className="text-dark-500 text-sm">Keine Pegeldaten verfügbar</p>;
  }

  return (
    <div className="space-y-2">
      {riskData.stations.slice(0, 6).map((station: any, i: number) => (
        <div key={i} className="flex items-center justify-between py-1 border-b border-dark-800 last:border-0">
          <div>
            <span className="text-sm">{station.station}</span>
            <span className="text-xs text-dark-500 ml-2">
              {station.trend === 'rising' ? '↑' : station.trend === 'falling' ? '↓' : '→'}
            </span>
          </div>
          <div className="text-right">
            <span className="text-sm font-mono">{station.level ? `${station.level} cm` : '-'}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function WeatherWidget({ riskData }: { riskData: any }) {
  if (!riskData?.warnings || riskData.warnings.length === 0) {
    return <p className="text-green-500 text-sm">Keine Wetterwarnungen aktiv</p>;
  }

  return (
    <div className="space-y-2">
      {riskData.warnings.map((w: any, i: number) => (
        <div key={i} className="flex items-center gap-2 py-1">
          <span className={`w-2 h-2 rounded-full ${
            w.severity >= 80 ? 'bg-red-500' :
            w.severity >= 50 ? 'bg-orange-500' : 'bg-yellow-500'
          }`} />
          <span className="text-sm truncate">{w.title}</span>
        </div>
      ))}
    </div>
  );
}

function SystemStatusWidget() {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    apiFetch('/api/system/status').then(setStatus).catch(() => {});
  }, []);

  if (!status) return <p className="text-dark-500 text-sm">Lade...</p>;

  const update = status.update_status || {};
  return (
    <div className="space-y-1 text-sm">
      <div className="flex justify-between">
        <span className="text-dark-400">Version</span>
        <span className="font-mono">{update.current_hash || status.version}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-dark-400">Auto-Update</span>
        <span className={update.auto_update_enabled ? 'text-green-400' : 'text-red-400'}>
          {update.auto_update_enabled ? 'Aktiv' : 'Deaktiviert'}
        </span>
      </div>
      <div className="flex justify-between">
        <span className="text-dark-400">Branch</span>
        <span className="font-mono">{update.update_branch}</span>
      </div>
    </div>
  );
}
