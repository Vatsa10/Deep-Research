import { useState } from "react";
import { getAuthHeaders } from "../hooks/useAuth";

interface FollowUpChatProps {
  sessionId: string;
  onNewResearch: (sessionId: string) => void;
}

export default function FollowUpChat({
  sessionId,
  onNewResearch,
}: FollowUpChatProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    try {
      const res = await fetch(`/api/research/${sessionId}/continue`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ query: query.trim(), depth: "standard" }),
      });
      if (res.ok) {
        const data = await res.json();
        onNewResearch(data.session_id);
        setQuery("");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="followup-chat" onSubmit={handleSubmit}>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask a follow-up question..."
        className="followup-input"
        disabled={loading}
      />
      <button
        type="submit"
        className="followup-btn"
        disabled={!query.trim() || loading}
      >
        {loading ? "\u2026" : "\u2192"}
      </button>
    </form>
  );
}
