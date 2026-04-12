import { useState, useRef, useEffect } from "react";

interface UserMenuProps {
  name: string;
  email: string;
  onLogout: () => void;
  onHistory: () => void;
}

export default function UserMenu({
  name,
  email,
  onLogout,
  onHistory,
}: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const initials = (name || email)
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join("");

  return (
    <div className="user-menu" ref={ref}>
      <button
        className="user-avatar"
        onClick={() => setOpen(!open)}
        type="button"
      >
        {initials}
      </button>

      {open && (
        <div className="user-dropdown">
          <div className="user-dropdown-header">
            <div className="user-dropdown-name">{name || "User"}</div>
            <div className="user-dropdown-email">{email}</div>
          </div>
          <div className="user-dropdown-divider" />
          <button
            className="user-dropdown-item"
            onClick={() => { onHistory(); setOpen(false); }}
            type="button"
          >
            Research History
          </button>
          <button
            className="user-dropdown-item user-dropdown-logout"
            onClick={onLogout}
            type="button"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
