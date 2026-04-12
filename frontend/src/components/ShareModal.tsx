import { useState } from "react";
import { getAuthHeaders } from "../hooks/useAuth";

interface ShareModalProps {
  sessionId: string;
  onClose: () => void;
}

export default function ShareModal({ sessionId, onClose }: ShareModalProps) {
  const [shareUrl, setShareUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const generateLink = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/research/${sessionId}/share`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        const url = `${window.location.origin}/shared/${data.share_token}`;
        setShareUrl(url);
      }
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Share Research</h3>
        <p className="modal-desc">
          Anyone with the link can view this research without signing in.
        </p>

        {!shareUrl ? (
          <button
            className="submit-btn"
            onClick={generateLink}
            disabled={loading}
            type="button"
          >
            {loading ? "Generating\u2026" : "Generate share link"}
          </button>
        ) : (
          <div className="share-link-box">
            <input
              type="text"
              value={shareUrl}
              readOnly
              className="share-link-input"
            />
            <button
              className="submit-btn"
              onClick={copyToClipboard}
              type="button"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        )}

        <button className="modal-close" onClick={onClose} type="button">
          Close
        </button>
      </div>
    </div>
  );
}
