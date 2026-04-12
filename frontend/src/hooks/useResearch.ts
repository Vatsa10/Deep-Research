import { useState, useCallback } from "react";
import { getAuthHeaders } from "./useAuth";

interface DAGStructure {
  nodes: { id: string; label: string; type: string; depends_on: string[] }[];
  edges: { from: string; to: string }[];
}

interface SSEEvent {
  type: string;
  [key: string]: unknown;
}

interface FactCheck {
  total: number;
  verified: number;
  dead: number;
}

interface ResearchState {
  status: "idle" | "running" | "completed" | "error";
  sessionId: string | null;
  dagStructure: DAGStructure | null;
  nodeStatuses: Record<string, string>;
  events: SSEEvent[];
  report: string | null;
  distilled: string | null;
  iteration: number;
  maxIterations: number;
  error: string | null;
  validation: Record<string, unknown> | null;
  factCheck: FactCheck | null;
  reasoningTrace: {
    agent: string;
    action: string;
    output_summary: string;
    decisions: string[];
  }[];
}

const INITIAL: ResearchState = {
  status: "idle",
  sessionId: null,
  dagStructure: null,
  nodeStatuses: {},
  events: [],
  report: null,
  distilled: null,
  iteration: 1,
  maxIterations: 3,
  error: null,
  validation: null,
  factCheck: null,
  reasoningTrace: [],
};

export function useResearch() {
  const [state, setState] = useState<ResearchState>(INITIAL);

  const reset = useCallback(() => setState(INITIAL), []);

  const startResearch = useCallback(async (query: string, depth: string) => {
    setState({ ...INITIAL, status: "running" });

    try {
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ query, depth }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }

      const { session_id } = await res.json();
      setState((p) => ({ ...p, sessionId: session_id }));
      connectSSE(session_id, setState);
    } catch (err) {
      setState((p) => ({
        ...p,
        status: "error",
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  const continueResearch = useCallback(
    async (sessionId: string, query: string, depth: string) => {
      setState((p) => ({
        ...p,
        status: "running",
        dagStructure: null,
        nodeStatuses: {},
        events: [],
        error: null,
      }));

      try {
        const res = await fetch(`/api/research/${sessionId}/continue`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeaders() },
          body: JSON.stringify({ query, depth }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || res.statusText);
        }

        const { session_id } = await res.json();
        setState((p) => ({ ...p, sessionId: session_id }));
        connectSSE(session_id, setState);
      } catch (err) {
        setState((p) => ({
          ...p,
          status: "error",
          error: err instanceof Error ? err.message : "Unknown error",
        }));
      }
    },
    []
  );

  const loadSession = useCallback(
    async (sessionId: string): Promise<{ query: string; report: string } | null> => {
      try {
        const res = await fetch(`/api/research/${sessionId}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) return null;
        const data = await res.json();

        setState({
          ...INITIAL,
          status: data.status === "completed" ? "completed" : "error",
          sessionId,
          report: data.report || null,
          distilled: data.distilled_summary || null,
          validation: data.validation || null,
          factCheck: data.fact_check || null,
          reasoningTrace: data.reasoning_trace || [],
        });

        return { query: data.query, report: data.report || "" };
      } catch {
        return null;
      }
    },
    []
  );

  const exportResearch = useCallback(async () => {
    if (!state.sessionId) return;
    const res = await fetch(`/api/research/${state.sessionId}/export`, {
      headers: getAuthHeaders(),
    });
    if (res.ok) {
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `research-${state.sessionId.slice(0, 8)}.json`;
      a.click();
    }
  }, [state.sessionId]);

  return { state, startResearch, continueResearch, loadSession, exportResearch, reset };
}

function connectSSE(
  sessionId: string,
  setState: React.Dispatch<React.SetStateAction<ResearchState>>
) {
  const src = new EventSource(`/api/research/${sessionId}/stream`);

  src.onmessage = (event) => {
    const data: SSEEvent = JSON.parse(event.data);

    setState((prev) => {
      const s = { ...prev, events: [...prev.events, data] };

      switch (data.type) {
        case "dag_init":
          s.dagStructure = data.structure as DAGStructure;
          s.iteration = (data.iteration as number) || 1;
          s.nodeStatuses = {};
          break;
        case "node_running":
          s.nodeStatuses = { ...prev.nodeStatuses, [data.node_id as string]: "running" };
          break;
        case "node_completed":
          s.nodeStatuses = { ...prev.nodeStatuses, [data.node_id as string]: "completed" };
          break;
        case "node_failed":
          s.nodeStatuses = { ...prev.nodeStatuses, [data.node_id as string]: "failed" };
          break;
        case "iteration_start":
          s.iteration = (data.iteration as number) || 1;
          s.maxIterations = (data.max as number) || 3;
          break;
        case "validation":
          s.validation = data as Record<string, unknown>;
          break;
        case "fact_check":
          s.factCheck = {
            total: (data.total as number) || 0,
            verified: (data.verified as number) || 0,
            dead: (data.dead as number) || 0,
          };
          break;
        case "done":
          s.status = "completed";
          s.report = (data.report as string) || null;
          s.distilled = (data.distilled as string) || null;
          fetchTrace(sessionId, setState);
          break;
        case "error":
          s.status = "error";
          s.error = (data.message as string) || "Unknown error";
          break;
      }
      return s;
    });

    if (data.type === "done" || data.type === "error") src.close();
  };

  src.onerror = () => {
    src.close();
    setState((p) => ({
      ...p,
      status: p.status === "completed" ? "completed" : "error",
      error: p.status === "completed" ? null : "Lost connection",
    }));
  };
}

async function fetchTrace(
  sessionId: string,
  setState: React.Dispatch<React.SetStateAction<ResearchState>>
) {
  try {
    const res = await fetch(`/api/research/${sessionId}/trace`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) return;
    const data = await res.json();
    setState((p) => ({
      ...p,
      validation: data.validation || p.validation,
      reasoningTrace: data.reasoning_trace || [],
      factCheck: data.fact_check
        ? { total: data.fact_check.total || 0, verified: data.fact_check.verified || 0, dead: data.fact_check.dead || 0 }
        : p.factCheck,
    }));
  } catch {}
}
