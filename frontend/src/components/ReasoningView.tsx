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

interface ReasoningViewProps {
  validation: Record<string, unknown> | null;
  factCheck: FactCheck | null;
  reasoningTrace: ReasoningStep[];
}

export default function ReasoningView({
  validation,
  factCheck,
  reasoningTrace,
}: ReasoningViewProps) {
  const [expanded, setExpanded] = useState(false);

  const hasContent = validation || factCheck || reasoningTrace.length > 0;
  if (!hasContent) return null;

  return (
    <div className="reasoning-view">
      <button
        className="reasoning-toggle"
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <span className="reasoning-toggle-icon">
          {expanded ? "\u25BC" : "\u25B6"}
        </span>
        <span>How we reached this conclusion</span>
        {factCheck && factCheck.total > 0 && (
          <span className="fact-check-badge">
            {factCheck.verified}/{factCheck.total} citations verified
            {factCheck.dead > 0 && (
              <span className="dead-links"> ({factCheck.dead} dead)</span>
            )}
          </span>
        )}
      </button>

      {expanded && (
        <div className="reasoning-content">
          {/* Premise Validation */}
          {validation && (
            <div className="reasoning-section">
              <h4>Premise Validation</h4>
              <div className={`validation-status ${validation.is_valid ? "valid" : "flagged"}`}>
                {validation.is_valid ? "Query premise is valid" : "Premise concerns detected"}
              </div>
              {(validation.concerns as string[])?.length > 0 && (
                <ul className="concern-list">
                  {(validation.concerns as string[]).map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              )}
              {validation.rewritten_query && (
                <div className="rewritten-query">
                  Rewritten as: <em>{validation.rewritten_query as string}</em>
                </div>
              )}
            </div>
          )}

          {/* Reasoning Trace */}
          {reasoningTrace.length > 0 && (
            <div className="reasoning-section">
              <h4>Reasoning Chain</h4>
              <div className="trace-steps">
                {reasoningTrace.map((step, i) => (
                  <div key={i} className="trace-step">
                    <div className="trace-agent">{step.agent}</div>
                    <div className="trace-action">{step.action}</div>
                    <div className="trace-output">{step.output_summary}</div>
                    {step.decisions.length > 0 && (
                      <ul className="trace-decisions">
                        {step.decisions.map((d, j) => (
                          <li key={j}>{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fact Check */}
          {factCheck && factCheck.total > 0 && (
            <div className="reasoning-section">
              <h4>Citation Verification</h4>
              <div className="fact-check-grid">
                <div className="fact-stat">
                  <span className="fact-number">{factCheck.total}</span>
                  <span className="fact-label">Total citations</span>
                </div>
                <div className="fact-stat verified">
                  <span className="fact-number">{factCheck.verified}</span>
                  <span className="fact-label">Verified</span>
                </div>
                <div className={`fact-stat ${factCheck.dead > 0 ? "dead" : ""}`}>
                  <span className="fact-number">{factCheck.dead}</span>
                  <span className="fact-label">Dead links</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
