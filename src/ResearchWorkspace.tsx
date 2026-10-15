import { useState } from "react";
import { api, downloadResearchCsv, type ResearchSessionRow } from "./api";

const pilotRotation = [
  ["P01", "Static · Linear", "Rule-based · Binary", "Personalized · Bubble"],
  ["P02", "Rule-based · Bubble", "Personalized · Linear", "Static · Binary"],
  ["P03", "Personalized · Binary", "Static · Bubble", "Rule-based · Linear"],
];

export default function ResearchWorkspace({ onBack }: { onBack: () => void }) {
  const [token, setToken] = useState("");
  const [rows, setRows] = useState<ResearchSessionRow[]>([]);
  const [assignments, setAssignments] = useState<string[][]>(pilotRotation);
  const [modeFilter, setModeFilter] = useState("all");
  const [purposeFilter, setPurposeFilter] = useState("all");
  const [resetCode, setResetCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const visibleRows = rows.filter(
    (row) =>
      (modeFilter === "all" || row.mode === modeFilter) &&
      (purposeFilter === "all" || row.study_kind === purposeFilter),
  );
  async function load() {
    setBusy(true);
    setError("");
    try {
      const [nextRows, rotation] = await Promise.all([
        api.researchSessions(token),
        api.researchAssignments(token),
      ]);
      setRows(nextRows);
      setAssignments(
        rotation.assignments.map((row) => [
          row.participant_code,
          row.session_1,
          row.session_2,
          row.session_3,
        ]),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load research data");
    } finally {
      setBusy(false);
    }
  }
  async function reset() {
    if (!resetCode.trim()) return;
    setError("");
    try {
      await api.resetParticipant(token, resetCode.trim());
      setResetCode("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to reset history");
    }
  }
  return (
    <div className="shell results-shell">
      <header className="app-header">
        <div className="topline">
          <span className="logo-mark">↻</span>
          <span>LOOP / RESEARCH WORKSPACE</span>
        </div>
        <button className="ghost-button" onClick={onBack}>
          Back to lessons
        </button>
      </header>
      <main className="results-main research-main">
        <p className="eyebrow">RESEARCHER ACCESS</p>
        <h1>
          Session history
          <br />
          <em>with provenance.</em>
        </h1>
        <p className="lead">
          Filter and export stored observations. Synthetic demonstration records
          remain labelled in their data origin.
        </p>
        <label>
          Researcher credential
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="X-Researcher-Token"
          />
        </label>
        <div className="result-actions">
          <button
            className="primary-button"
            disabled={!token || busy}
            onClick={load}
          >
            {busy ? "Loading…" : "Load sessions"}
          </button>
          <button
            className="ghost-button"
            disabled={!token}
            onClick={() => downloadResearchCsv(token)}
          >
            Download study CSV
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        {rows.length > 0 && (
          <div className="research-tools">
            <label>
              Mode
              <select
                value={modeFilter}
                onChange={(e) => setModeFilter(e.target.value)}
              >
                <option value="all">All modes</option>
                <option value="static">Static</option>
                <option value="rule_based">Rule-based</option>
                <option value="personalized">Personalized</option>
              </select>
            </label>
            <label>
              Purpose
              <select
                value={purposeFilter}
                onChange={(e) => setPurposeFilter(e.target.value)}
              >
                <option value="all">All purposes</option>
                <option value="practice">Practice</option>
                <option value="study">Study</option>
              </select>
            </label>
            <label>
              Reset participant history
              <input
                value={resetCode}
                onChange={(e) => setResetCode(e.target.value)}
                placeholder="participant code"
              />
            </label>
            <button
              className="ghost-button"
              disabled={!token || !resetCode.trim()}
              onClick={reset}
            >
              Start new history boundary
            </button>
          </div>
        )}
        {token && (
          <details className="rotation-panel">
            <summary>Planned pilot assignment rotation</summary>
            <p className="muted">
              Protocol planning only. These rows are not participant
              observations.
            </p>
            <div className="research-table">
              <table>
                <thead>
                  <tr>
                    <th>Participant</th>
                    <th>Session 1</th>
                    <th>Session 2</th>
                    <th>Session 3</th>
                  </tr>
                </thead>
                <tbody>
                  {assignments.map((row) => (
                    <tr key={row[0]}>
                      {row.map((cell, index) => (
                        <td key={index}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
        <div className="research-table">
          {visibleRows.length ? (
            <table>
              <thead>
                <tr>
                  <th>Participant</th>
                  <th>Lesson</th>
                  <th>Mode</th>
                  <th>Purpose</th>
                  <th>Answers</th>
                  <th>Supports</th>
                  <th>Origin</th>
                  <th>Versions</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.session_id}>
                    <td>{row.participant_code}</td>
                    <td>{row.lesson_id}</td>
                    <td>{row.mode}</td>
                    <td>{row.study_kind}</td>
                    <td>{row.answer_count}</td>
                    <td>{row.intervention_count}</td>
                    <td>{row.data_origin}</td>
                    <td>
                      {row.content_version} / {row.policy_version}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">
              {rows.length
                ? "No sessions match these filters."
                : "No sessions loaded."}
            </p>
          )}
        </div>
      </main>
    </div>
  );
}

