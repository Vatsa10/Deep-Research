interface SourceCardProps {
  url: string;
  title: string;
  relevance?: number;
}

export default function SourceCard({ url, title, relevance }: SourceCardProps) {
  const domain = new URL(url).hostname.replace("www.", "");

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="source-card"
    >
      <div className="source-domain">{domain}</div>
      <div className="source-title">{title || url}</div>
      {relevance !== undefined && (
        <div className="source-relevance">
          Relevance: {(relevance * 100).toFixed(0)}%
        </div>
      )}
    </a>
  );
}
