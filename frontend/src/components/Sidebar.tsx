import { useState, useEffect } from "react";
import { getAuthHeaders } from "../hooks/useAuth";

interface Chat {
  session_id: string;
  query: string;
  status: string;
  created_at: string;
}

interface SidebarProps {
  activeId: string | null;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
  user: { name: string; email: string } | null;
  onLogout: () => void;
  refreshKey: number;
}

export default function Sidebar({
  activeId,
  onSelect,
  onNewChat,
  user,
  onLogout,
  refreshKey,
}: SidebarProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/history?limit=50", { headers: getAuthHeaders() })
      .then((r) => (r.ok ? r.json() : { sessions: [] }))
      .then((d) => setChats(d.sessions || []))
      .catch(() => {});
  }, [refreshKey]);

  const filtered = search
    ? chats.filter((c) =>
        c.query.toLowerCase().includes(search.toLowerCase())
      )
    : chats;

  const initials = user
    ? (user.name || user.email)
        .split(/[\s@]/)
        .filter(Boolean)
        .slice(0, 2)
        .map((s) => s[0].toUpperCase())
        .join("")
    : "?";

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <button className="new-chat-btn" onClick={onNewChat} type="button">
          + New Research
        </button>
      </div>

      <div className="sidebar-search">
        <input
          type="text"
          placeholder="Search chats..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="sidebar-list">
        {filtered.length === 0 ? (
          <div className="sidebar-empty">
            {search ? "No matches" : "No research yet"}
          </div>
        ) : (
          filtered.map((chat) => (
            <button
              key={chat.session_id}
              className={`sidebar-item ${activeId === chat.session_id ? "active" : ""}`}
              onClick={() => onSelect(chat.session_id)}
              type="button"
            >
              <div className="sidebar-item-title">{chat.query}</div>
              <div className="sidebar-item-meta">
                {new Date(chat.created_at).toLocaleDateString()}
              </div>
            </button>
          ))
        )}
      </div>

      {user && (
        <div className="sidebar-footer">
          <div className="sidebar-avatar">{initials}</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">{user.name || "User"}</div>
            <div className="sidebar-user-email">{user.email}</div>
          </div>
          <button className="sidebar-logout" onClick={onLogout} type="button">
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
