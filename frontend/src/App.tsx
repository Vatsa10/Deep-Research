import { useState, useRef, useEffect } from "react";
import { useAuth } from "./hooks/useAuth";
import { useResearch } from "./hooks/useResearch";
import AuthModal from "./components/AuthModal";
import Sidebar from "./components/Sidebar";
import WelcomeScreen from "./components/WelcomeScreen";
import ChatInput from "./components/ChatInput";
import MessageBubble from "./components/MessageBubble";
import DAGInline from "./components/DAGInline";
import ReasoningPanel from "./components/ReasoningPanel";
import ShareModal from "./components/ShareModal";
import SharedView from "./pages/SharedView";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export default function App() {
  // Handle /shared/:token routes
  const path = window.location.pathname;
  const sharedMatch = path.match(/^\/shared\/(.+)$/);
  if (sharedMatch) return <SharedView token={sharedMatch[1]} />;

  return <MainApp />;
}

function MainApp() {
  const auth = useAuth();
  const research = useResearch();
  const { state } = research;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showShare, setShowShare] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, state.report, state.events.length]);

  // When research completes, add assistant message
  useEffect(() => {
    if (state.status === "completed" && state.report) {
      setMessages((prev) => {
        // Don't duplicate if already added
        if (prev.length > 0 && prev[prev.length - 1].content === state.report) return prev;
        return [...prev, { role: "assistant", content: state.report! }];
      });
      setSidebarRefresh((n) => n + 1);
    }
  }, [state.status, state.report]);

  if (auth.isLoading) {
    return (
      <div className="auth-overlay">
        <div className="loading-dots"><span /><span /><span /></div>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return <AuthModal onLogin={auth.login} onRegister={auth.register} />;
  }

  const handleNewChat = () => {
    setMessages([]);
    setActiveSessionId(null);
    research.reset();
  };

  const handleSend = (query: string, depth: string) => {
    setMessages((prev) => [...prev, { role: "user", content: query }]);

    if (activeSessionId && state.status === "completed") {
      // Continued research — enforce Quick/Standard
      const safeDepth = depth === "deep" ? "standard" : depth;
      research.continueResearch(activeSessionId, query, safeDepth);
    } else {
      research.startResearch(query, depth);
    }
  };

  // When a new session starts, track it
  useEffect(() => {
    if (state.sessionId && state.sessionId !== activeSessionId) {
      setActiveSessionId(state.sessionId);
    }
  }, [state.sessionId]);

  const handleSelectChat = async (sessionId: string) => {
    setMessages([]);
    setActiveSessionId(sessionId);
    research.reset();

    // Load from API
    const data = await research.loadSession(sessionId);
    if (data) {
      setMessages([
        { role: "user", content: data.query },
        ...(data.report ? [{ role: "assistant" as const, content: data.report }] : []),
      ]);
    }
  };

  const isNewChat = messages.length === 0 && state.status === "idle";
  const isRunning = state.status === "running";

  return (
    <div className="app-layout">
      <Sidebar
        activeId={activeSessionId}
        onSelect={handleSelectChat}
        onNewChat={handleNewChat}
        user={auth.user}
        onLogout={auth.logout}
        refreshKey={sidebarRefresh}
      />

      <div className="chat-area">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-title">
            {isNewChat ? "New Research" : (messages[0]?.content.slice(0, 60) || "Research")}
          </div>
          {activeSessionId && state.status === "completed" && (
            <div className="chat-actions">
              <button
                className="chat-action-btn"
                onClick={() => setShowShare(true)}
                type="button"
              >
                Share
              </button>
              <button
                className="chat-action-btn"
                onClick={() => research.exportResearch()}
                type="button"
              >
                Export
              </button>
            </div>
          )}
        </div>

        {/* Messages or Welcome */}
        {isNewChat ? (
          <WelcomeScreen onStartResearch={handleSend} />
        ) : (
          <div className="chat-messages">
            {messages.map((msg, i) => (
              <MessageBubble key={i} role={msg.role} content={msg.content} />
            ))}

            {/* Show DAG while running */}
            {isRunning && (
              <div className="message message-assistant">
                <div className="message-label">Deep Research</div>
                <div className="message-content">
                  <DAGInline
                    dagStructure={state.dagStructure}
                    nodeStatuses={state.nodeStatuses}
                    iteration={state.iteration}
                    maxIterations={state.maxIterations}
                    events={state.events}
                  />
                  <div className="loading-dots"><span /><span /><span /></div>
                </div>
              </div>
            )}

            {/* Error */}
            {state.error && <div className="error-banner">{state.error}</div>}

            {/* Reasoning panel after completion */}
            {state.status === "completed" && (
              <ReasoningPanel
                validation={state.validation}
                factCheck={state.factCheck}
                reasoningTrace={state.reasoningTrace}
              />
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input bar — always visible unless on welcome screen */}
        {!isNewChat && (
          <ChatInput
            onSend={handleSend}
            isLoading={isRunning}
            isContinued={state.status === "completed"}
          />
        )}

        {/* Welcome screen has its own input area via templates */}
        {isNewChat && (
          <ChatInput
            onSend={handleSend}
            isLoading={false}
          />
        )}

        {/* Share modal */}
        {showShare && activeSessionId && (
          <ShareModal
            sessionId={activeSessionId}
            onClose={() => setShowShare(false)}
          />
        )}
      </div>
    </div>
  );
}
