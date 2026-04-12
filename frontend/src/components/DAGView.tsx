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

  const searchers =
    dagStructure?.nodes.filter((n) => n.type === "searcher") ?? [];
  const readers =
    dagStructure?.nodes.filter((n) => n.type === "reader") ?? [];
  const synthesizer =
    dagStructure?.nodes.filter((n) => n.type === "synthesizer") ?? [];
  const critic =
    dagStructure?.nodes.filter((n) => n.type === "critic") ?? [];

  const renderNode = (node: DAGNode) => {
    const status = nodeStatuses[node.id] || "pending";
    return (
      <div key={node.id} className={`dag-node ${status}`}>
        <span className="node-icon">
          {AGENT_ICONS[node.type] || "?"}
        </span>
        <span className="node-label" title={node.label}>
          {node.label.length > 35
            ? node.label.slice(0, 35) + "\u2026"
            : node.label}
        </span>
      </div>
    );
  };

  // Only show recent events
  const recentEvents = events.filter(
    (e) => e.type !== "keepalive"
  ).slice(-6);

  return (
    <div className="dag-view">
      <div className="dag-header">
        <h2>Research DAG</h2>
        <span className="iteration-badge">
          Pass {iteration}/{maxIterations}
        </span>
      </div>

      {dagStructure ? (
        <div className="dag-graph">
          {/* Planner (always done by this point) */}
          <div className="dag-layer">
            <div className="dag-node completed">
              <span className="node-icon">P</span>
              <span className="node-label">Planner</span>
            </div>
          </div>

          {searchers.length > 0 && (
            <div className="dag-layer">{searchers.map(renderNode)}</div>
          )}

          {readers.length > 0 && (
            <div className="dag-layer">{readers.map(renderNode)}</div>
          )}

          {(synthesizer.length > 0 || critic.length > 0) && (
            <div className="dag-layer">
              {synthesizer.map(renderNode)}
              {critic.map(renderNode)}
            </div>
          )}
        </div>
      ) : (
        <div className="dag-loading">Preparing research plan</div>
      )}

      {recentEvents.length > 0 && (
        <div className="event-log">
          {recentEvents.map((event, i) => (
            <div key={i} className={`event-item event-${event.type}`}>
              <span className="event-type">{event.type}</span>
              <span className="event-msg">
                {(event.agent as string) ||
                  (event.node_id as string) ||
                  ""}{" "}
                {(event.message as string) ||
                  (event.summary as string) ||
                  ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
