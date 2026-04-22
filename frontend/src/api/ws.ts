import { useEffect, useRef, useState } from "react";

import { useAuth } from "../store/auth";

export type ChannelEnvelope = {
  v: number;
  type: string;
  ts: string;
  seq?: number;
  data: Record<string, unknown>;
};

export type ChannelState = "idle" | "connecting" | "open" | "closed" | "error";

type UseChannelOptions = {
  /** URL path starting with "/ws/…". Pass "" to disable the hook. */
  path: string;
  /** Max messages retained in-memory. Older messages are dropped FIFO. */
  bufferSize?: number;
};

/**
 * One WebSocket per hook instance, keyed on `path`. Reconnects with the last
 * observed ``seq`` via the ``since_seq`` query param. Automatically attaches
 * the current access token from the auth store.
 */
export function useChannel({ path, bufferSize = 500 }: UseChannelOptions) {
  const [state, setState] = useState<ChannelState>("idle");
  const [messages, setMessages] = useState<ChannelEnvelope[]>([]);
  const lastSeq = useRef<number>(0);
  const wsRef = useRef<WebSocket | null>(null);

  const access = useAuth((s) => s.access);

  useEffect(() => {
    if (!path || !access) {
      setState("idle");
      return;
    }

    let cancelled = false;
    let retryHandle: number | undefined;

    const connect = () => {
      if (cancelled) return;
      setState("connecting");
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const url = new URL(`${proto}://${window.location.host}${path}`);
      url.searchParams.set("token", access);
      if (lastSeq.current > 0) url.searchParams.set("since_seq", String(lastSeq.current));

      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      ws.onopen = () => setState("open");
      ws.onmessage = (ev) => {
        try {
          const env = JSON.parse(ev.data) as ChannelEnvelope;
          if (typeof env.seq === "number") lastSeq.current = env.seq;
          setMessages((prev) => {
            const next = prev.length >= bufferSize ? prev.slice(-bufferSize + 1) : prev.slice();
            next.push(env);
            return next;
          });
        } catch {
          // ignore non-JSON frames
        }
      };
      ws.onerror = () => setState("error");
      ws.onclose = (ev) => {
        setState("closed");
        if (!cancelled && ev.code !== 4401) {
          retryHandle = window.setTimeout(connect, 2000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (retryHandle) window.clearTimeout(retryHandle);
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
    };
  }, [path, access, bufferSize]);

  const clear = () => {
    lastSeq.current = 0;
    setMessages([]);
  };

  return { state, messages, clear };
}
