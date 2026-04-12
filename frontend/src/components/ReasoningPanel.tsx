import { useState } from "react";

interface ReasoningStep {
  agent: string;
  action: string;
  output_summary: string;
  decisions: string[];
}

interface FactCheck {
  total: number;
  verified: number;
  dead: number;
}

interface ReasoningPanelProps {
  validation: Record<string, unknown> | null;
  factCheck: FactCheck | null;
  reasoningTrace: ReasoningStep[];
}

export default function ReasoningPanel({
  validation,
  factCheck,
  reasoningTrace,
}: ReasoningPanelProps) {
  const [open, setOpen] = useState(false);
  if (!validation && !factCheck && reasoningTrace.length === 0) return null;

  return (
    <div className="reasoning-panel">
      <button className="reasoning-toggle" onClick={() => setOpen(!open)} type="button">
        <span className="reasoning-toggle-icon">{open ? "\u25BC" : "\u25B6"}</span>
        <span>How we reached this conclusion</span>
        {factCheck && factCheck.total > 0 && (
          <span className="fact-badge">
            {factCheck.verified}/{factCheck.total} verified
            {factCheck.dead > 0 && <span className="dead"> ({factCheck.dead} dead)</span>}
          </span>
        )}
      </button>

      {open && (
        <div className="reasoning-body">
          {validation && (
            <div className="reasoning-section">
              <h4>Premise Validation</h4>
              <p style={{ fontSize: "0.82rem", color: validation.is_valid ? "var(--green)" : "var(--amber)" }}>
                {validation.is_valid ? "Query premise is valid" : "Premise concerns detected"}
              </p>
              {(validation.concerns as string[])?.length > 0 && (
                <ul style={{ paddingLeft: 16, marginTop: 4, fontSize: "0.78rem", color: "var(--amber)" }}>
                  {(validation.concerns as string[]).map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              )}
            </div>
          )}

          {reasoningTrace.length > 0 && (
            <div className="reasoning-section">
              <h4>Reasoning Chain</h4>
              {reasoningTrace.map((step, i) => (
                <div key={i} className="trace-step">
                  <div className="trace-agent">{step.agent}</div>
                  <div className="trace-action">{step.action}</div>
                  <div className="trace-output">{step.output_summary}</div>
                </div>
              ))}
            </div>
          )}

          {factCheck && factCheck.total > 0 && (
            <div className="reasoning-section">
              <h4>Citation Verification</h4>
              <div className="fact-grid">
                <div className="fact-stat">
                  <span className="fact-number">{factCheck.total}</span>
                  <span className="fact-label">Total</span>
                </div>
                <div className="fact-stat ok">
                  <span className="fact-number">{factCheck.verified}</span>
                  <span className="fact-label">Verified</span>
                </div>
                <div className={`fact-stat ${factCheck.dead > 0 ? "bad" : ""}`}>
                  <span className="fact-number">{factCheck.dead}</span>
                  <span className="fact-label">Dead</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
