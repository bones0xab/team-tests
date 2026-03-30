import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api/client";
import type { DashboardResponse } from "../api/client";
import { useWebSocketContext } from "./useWebSocket";

interface UseAnalysisResult {
  data: DashboardResponse | null;
  loading: boolean;
  /** True while fetching when we already have data (stale-while-revalidate). */
  isRefreshing: boolean;
  error: string | null;
  refresh: () => void;
}

export function useAnalysis(
  projectKey: string | null,
  daysBack: number,
  page: number,
  pageSize: number
): UseAnalysisResult {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const { lastMessage } = useWebSocketContext();

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async () => {

    setLoading(true);
    setError(null);

    try {
      const result = await api.getDashboard(
        projectKey ?? undefined,
        daysBack,
        page,
        pageSize
      );
      if (mounted.current) {
        setData(result);
      }
    } catch (e) {
      if (mounted.current) {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    } finally {
      if (mounted.current) {
        setLoading(false);
      }
    }
  }, [projectKey, daysBack, page, pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  // Replace the 5-minute polling with a WebSocket JIRA_UPDATE listener
  useEffect(() => {
    if (lastMessage?.type === "JIRA_UPDATE") {
      void load();
    }
  }, [lastMessage, load]);

  const isRefreshing = loading && data !== null;

  return { data, loading, isRefreshing, error, refresh: load };
}
