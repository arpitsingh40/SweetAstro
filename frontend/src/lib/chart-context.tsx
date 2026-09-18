import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ChartResponse } from "./types";

interface ChartContextValue {
  chart: ChartResponse | null;
  setChart: (chart: ChartResponse | null) => void;
}

const ChartContext = createContext<ChartContextValue | null>(null);

const STORAGE_KEY = "sweetastro_chart_v1";

export function ChartProvider({ children }: { children: ReactNode }) {
  const [chart, setChartState] = useState<ChartResponse | null>(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as ChartResponse) : null;
    } catch {
      return null;
    }
  });

  const setChart = (next: ChartResponse | null) => {
    setChartState(next);
    try {
      if (next) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      else sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // storage unavailable (private mode) — in-memory state still works
    }
  };

  useEffect(() => {
    // keep multi-tab usage consistent without a store dependency
    const onStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY) return;
      try {
        setChartState(event.newValue ? (JSON.parse(event.newValue) as ChartResponse) : null);
      } catch {
        setChartState(null);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = useMemo(() => ({ chart, setChart }), [chart]);
  return <ChartContext.Provider value={value}>{children}</ChartContext.Provider>;
}

export function useChart(): ChartContextValue {
  const ctx = useContext(ChartContext);
  if (!ctx) throw new Error("useChart must be used inside ChartProvider");
  return ctx;
}
