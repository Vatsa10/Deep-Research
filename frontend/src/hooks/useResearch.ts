import { useState, useCallback } from "react";

interface DAGStructure {
  nodes: { id: string; label: string; type: string; depends_on: string[] }[];
  edges: { from: string; to: string }[];
}

interface SSEEvent {
  type: string;
  [key: string]: unknown;
}

interface ResearchState {
  status: "idle" | "running" | "completed" | "error";
  sessionId: string | null;
  dagStructure: DAGStructure | null;
  nodeStatuses: Record<string, string>;
  events: SSEEvent[];
  report: string | null;
  iteration: number;
  maxIterations: number;
  error: string | null;
}

const INITIAL_STATE: ResearchState = {
  status: "idle",
  sessionId: null,
  dagStructure: null,
  nodeStatuses: {},
  events: [],
  report: null,
  iteration: 1,
  maxIterations: 3,
  error: null,
};

export function useResearch() {
  const [state, setState] = useState<ResearchState>(INITIAL_STATE);

  const startResearch = useCallback(async (query: string, depth: string) => {
    setState({ ...INITIAL_STATE, status: "running" });

    try {
      // Start the research
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, depth }),
      });

      if (!res.ok) {
        throw new Error(`Failed to start research: ${res.statusText}`);
      }

      const { session_id } = await res.json();
      setState((prev) => ({ ...prev, sessionId: session_id }));

      // Connect SSE
      const evtSource = new EventSource(
        `/api/research/${session_id}/stream`
      );

      evtSource.onmessage = (event) => {
        const data: SSEEvent = JSON.parse(event.data);

        setState((prev) => {
          const newState = { ...prev };
          newState.events = [...prev.events, data];

          switch (data.type) {
            case "dag_init":
              newState.dagStructure = data.structure as DAGStructure;
              newState.iteration = (data.iteration as number) || 1;
              // Reset node statuses for new iteration
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

            case "critique":
              // Critique received
              break;

            case "done":
              newState.status = "completed";
              newState.report = (data.report as string) || null;
              break;

            case "error":
              newState.status = "error";
              newState.error = (data.message as string) || "Unknown error";
              break;

            case "keepalive":
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
          status: "error",
          error: "Lost connection to server",
        }));
      };
    } catch (err) {
      setState((prev) => ({
        ...prev,
        status: "error",
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  return { state, startResearch };
}
