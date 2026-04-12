import QueryInput from "./components/QueryInput";
import DAGView from "./components/DAGView";
import ReportView from "./components/ReportView";
import ReasoningView from "./components/ReasoningView";
import { useResearch } from "./hooks/useResearch";

export default function App() {
  const { state, startResearch, exportResearch } = useResearch();

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

      <main>
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

                {state.status === "completed" && (
                  <div className="export-bar">
                    <button
                      className="export-btn"
                      onClick={exportResearch}
                      type="button"
                    >
                      Export Research Artifact
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
