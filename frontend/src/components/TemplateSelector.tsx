import { useState, useEffect } from "react";

interface Template {
  id: string;
  name: string;
  description: string;
  query_pattern: string;
  depth: string;
  domain: string;
  is_builtin: boolean;
}

interface TemplateSelectorProps {
  onSelect: (query: string, depth: string) => void;
}

export default function TemplateSelector({ onSelect }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<Template | null>(null);

  useEffect(() => {
    fetch("/api/templates/public")
      .then((r) => r.json())
      .then(setTemplates)
      .catch(() => {});
  }, []);

  if (templates.length === 0) return null;

  const handleUse = () => {
    if (selected && topic.trim()) {
      const query = selected.query_pattern.replace("{topic}", topic.trim());
      onSelect(query, selected.depth);
      setSelected(null);
      setTopic("");
    }
  };

  return (
    <div className="template-selector">
      <div className="template-label">Quick start with a template</div>
      <div className="template-grid">
        {templates.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`template-card ${selected?.id === t.id ? "active" : ""}`}
            onClick={() => setSelected(selected?.id === t.id ? null : t)}
          >
            <div className="template-name">{t.name}</div>
            <div className="template-desc">{t.description}</div>
          </button>
        ))}
      </div>

      {selected && (
        <div className="template-input-row">
          <input
            type="text"
            placeholder={`Enter topic for "${selected.name}"...`}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="template-topic-input"
            onKeyDown={(e) => e.key === "Enter" && handleUse()}
          />
          <button
            type="button"
            className="submit-btn"
            onClick={handleUse}
            disabled={!topic.trim()}
          >
            Research
          </button>
        </div>
      )}
    </div>
  );
}
