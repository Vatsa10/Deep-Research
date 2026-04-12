import { useState, useRef, useEffect } from "react";

interface ChatInputProps {
  onSend: (query: string, depth: string) => void;
  isLoading: boolean;
  isContinued?: boolean;
}

const DEPTHS = ["quick", "standard", "deep"] as const;

export default function ChatInput({ onSend, isLoading, isContinued }: ChatInputProps) {
  const [text, setText] = useState("");
  const [depth, setDepth] = useState<string>(isContinued ? "standard" : "standard");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isLoading) ref.current?.focus();
  }, [isLoading]);

  const handleSubmit = () => {
    if (text.trim() && !isLoading) {
      onSend(text.trim(), depth);
      setText("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  };

  // For continued responses: only Quick and Standard
  const availableDepths = isContinued
    ? (["quick", "standard"] as const)
    : DEPTHS;

  return (
    <div className="chat-input-bar">
      <div className="chat-input-row">
        <div className="chat-input-wrapper">
          <textarea
            ref={ref}
            className="chat-input"
            value={text}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={
              isContinued
                ? "Ask a follow-up question..."
                : "What would you like to research?"
            }
            disabled={isLoading}
            rows={1}
          />
          <div className="depth-pills">
            {availableDepths.map((d) => (
              <button
                key={d}
                type="button"
                className={`depth-pill ${depth === d ? "active" : ""}`}
                onClick={() => setDepth(d)}
                disabled={isLoading}
              >
                {d[0].toUpperCase() + d.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <button
          className="send-btn"
          onClick={handleSubmit}
          disabled={!text.trim() || isLoading}
          type="button"
        >
          {isLoading ? "\u2026" : "\u2192"}
        </button>
      </div>
    </div>
  );
}
