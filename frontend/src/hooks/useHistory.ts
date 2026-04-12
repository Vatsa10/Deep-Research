import { useState, useCallback } from "react";
import { getAuthHeaders } from "./useAuth";

interface SessionSummary {
  session_id: string;
  query: string;
  depth: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  continued_from: string | null;
}

export function useHistory() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchHistory = useCallback(
    async (limit = 20, offset = 0) => {
      setIsLoading(true);
      try {
        const res = await fetch(
          `/api/history?limit=${limit}&offset=${offset}`,
          { headers: getAuthHeaders() }
        );
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions);
        }
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return { sessions, isLoading, fetchHistory };
}
