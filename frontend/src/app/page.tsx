'use client';

import { useEffect, useCallback, useState } from 'react';
import Header from '@/components/Header';
import RiskGauge from '@/components/RiskGauge';
import CategoryCard from '@/components/CategoryCard';
import AlertList from '@/components/AlertList';
import WaterLevelBars from '@/components/WaterLevelBars';
import FireDangerCard from '@/components/FireDangerCard';
import WeatherCard from '@/components/WeatherCard';
import AirQualityCard from '@/components/AirQualityCard';
import CategoryDetailModal from '@/components/CategoryDetailModal';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDashboardStore } from '@/store/dashboard';
import { apiFetch } from '@/lib/api';

const CATEGORIES = [
  { key: 'water', title: 'Hochwasser', icon: '🌊' },
  { key: 'weather', title: 'Wetter', icon: '⛈️' },
  { key: 'fire', title: 'Waldbrand', icon: '🔥' },
  { key: 'official_warning', title: 'Behörden', icon: '⚠️' },
  { key: 'traffic', title: 'Verkehr', icon: '🚗' },
  { key: 'air_quality', title: 'Luft', icon: '💨' },
  { key: 'news', title: 'News', icon: '📰' },
  { key: 'seismic', title: 'Erdbeben', icon: '🌍' },
  { key: 'radiation', title: 'Strahlung', icon: '☢️' },
  { key: 'health', title: 'Gesundheit', icon: '🏥' },
];

// Die Overview-API liefert {score, components: {...details}} — hier flach ziehen.
function flat(rs: any): any {
  if (!rs) return null;
  return { ...(rs.components || {}), score: rs.score ?? rs.components?.score ?? 0 };
}

export default function Dashboard() {
  const store = useDashboardStore();
  const [, setRefreshKey] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<(typeof CATEGORIES)[number] | null>(null);

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

  const water = flat(store.riskScores.water);
  const weather = flat(store.riskScores.weather);
  const fire = flat(store.riskScores.fire);

  return (
    <div className="min-h-screen" style={{ padding: 24 }}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
        <Header isConnected={isConnected} lastUpdated={store.lastUpdated} />

        <div className="grid grid-cols-1 xl:grid-cols-3" style={{ gap: 24 }}>
          {/* Gesamtrisiko */}
          <div className="card slide-in flex flex-col items-center justify-center" style={{ animationDelay: '.1s' }}>
            <div className="lbl" style={{ marginBottom: 24 }}>Gesamtrisiko</div>
            <RiskGauge score={store.overallScore} />
          </div>

          {/* Pegelstände */}
          <div className="card slide-in xl:col-span-2" style={{ animationDelay: '.2s' }}>
            <div className="card-head">
              <span style={{ fontSize: 24 }}>🌊</span>
              <div className="lbl">Pegelstände</div>
            </div>
            <WaterLevelBars stations={water?.stations || []} />
          </div>

          {/* Waldbrandgefahr */}
          <div className="card slide-in" style={{ animationDelay: '.3s' }}>
            <div className="card-head">
              <span style={{ fontSize: 24 }}>🔥</span>
              <div className="lbl">Waldbrandgefahr</div>
            </div>
            <FireDangerCard riskData={fire} />
          </div>

          {/* Wetter */}
          <div className="card slide-in" style={{ animationDelay: '.4s' }}>
            <div className="card-head">
              <span style={{ fontSize: 24 }}>⛈️</span>
              <div className="lbl">Wetter</div>
            </div>
            <WeatherCard riskData={weather} />
          </div>

          {/* Luftqualität */}
          <div className="card slide-in" style={{ animationDelay: '.5s' }}>
            <div className="card-head">
              <span style={{ fontSize: 24 }}>💨</span>
              <div className="lbl">Luftqualität</div>
            </div>
            <AirQualityCard />
          </div>

          {/* Kategorien */}
          <div
            className="slide-in xl:col-span-3 grid grid-cols-2 md:grid-cols-5"
            style={{ gap: 12, animationDelay: '.6s' }}
          >
            {CATEGORIES.map((cat) => {
              const data = flat(store.riskScores[cat.key]);
              return (
                <CategoryCard
                  key={cat.key}
                  title={cat.title}
                  icon={cat.icon}
                  score={data?.score ?? 0}
                  detail={data?.detail}
                  onClick={() => setSelectedCategory(cat)}
                />
              );
            })}
          </div>

          {/* Aktive Alarme */}
          <div className="card slide-in xl:col-span-3" style={{ animationDelay: '.7s' }}>
            <div className="card-head">
              <span style={{ fontSize: 24 }}>🚨</span>
              <div className="lbl">Aktive Alarme</div>
            </div>
            <AlertList
              alerts={store.activeAlerts}
              onAcknowledge={() => setRefreshKey((k) => k + 1)}
            />
          </div>
        </div>

        {selectedCategory && (
          <CategoryDetailModal
            category={selectedCategory}
            riskData={flat(store.riskScores[selectedCategory.key])}
            onClose={() => setSelectedCategory(null)}
          />
        )}
      </div>
    </div>
  );
}
