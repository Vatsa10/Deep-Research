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

interface DAGInlineProps {
  dagStructure: DAGStructure | null;
  nodeStatuses: Record<string, string>;
  iteration: number;
  maxIterations: number;
  events: SSEEvent[];
}

const ICONS: Record<string, string> = {
  web_agent: "W",
  searcher: "S",
  reader: "R",
  synthesizer: "Y",
  distiller: "D",
  critic: "C",
};

export default function DAGInline({
  dagStructure,
  nodeStatuses,
  iteration,
  maxIterations,
  events,
}: DAGInlineProps) {
  if (!dagStructure && events.length === 0) return null;

  const webAgents = dagStructure?.nodes.filter((n) => n.type === "web_agent") ?? [];
  const searchers = dagStructure?.nodes.filter((n) => n.type === "searcher") ?? [];
  const readers = dagStructure?.nodes.filter((n) => n.type === "reader") ?? [];
  const others = dagStructure?.nodes.filter(
    (n) => n.type !== "searcher" && n.type !== "reader"
  ) ?? [];

  const renderNode = (node: DAGNode) => {
    const status = nodeStatuses[node.id] || "pending";
    return (
      <div key={node.id} className={`dag-node ${status}`}>
        <span className="node-icon">{ICONS[node.type] || "?"}</span>
        <span className="node-label" title={node.label}>
          {node.label.length > 30 ? node.label.slice(0, 30) + "\u2026" : node.label}
        </span>
      </div>
    );
  };

  const recent = events.filter((e) => e.type !== "keepalive").slice(-5);

  return (
    <div className="dag-inline">
      <div className="dag-inline-header">
        <span className="dag-inline-title">Research Pipeline</span>
        <span className="dag-badge">Pass {iteration}/{maxIterations}</span>
      </div>

      {dagStructure ? (
        <div className="dag-layers">
          <div className="dag-layer">
            <div className="dag-node completed">
              <span className="node-icon">P</span>
              <span className="node-label">Planner</span>
            </div>
          </div>
          {webAgents.length > 0 && <div className="dag-layer">{webAgents.map(renderNode)}</div>}
          {searchers.length > 0 && <div className="dag-layer">{searchers.map(renderNode)}</div>}
          {readers.length > 0 && <div className="dag-layer">{readers.map(renderNode)}</div>}
          {others.length > 0 && <div className="dag-layer">{others.map(renderNode)}</div>}
        </div>
      ) : (
        <div className="loading-dots"><span /><span /><span /></div>
      )}

      {recent.length > 0 && (
        <div className="event-log">
          {recent.map((ev, i) => (
            <div key={i} className={`event-item event-${ev.type}`}>
              <span className="event-type">{ev.type}</span>
              <span className="event-msg">
                {(ev.agent as string) || (ev.node_id as string) || ""}{" "}
                {(ev.message as string) || (ev.summary as string) || ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
