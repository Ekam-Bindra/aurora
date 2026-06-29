"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { getExplain, type ExplainData } from "@/lib/api";
import ExplainOverlay from "./ExplainOverlay";

type ExplainContextValue = {
  openExplain: (ref: string) => void;
  closeExplain: () => void;
};

const ExplainContext = createContext<ExplainContextValue | null>(null);

export function useExplain(): ExplainContextValue {
  const ctx = useContext(ExplainContext);
  if (!ctx) throw new Error("useExplain must be used within ExplainProvider");
  return ctx;
}

export function ExplainProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ExplainData | null>(null);

  const closeExplain = useCallback(() => {
    setOpen(false);
    setData(null);
    setError(null);
  }, []);

  const openExplain = useCallback((ref: string) => {
    setOpen(true);
    setLoading(true);
    setError(null);
    setData(null);
    getExplain(ref)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ExplainContext.Provider value={{ openExplain, closeExplain }}>
      {children}
      <ExplainOverlay
        open={open}
        loading={loading}
        error={error}
        data={data}
        onClose={closeExplain}
      />
    </ExplainContext.Provider>
  );
}
