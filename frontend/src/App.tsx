import QueryInput from "./components/QueryInput";
import DAGView from "./components/DAGView";
import ReportView from "./components/ReportView";
import { useResearch } from "./hooks/useResearch";

export default function App() {
  const { state, startResearch } = useResearch();

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span>Deep Research</span>
        </h1>
        <p className="subtitle">
          Multi-agent research powered by async DAG execution
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

            {state.report && <ReportView report={state.report} />}
          </div>
        )}
      </main>
    </div>
  );
}
