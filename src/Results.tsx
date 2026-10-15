import { useState } from "react";
import { api, downloadCsv, type AnswerRecord, type Lesson, type Session, type SessionDetail } from "./api";

export default function Results({
  session,
  lesson,
  detail,
  onStartSession,
  onExit,
}: {
  session: Session;
  lesson: Lesson;
  detail: SessionDetail | null;
  onStartSession: (session: Session) => void;
  onExit: () => void;
}) {
  const [retentionBusy, setRetentionBusy] = useState(false);
  const answers = detail?.answers || [];
  const pre = answers.filter((a) => a.phase === "pre");
  const checkpoint = answers.filter((a) => a.phase === "checkpoint");
  const post = answers.filter((a) => a.phase === "post");
  const correct = answers.filter((a) => a.correct).length;
  const interventions = detail?.interventions || [];
  const followUps = interventions.flatMap((i) => i.follow_ups || []);
  const events = detail?.events || [];
  const score = (items: AnswerRecord[]) =>
    items.length
      ? `${items.filter((a) => a.correct).length}/${items.length}`
      : "No score";
  const lifecycle = (status: string) =>
    interventions.filter((i) => i.status === status).length;
  const signalEvents = events.filter((e) => e.event_type === "signal_summary");
  const availableSignals = signalEvents.filter(
    (e) =>
      e.payload?.signal_summary?.face_present !== null &&
      e.payload?.signal_summary?.face_present !== undefined,
  ).length;
  const coverage = signalEvents.length
    ? `${Math.round((availableSignals / signalEvents.length) * 100)}%`
    : "Unavailable";
  const helpful = followUps.filter(
    (f): f is typeof f & { helpfulness: number } =>
      typeof f.helpfulness === "number",
  );
  const helpfulness = helpful.length
    ? `${(helpful.reduce((sum, item) => sum + item.helpfulness, 0) / helpful.length).toFixed(1)}/5`
    : "Unavailable";
  const timeline = [
    ...answers.map((a) => ({
      at: a.submitted_at || a.created_at,
      text: `${a.phase} answer · ${a.correct ? "correct" : "incorrect"}`,
    })),
    ...interventions.map((i) => ({
      at: i.created_at,
      text: `${i.kind.replace("_", " ")} support · ${i.status}`,
    })),
    ...events
      .filter((e) => e.event_type !== "signal_summary")
      .map((e) => ({ at: e.created_at, text: e.event_type.replace("_", " ") })),
  ]
    .filter((item): item is { at: string; text: string } => Boolean(item.at))
    .sort((a, b) => String(a.at).localeCompare(String(b.at)))
    .slice(-12);
  async function startRetention() {
    setRetentionBusy(true);
    try {
      const next = await api.createSession({
        participant_code: session.participant_code,
        mode: session.mode,
        lesson_id: lesson.id,
        study_kind: "retention",
        camera_consent: false,
        researcher_token: sessionStorage.getItem("idp.researcher-token") || "",
      });
      onStartSession(next);
    } finally {
      setRetentionBusy(false);
    }
  }
  return (
    <div className="shell results-shell">
      <header className="app-header">
        <div className="topline">
          <span className="logo-mark">↻</span>
          <span>LOOP / SESSION COMPLETE</span>
        </div>
        <button className="ghost-button" onClick={onExit}>
          New session
        </button>
      </header>
      <main className="results-main">
        <p className="eyebrow">A SESSION TRACE</p>
        <h1>
          {lesson.title}
          <br />
          <em>responded.</em>
        </h1>
        <p className="lead">
          Stored observations for {session.study_kind === "demo" ? "this demo learner" : session.participant_code}; values below come
          from this session record.
        </p>
        <div className="result-context">
          <span>{session.mode.replace("_", " ")} mode</span>
          <span>
            {detail?.study_kind || session.study_kind || "practice"} session
          </span>
          <span>data origin: {detail?.data_origin || "observed"}</span>
        </div>
        <div className="metrics">
          <div>
            <strong>{score(pre)}</strong>
            <span>pre-test correct</span>
          </div>
          <div>
            <strong>{score(checkpoint)}</strong>
            <span>checkpoint correct</span>
          </div>
          <div>
            <strong>{score(post)}</strong>
            <span>post-test correct</span>
          </div>
          <div>
            <strong>{interventions.length}</strong>
            <span>support offered</span>
          </div>
          <div>
            <strong>{interventions.filter((item) => Boolean(item.accepted)).length}</strong>
            <span>accepted</span>
          </div>
          <div>
            <strong>{lifecycle("dismissed") + lifecycle("skipped")}</strong>
            <span>dismissed or skipped</span>
          </div>
          <div>
            <strong>{lifecycle("completed")}</strong>
            <span>completed support</span>
          </div>
          <div>
            <strong>
              {Math.round((detail?.progress?.active_time_ms || 0) / 1000)}s /{" "}
              {Math.round((detail?.progress?.elapsed_time_ms || 0) / 1000)}s
            </strong>
            <span>active / elapsed</span>
          </div>
          <div>
            <strong>{coverage}</strong>
            <span>camera signal coverage</span>
          </div>
          <div>
            <strong>
              {followUps.length
                ? `${followUps.filter((f) => f.correct).length}/${followUps.length}`
                : "No follow-ups"}
            </strong>
            <span>follow-up correct</span>
          </div>
          <div>
            <strong>{helpfulness}</strong>
            <span>helpfulness rating</span>
          </div>
          <div>
            <strong>
              {answers.length ? `${correct}/${answers.length}` : "No score"}
            </strong>
            <span>all answers correct</span>
          </div>
        </div>
        <div className="result-actions">
          <button
            className="primary-button"
            onClick={() => downloadCsv(session.session_id)}
          >
            Download CSV ↗
          </button>
          <button className="ghost-button" onClick={onExit}>
            Run another mode
          </button>
          {session.study_kind !== "retention" && session.study_kind !== "demo" && (
            <button
              className="ghost-button"
              disabled={retentionBusy}
              onClick={startRetention}
            >
              {retentionBusy ? "Opening…" : "Optional retention check"}
            </button>
          )}
        </div>
        <SessionFeedback
          sessionId={session.session_id}
          existing={detail?.feedback || null}
        />
        <section className="timeline">
          <div className="section-heading">
            <span className="eyebrow">EVENT TIMELINE</span>
            <span className="muted">Latest stored actions</span>
          </div>
          {timeline.length ? (
            <ol>
              {timeline.map((item, index) => (
                <li key={`${item.at}-${index}`}>
                  <time>
                    {new Date(item.at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                  <span>{item.text}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">No event timeline is available.</p>
          )}
        </section>
        <div className="limitations">
          <strong>Interpretation note</strong>
          <p>
            Webcam signals are observable context, not proof of comprehension.
            This session reports descriptive evidence; it does not claim causal
            learning gains.
          </p>
        </div>
      </main>
    </div>
  );
}
function SessionFeedback({
  sessionId,
  existing,
}: {
  sessionId: string;
  existing: SessionDetail["feedback"];
}) {
  const [supportHelpfulness, setSupportHelpfulness] = useState(
    existing?.support_helpfulness ? String(existing.support_helpfulness) : "",
  );
  const [usability, setUsability] = useState(
    existing?.usability_rating ? String(existing.usability_rating) : "",
  );
  const [ease, setEase] = useState(
    existing?.ease_rating ? String(existing.ease_rating) : "",
  );
  const [comment, setComment] = useState(existing?.comment || "");
  const [saved, setSaved] = useState(Boolean(existing));
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!supportHelpfulness && !usability && !ease && !comment.trim()) return;
    setBusy(true);
    try {
      await api.feedback(sessionId, {
        support_helpfulness: supportHelpfulness
          ? Number(supportHelpfulness)
          : undefined,
        usability_rating: usability ? Number(usability) : undefined,
        ease_rating: ease ? Number(ease) : undefined,
        comment: comment.trim() || undefined,
      });
      setSaved(true);
    } finally {
      setBusy(false);
    }
  }
  if (saved)
    return (
      <section className="feedback-card">
        <div className="section-heading">
          <span className="eyebrow">OPTIONAL FEEDBACK</span>
          <span className="muted">saved</span>
        </div>
        <p>
          Thanks. Your usability feedback is attached to this session record.
        </p>
      </section>
    );
  return (
    <section className="feedback-card">
      <div className="section-heading">
        <span className="eyebrow">OPTIONAL FEEDBACK</span>
        <span className="muted">researchers use ratings descriptively</span>
      </div>
      <h2>How did this session feel?</h2>
      <div className="feedback-fields">
        <label>
          Support helpfulness
          <select
            value={supportHelpfulness}
            onChange={(e) => setSupportHelpfulness(e.target.value)}
          >
            <option value="">Choose a rating</option>
            <option value="1">1 · not helpful</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5 · very helpful</option>
          </select>
        </label>
        <label>
          Usefulness
          <select
            value={usability}
            onChange={(e) => setUsability(e.target.value)}
          >
            <option value="">Choose a rating</option>
            <option value="1">1 · not useful</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5 · very useful</option>
          </select>
        </label>
        <label>
          Ease of use
          <select value={ease} onChange={(e) => setEase(e.target.value)}>
            <option value="">Choose a rating</option>
            <option value="1">1 · difficult</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5 · easy</option>
          </select>
        </label>
      </div>
      <label>
        Optional comment
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={1000}
          placeholder="What should the team improve?"
        />
      </label>
      <button
        className="small-button"
        disabled={
          busy ||
          (!supportHelpfulness && !usability && !ease && !comment.trim())
        }
        onClick={submit}
      >
        {busy ? "Saving…" : "Save feedback"}
      </button>
    </section>
  );
}
