import { useEffect, useRef, useState, useCallback } from 'react';

interface WSEvent {
  type: string;
  [key: string]: unknown;
}

export function useWebSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WSEvent;
          if (data.type !== 'pong') {
            setEvents((prev) => [...prev.slice(-100), data]);
          }
        } catch { /* ignore invalid JSON */ }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 3s
        setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    } catch { /* ignore connection errors */ }
  }, [url]);

  useEffect(() => {
    connect();
    // Ping every 30s
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      wsRef.current?.close();
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}
