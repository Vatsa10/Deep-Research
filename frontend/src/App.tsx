import { useState } from "react";
import { useAuth } from "./hooks/useAuth";
import { useResearch } from "./hooks/useResearch";
import AuthModal from "./components/AuthModal";
import UserMenu from "./components/UserMenu";
import QueryInput from "./components/QueryInput";
import TemplateSelector from "./components/TemplateSelector";
import DAGView from "./components/DAGView";
import ReportView from "./components/ReportView";
import ReasoningView from "./components/ReasoningView";
import ShareModal from "./components/ShareModal";
import FollowUpChat from "./components/FollowUpChat";
import HistoryList from "./components/HistoryList";
import SharedView from "./pages/SharedView";

type Page = "research" | "history";

export default function App() {
  // Check if viewing a shared research link
  const path = window.location.pathname;
  const sharedMatch = path.match(/^\/shared\/(.+)$/);
  if (sharedMatch) {
    return <SharedView token={sharedMatch[1]} />;
  }

  return <MainApp />;
}

function MainApp() {
  const auth = useAuth();
  const { state, startResearch, exportResearch, loadSession } = useResearch();
  const [page, setPage] = useState<Page>("research");
  const [showShare, setShowShare] = useState(false);

  // Show auth modal if not logged in
  if (auth.isLoading) {
    return (
      <div className="app">
        <div className="dag-loading">Loading</div>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="app">
        <header className="header">
          <h1>
            <span>Deep Research</span>
          </h1>
          <p className="subtitle">
            Multi-agent research with source credibility, fact-checking, and
            transparent reasoning
          </p>
        </header>
        <AuthModal onLogin={auth.login} onRegister={auth.register} />
      </div>
    );
  }

  const handleHistorySelect = (sessionId: string) => {
    loadSession(sessionId);
    setPage("research");
  };

  const handleFollowUp = (newSessionId: string) => {
    loadSession(newSessionId);
  };

  const handleTemplateSelect = (query: string, depth: string) => {
    startResearch(query, depth);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-row">
          <h1>
            <span>Deep Research</span>
          </h1>
          <UserMenu
            name={auth.user?.name || ""}
            email={auth.user?.email || ""}
            onLogout={auth.logout}
            onHistory={() => setPage("history")}
          />
        </div>
        <p className="subtitle">
          Multi-agent research with source credibility, fact-checking, and
          transparent reasoning
        </p>
      </header>

      <main>
        {page === "history" ? (
          <HistoryList
            onSelect={handleHistorySelect}
            onBack={() => setPage("research")}
          />
        ) : (
          <>
            <TemplateSelector onSelect={handleTemplateSelect} />

            <QueryInput
              onSubmit={startResearch}
              isLoading={state.status === "running"}
            />

            {state.status !== "idle" && (
              <div className="results">
                {state.error && (
                  <div className="error-banner">{state.error}</div>
                )}

                <DAGView
                  dagStructure={state.dagStructure}
                  nodeStatuses={state.nodeStatuses}
                  iteration={state.iteration}
                  maxIterations={state.maxIterations}
                  events={state.events}
                />

                {state.report && (
                  <>
                    <ReportView report={state.report} />

                    <ReasoningView
                      validation={state.validation}
                      factCheck={state.factCheck}
                      reasoningTrace={state.reasoningTrace}
                    />

                    {state.status === "completed" && state.sessionId && (
                      <>
                        <FollowUpChat
                          sessionId={state.sessionId}
                          onNewResearch={handleFollowUp}
                        />

                        <div className="export-bar">
                          <button
                            className="export-btn"
                            onClick={() => setShowShare(true)}
                            type="button"
                          >
                            Share
                          </button>
                          <button
                            className="export-btn"
                            onClick={exportResearch}
                            type="button"
                          >
                            Export JSON
                          </button>
                        </div>

                        {showShare && (
                          <ShareModal
                            sessionId={state.sessionId}
                            onClose={() => setShowShare(false)}
                          />
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
