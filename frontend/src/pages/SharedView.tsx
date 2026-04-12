import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";

interface SharedViewProps {
  token: string;
}

interface SharedData {
  query: string;
  report: string;
  distilled_summary: string;
  iterations: number;
  created_at: string;
  view_count: number;
}

export default function SharedView({ token }: SharedViewProps) {
  const [data, setData] = useState<SharedData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`/api/shared/${token}`)
      .then((r) => {
        if (!r.ok) throw new Error("Research not found");
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [token]);

  if (error) {
    return (
      <div className="shared-page">
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="shared-page">
        <div className="dag-loading">Loading shared research</div>
      </div>
    );
  }

  return (
    <div className="shared-page">
      <header className="shared-header">
        <div className="shared-badge">Shared Research</div>
        <h1>{data.query}</h1>
        <div className="shared-meta">
          {new Date(data.created_at).toLocaleDateString()} &middot;{" "}
          {data.iterations} iteration{data.iterations !== 1 ? "s" : ""} &middot;{" "}
          {data.view_count} view{data.view_count !== 1 ? "s" : ""}
        </div>
      </header>

      <div className="report-view">
        <div className="report-content">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {data.report}
          </ReactMarkdown>
        </div>
      </div>

      <div className="shared-cta">
        <a href="/" className="submit-btn">
          Try Deep Research yourself
        </a>
      </div>
    </div>
  );
}
