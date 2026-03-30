import { useState, useEffect } from "react";
import { api } from "../api/client";
import type { Snapshot, Metrics, Rules } from "../api/client";

export function useSnapshots() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);

  const load = async () => {
    try {
      const data = await api.getSnapshots();
      setSnapshots(data);
    } catch {
      setSnapshots([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (project: string, health: string, metrics: Metrics, rules: Rules) => {
    try {
      const snap = await api.saveSnapshot({ project, health, metrics, rules });
      setSnapshots((prev) => [...prev, snap]);
      return true;
    } catch {
      return false;
    }
  };

  const clear = async () => {
    await api.deleteSnapshots();
    setSnapshots([]);
  };

  return { snapshots, save, clear, reload: load };
}
