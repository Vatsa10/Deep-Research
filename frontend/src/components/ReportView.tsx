import ReactMarkdown from "react-markdown";

interface ReportViewProps {
  report: string;
}

export default function ReportView({ report }: ReportViewProps) {
  return (
    <div className="report-view">
      <h2>Research Report</h2>
      <div className="report-content">
        <ReactMarkdown
          components={{
            a: ({ href, children }) => (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {report}
        </ReactMarkdown>
      </div>
    </div>
  );
}
