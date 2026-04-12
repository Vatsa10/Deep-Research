interface DAGNode {
  id: string;
  label: string;
  type: string;
  depends_on: string[];
}

interface DAGStructure {
  nodes: DAGNode[];
  edges: { from: string; to: string }[];
}

interface SSEEvent {
  type: string;
  [key: string]: unknown;
}

interface DAGViewProps {
  dagStructure: DAGStructure | null;
  nodeStatuses: Record<string, string>;
  iteration: number;
  maxIterations: number;
  events: SSEEvent[];
}

const STATUS_COLORS: Record<string, string> = {
  pending: "#6b7280",
  running: "#3b82f6",
  completed: "#10b981",
  failed: "#ef4444",
};

const AGENT_ICONS: Record<string, string> = {
  searcher: "S",
  reader: "R",
  synthesizer: "Y",
  critic: "C",
};

export default function DAGView({
  dagStructure,
  nodeStatuses,
  iteration,
  maxIterations,
  events,
}: DAGViewProps) {
  if (!dagStructure && events.length === 0) return null;

  // Group nodes by type for layout
  const searchers = dagStructure?.nodes.filter((n) => n.type === "searcher") ?? [];
  const readers = dagStructure?.nodes.filter((n) => n.type === "reader") ?? [];
  const others = dagStructure?.nodes.filter(
    (n) => n.type !== "searcher" && n.type !== "reader"
  ) ?? [];

  return (
    <div className="dag-view">
      <div className="dag-header">
        <h2>Research DAG</h2>
        <span className="iteration-badge">
          Iteration {iteration}/{maxIterations}
        </span>
      </div>

      {dagStructure ? (
        <div className="dag-graph">
          {/* Planner seed (always completed at this point) */}
          <div className="dag-layer">
            <div
              className="dag-node"
              style={{ borderColor: "#10b981" }}
            >
              <span className="node-icon">P</span>
              <span className="node-label">Planner</span>
            </div>
          </div>

          {/* Searchers layer */}
          {searchers.length > 0 && (
            <div className="dag-layer">
              {searchers.map((node) => (
                <div
                  key={node.id}
                  className={`dag-node ${nodeStatuses[node.id] || "pending"}`}
                  style={{
                    borderColor: STATUS_COLORS[nodeStatuses[node.id] || "pending"],
                  }}
                >
                  <span className="node-icon">
                    {AGENT_ICONS[node.type] || "?"}
                  </span>
                  <span className="node-label" title={node.label}>
                    {node.label.length > 30
                      ? node.label.slice(0, 30) + "..."
                      : node.label}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Readers layer */}
          {readers.length > 0 && (
            <div className="dag-layer">
              {readers.map((node) => (
                <div
                  key={node.id}
                  className={`dag-node ${nodeStatuses[node.id] || "pending"}`}
                  style={{
                    borderColor: STATUS_COLORS[nodeStatuses[node.id] || "pending"],
                  }}
                >
                  <span className="node-icon">
                    {AGENT_ICONS[node.type] || "?"}
                  </span>
                  <span className="node-label" title={node.label}>
                    {node.label.length > 30
                      ? node.label.slice(0, 30) + "..."
                      : node.label}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Synthesizer + Critic layer */}
          {others.length > 0 && (
            <div className="dag-layer">
              {others.map((node) => (
                <div
                  key={node.id}
                  className={`dag-node ${nodeStatuses[node.id] || "pending"}`}
                  style={{
                    borderColor: STATUS_COLORS[nodeStatuses[node.id] || "pending"],
                  }}
                >
                  <span className="node-icon">
                    {AGENT_ICONS[node.type] || "?"}
                  </span>
                  <span className="node-label">{node.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="dag-loading">Preparing research plan...</div>
      )}

      {/* Event log */}
      <div className="event-log">
        {events.slice(-8).map((event, i) => (
          <div key={i} className={`event-item event-${event.type}`}>
            <span className="event-type">{event.type}</span>
            <span className="event-msg">
              {(event.agent as string) || (event.node_id as string) || ""}{" "}
              {(event.message as string) || (event.summary as string) || ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
