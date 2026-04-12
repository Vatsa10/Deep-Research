import { useState, useEffect } from "react";

interface Template {
  id: string;
  name: string;
  description: string;
  query_pattern: string;
  depth: string;
}

interface WelcomeScreenProps {
  onStartResearch: (query: string, depth: string) => void;
}

export default function WelcomeScreen({ onStartResearch }: WelcomeScreenProps) {
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    fetch("/api/templates/public")
      .then((r) => r.json())
      .then(setTemplates)
      .catch(() => {});
  }, []);

  const handleTemplate = (t: Template) => {
    const topic = prompt(`Enter a topic for "${t.name}":`);
    if (topic?.trim()) {
      const query = t.query_pattern.replace("{topic}", topic.trim());
      onStartResearch(query, t.depth);
    }
  };

  return (
    <div className="welcome-screen">
      <h1 className="welcome-title">
        <em>Deep Research</em>
      </h1>
      <p className="welcome-subtitle">
        What would you like to research today?
      </p>

      {templates.length > 0 && (
        <div className="template-grid">
          {templates.map((t) => (
            <button
              key={t.id}
              className="template-card"
              onClick={() => handleTemplate(t)}
              type="button"
            >
              <div className="template-name">{t.name}</div>
              <div className="template-desc">{t.description}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
