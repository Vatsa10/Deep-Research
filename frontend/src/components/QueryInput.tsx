import { useState, useRef, useEffect } from "react";

interface QueryInputProps {
  onSubmit: (query: string, depth: string) => void;
  isLoading: boolean;
}

const DEPTHS = [
  { id: "quick", label: "Quick", desc: "~5 sources, 1 pass" },
  { id: "standard", label: "Standard", desc: "~12 sources, 2 passes" },
  { id: "deep", label: "Deep", desc: "~20 sources, 3 passes" },
] as const;

export default function QueryInput({ onSubmit, isLoading }: QueryInputProps) {
  const [query, setQuery] = useState("");
  const [depth, setDepth] = useState("standard");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query.trim(), depth);
    }
  };

  // Ctrl/Cmd+Enter to submit
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      handleSubmit(e);
    }
  };

  return (
    <form className="query-input" onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="What would you like to research?"
        rows={3}
        disabled={isLoading}
      />
      <div className="query-controls">
        <div className="depth-selector">
          <label>Depth</label>
          {DEPTHS.map((d) => (
            <button
              key={d.id}
              type="button"
              className={`depth-btn ${depth === d.id ? "active" : ""}`}
              onClick={() => setDepth(d.id)}
              disabled={isLoading}
              title={d.desc}
            >
              {d.label}
            </button>
          ))}
        </div>
        <button
          type="submit"
          className="submit-btn"
          disabled={!query.trim() || isLoading}
        >
          {isLoading ? "Researching\u2026" : "Research"}
        </button>
      </div>
    </form>
  );
}
