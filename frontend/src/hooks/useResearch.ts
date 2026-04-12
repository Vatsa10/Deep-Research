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

const INITIAL_STATE: ResearchState = {
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
  const [state, setState] = useState<ResearchState>(INITIAL_STATE);

  const startResearch = useCallback(
    async (query: string, depth: string) => {
      setState({ ...INITIAL_STATE, status: "running" });

      try {
        const res = await fetch("/api/research", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
          },
          body: JSON.stringify({ query, depth }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Failed: ${res.statusText}`);
        }

        const { session_id } = await res.json();
        setState((prev) => ({ ...prev, sessionId: session_id }));

        connectSSE(session_id, setState);
      } catch (err) {
        setState((prev) => ({
          ...prev,
          status: "error",
          error: err instanceof Error ? err.message : "Unknown error",
        }));
      }
    },
    []
  );

  const exportResearch = useCallback(async () => {
    if (!state.sessionId) return;
    const headers = getAuthHeaders();
    const url = `/api/research/${state.sessionId}/export`;
    const res = await fetch(url, { headers });
    if (res.ok) {
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `research-${state.sessionId.slice(0, 8)}.json`;
      a.click();
    }
  }, [state.sessionId]);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`/api/research/${sessionId}`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      setState({
        ...INITIAL_STATE,
        status: data.status === "completed" ? "completed" : "error",
        sessionId,
        report: data.report || null,
        distilled: data.distilled_summary || null,
        validation: data.validation || null,
        factCheck: data.fact_check || null,
        reasoningTrace: data.reasoning_trace || [],
      });
    } catch {}
  }, []);

  return { state, startResearch, exportResearch, loadSession };
}

function connectSSE(
  sessionId: string,
  setState: React.Dispatch<React.SetStateAction<ResearchState>>
) {
  const evtSource = new EventSource(`/api/research/${sessionId}/stream`);

  evtSource.onmessage = (event) => {
    const data: SSEEvent = JSON.parse(event.data);

    setState((prev) => {
      const newState = { ...prev };
      newState.events = [...prev.events, data];

      switch (data.type) {
        case "dag_init":
          newState.dagStructure = data.structure as DAGStructure;
          newState.iteration = (data.iteration as number) || 1;
          newState.nodeStatuses = {};
          break;
        case "node_running":
          newState.nodeStatuses = {
            ...prev.nodeStatuses,
            [data.node_id as string]: "running",
          };
          break;
        case "node_completed":
          newState.nodeStatuses = {
            ...prev.nodeStatuses,
            [data.node_id as string]: "completed",
          };
          break;
        case "node_failed":
          newState.nodeStatuses = {
            ...prev.nodeStatuses,
            [data.node_id as string]: "failed",
          };
          break;
        case "iteration_start":
          newState.iteration = (data.iteration as number) || 1;
          newState.maxIterations = (data.max as number) || 3;
          break;
        case "validation":
          newState.validation = data as Record<string, unknown>;
          break;
        case "fact_check":
          newState.factCheck = {
            total: (data.total as number) || 0,
            verified: (data.verified as number) || 0,
            dead: (data.dead as number) || 0,
          };
          break;
        case "done":
          newState.status = "completed";
          newState.report = (data.report as string) || null;
          newState.distilled = (data.distilled as string) || null;
          fetchTrace(sessionId, setState);
          break;
        case "error":
          newState.status = "error";
          newState.error = (data.message as string) || "Unknown error";
          break;
      }

      return newState;
    });

    if (data.type === "done" || data.type === "error") {
      evtSource.close();
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    setState((prev) => ({
      ...prev,
      status: prev.status === "completed" ? "completed" : "error",
      error: prev.status === "completed" ? null : "Lost connection to server",
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
    if (res.ok) {
      const data = await res.json();
      setState((prev) => ({
        ...prev,
        validation: data.validation || prev.validation,
        reasoningTrace: data.reasoning_trace || [],
        factCheck: data.fact_check
          ? {
              total: data.fact_check.total || 0,
              verified: data.fact_check.verified || 0,
              dead: data.fact_check.dead || 0,
            }
          : prev.factCheck,
      }));
    }
  } catch {}
}
