import { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react';

export interface WebSocketMessage {
  type: string;
  data?: any;
  user?: string;
  [key: string]: any;
}

interface WebSocketContextPayload {
  lastMessage: WebSocketMessage | null;
  isConnected: boolean;
  send: (msg: WebSocketMessage) => void;
}

export const WebSocketContext = createContext<WebSocketContextPayload>({
  lastMessage: null,
  isConnected: false,
  send: () => {},
});

export const useWebSocketContext = () => useContext(WebSocketContext);

export function useWebSocket(roomId: string = 'global'): WebSocketContextPayload {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const isMountedRef = useRef(false); // ← tracks whether we're truly mounted

  const connect = useCallback(() => {
    if (!isMountedRef.current) return; // ← bail if already torn down

    if (wsRef.current && (
      wsRef.current.readyState === WebSocket.CONNECTING ||
      wsRef.current.readyState === WebSocket.OPEN
    )) return;

    const userId = "browser-client";
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${roomId}/${userId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) { ws.close(); return; } // ← guard here too
      setIsConnected(true);
      retryCountRef.current = 0;
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        setLastMessage(JSON.parse(event.data));
      } catch {
        // ignored
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (!isMountedRef.current) return; // ← don't reschedule if unmounted
      const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 15000);
      retryCountRef.current += 1;
      reconnectTimeoutRef.current = window.setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [roomId]);

  useEffect(() => {
    isMountedRef.current = true;

    // Small delay lets Strict Mode's first unmount fire before we open the socket
    const initTimeout = window.setTimeout(() => {
      if (isMountedRef.current) connect();
    }, 0);

    return () => {
      isMountedRef.current = false;
      window.clearTimeout(initTimeout);
      if (reconnectTimeoutRef.current) window.clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  return { isConnected, lastMessage, send };
}