import { useRef, useEffect, useState } from "react";

interface ArtifactFrameProps {
  html: string;
  title?: string;
}

/**
 * Renders user-generated HTML/JS/CSS in a sandboxed iframe.
 * Isolated from the main page — safe for dynamic content.
 */
export default function ArtifactFrame({ html, title = "Visualization" }: ArtifactFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(320);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;

    const fullHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      margin: 0;
      padding: 16px;
      font-family: 'Inter', -apple-system, sans-serif;
      color: #0f172a;
      background: #fff;
    }
  </style>
</head>
<body>${html}</body>
<script>
  // Auto-resize: tell parent the content height
  const ro = new ResizeObserver(() => {
    window.parent.postMessage({ type: 'resize', height: document.body.scrollHeight + 32 }, '*');
  });
  ro.observe(document.body);
</script>
</html>`;

    doc.open();
    doc.write(fullHtml);
    doc.close();
  }, [html]);

  // Listen for resize messages from the iframe
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === "resize" && typeof e.data.height === "number") {
        setHeight(Math.min(e.data.height, 600));
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  return (
    <div className="artifact-frame">
      <div className="artifact-header">
        <span>{title}</span>
      </div>
      <iframe
        ref={iframeRef}
        className="artifact-iframe"
        style={{ height }}
        sandbox="allow-scripts"
        title={title}
      />
    </div>
  );
}
