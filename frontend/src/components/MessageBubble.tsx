import ReactMarkdown from "react-markdown";
import ArtifactFrame from "./ArtifactFrame";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
}

/**
 * Renders a single chat message.
 * - User messages: right-aligned blue bubble
 * - Assistant messages: full-width with markdown + optional HTML artifacts
 */
export default function MessageBubble({ role, content }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className="message message-user">
        <div className="message-content">{content}</div>
      </div>
    );
  }

  // Extract HTML artifacts from the response: ```html ... ```
  const { text, artifacts } = extractArtifacts(content);

  return (
    <div className="message message-assistant">
      <div className="message-label">Deep Research</div>
      <div className="message-content">
        <div className="report-md">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {text}
          </ReactMarkdown>
        </div>

        {artifacts.map((art, i) => (
          <ArtifactFrame
            key={i}
            html={art.html}
            title={art.title || `Visualization ${i + 1}`}
          />
        ))}
      </div>
    </div>
  );
}

interface Artifact {
  html: string;
  title: string;
}

function extractArtifacts(content: string): { text: string; artifacts: Artifact[] } {
  const artifacts: Artifact[] = [];
  const htmlBlockRegex = /```html\s*\n([\s\S]*?)```/g;

  let match;
  let cleanText = content;

  while ((match = htmlBlockRegex.exec(content)) !== null) {
    artifacts.push({
      html: match[1].trim(),
      title: "Interactive Visualization",
    });
  }

  // Remove HTML blocks from the markdown text
  cleanText = content.replace(htmlBlockRegex, "").trim();

  return { text: cleanText, artifacts };
}
