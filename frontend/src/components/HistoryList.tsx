import { useEffect } from "react";
import { useHistory } from "../hooks/useHistory";

interface HistoryListProps {
  onSelect: (sessionId: string) => void;
  onBack: () => void;
}

export default function HistoryList({ onSelect, onBack }: HistoryListProps) {
  const { sessions, isLoading, fetchHistory } = useHistory();

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return (
    <div className="history-panel">
      <div className="history-header">
        <button className="back-btn" onClick={onBack} type="button">
          \u2190 Back
        </button>
        <h2>Research History</h2>
      </div>

      {isLoading ? (
        <div className="history-loading">Loading...</div>
      ) : sessions.length === 0 ? (
        <div className="history-empty">
          No research yet. Start your first one!
        </div>
      ) : (
        <div className="history-list">
          {sessions.map((s) => (
            <button
              key={s.session_id}
              className="history-item"
              onClick={() => onSelect(s.session_id)}
              type="button"
            >
              <div className="history-query">{s.query}</div>
              <div className="history-meta">
                <span className={`history-status ${s.status}`}>
                  {s.status}
                </span>
                <span className="history-depth">{s.depth}</span>
                <span className="history-date">
                  {new Date(s.created_at).toLocaleDateString()}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
