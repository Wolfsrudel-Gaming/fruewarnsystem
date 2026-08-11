const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/fruelage';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('fws_token') : null;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function getWsUrl(): string {
  if (typeof window === 'undefined') return '';
  const wsBase = process.env.NEXT_PUBLIC_WS_URL;
  if (wsBase) return wsBase;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/fruelage/ws`;
}
