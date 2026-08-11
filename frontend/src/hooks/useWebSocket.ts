'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { getWsUrl } from '@/lib/api';

interface WSMessage {
  type: string;
  [key: string]: any;
}

export function useWebSocket(onMessage?: (msg: WSMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeout = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    const url = getWsUrl();
    if (!url) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage?.(data);
      } catch {}
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimeout.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { isConnected };
}
