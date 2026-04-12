import { useState } from "react";

interface QueryInputProps {
  onSubmit: (query: string, depth: string) => void;
  isLoading: boolean;
}

export default function QueryInput({ onSubmit, isLoading }: QueryInputProps) {
  const [query, setQuery] = useState("");
  const [depth, setDepth] = useState("standard");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query.trim(), depth);
    }
  };

  return (
    <form className="query-input" onSubmit={handleSubmit}>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="What would you like to research? e.g., 'What are the latest advances in quantum computing?'"
        rows={3}
        disabled={isLoading}
      />
      <div className="query-controls">
        <div className="depth-selector">
          <label>Depth:</label>
          {["quick", "standard", "deep"].map((d) => (
            <button
              key={d}
              type="button"
              className={`depth-btn ${depth === d ? "active" : ""}`}
              onClick={() => setDepth(d)}
              disabled={isLoading}
            >
              {d.charAt(0).toUpperCase() + d.slice(1)}
            </button>
          ))}
        </div>
        <button
          type="submit"
          className="submit-btn"
          disabled={!query.trim() || isLoading}
        >
          {isLoading ? "Researching..." : "Research"}
        </button>
      </div>
    </form>
  );
}
