import { create } from 'zustand';

interface RiskScore {
  score: number;
  weight?: number;
  detail?: string;
  [key: string]: any;
}

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

interface DashboardState {
  overallScore: number;
  riskScores: Record<string, RiskScore>;
  activeAlerts: Alert[];
  lastUpdated: string | null;
  isLoading: boolean;

  setOverview: (data: {
    overall_score: number;
    risk_scores: Record<string, RiskScore>;
    active_alerts: Alert[];
    last_updated: string;
  }) => void;

  updateScores: (scores: Record<string, RiskScore>) => void;
  setLoading: (loading: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  overallScore: 0,
  riskScores: {},
  activeAlerts: [],
  lastUpdated: null,
  isLoading: true,

  setOverview: (data) =>
    set({
      overallScore: data.overall_score,
      riskScores: data.risk_scores,
      activeAlerts: data.active_alerts,
      lastUpdated: data.last_updated,
      isLoading: false,
    }),

  updateScores: (scores) =>
    set((state) => ({
      riskScores: { ...state.riskScores, ...scores },
      lastUpdated: new Date().toISOString(),
    })),

  setLoading: (loading) => set({ isLoading: loading }),
}));
