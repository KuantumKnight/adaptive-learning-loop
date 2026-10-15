import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  flushOutbox,
  Lesson,
  Mode,
  outboxSize,
  Question,
  Session,
  SessionDetail,
  StateResponse,
} from "./api";
import { useCamera } from "./useCamera";
import ResearchWorkspace from "./ResearchWorkspace";
import AlgorithmVisualizer from "./AlgorithmVisualizer";
import InterventionModal from "./InterventionModal";
import Results from "./Results";
import { useSessionSync } from "./useSessionSync";
import { useSessionRecovery } from "./useSessionRecovery";

const modeCopy: Record<Mode, { label: string; detail: string }> = {
  static: {
    label: "Static lesson",
    detail: "The same lesson flow for everyone.",
  },
  rule_based: {
    label: "Rule-based adaptive",
    detail: "Fixed rules choose a useful intervention.",
  },
  personalized: {
    label: "Personalized adaptive",
    detail: "Your intervention history guides future help.",
  },
};
function formatDegrees(value: number | null) {
  return value === null ? "unavailable" : `${value.toFixed(0)}°`;
}

export default function App() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const { session, setSession, exit } = useSessionRecovery();
  const [error, setError] = useState("");
  const [research, setResearch] = useState(false);
  useEffect(() => {
    api
      .lessons()
      .then(setLessons)
      .catch((e) => setError(e.message));
  }, []);
  if (session) {
    const lesson = lessons.find((l) => l.id === session.lesson_id);
    if (!lesson)
      return <div className="loading-screen">Loading your session…</div>;
    return (
      <LessonRunner
        key={session.session_id}
        session={session}
        lesson={lesson}
        onStartSession={setSession}
        onExit={exit}
      />
    );
  }
  if (research) return <ResearchWorkspace onBack={() => setResearch(false)} />;
  return (
    <StartScreen
      lessons={lessons}
      error={error}
      onStart={setSession}
      onResearch={() => setResearch(true)}
    />
  );
}

function StartScreen({
  lessons,
  error,
  onStart,
  onResearch,
}: {
  lessons: Lesson[];
  error: string;
  onStart: (s: Session) => void;
  onResearch: () => void;
}) {
  const [code, setCode] = useState("demo-01");
  const [mode, setMode] = useState<Mode>("personalized");
  const [lesson, setLesson] = useState("binary-search");
  const [studyKind, setStudyKind] = useState<"demo" | "practice" | "study">("demo");
  const [researcherToken, setResearcherToken] = useState("");
  const [cameraConsent, setCameraConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState("");
  const selectedLesson = lessons.find((item) => item.id === lesson);
  async function begin() {
    setBusy(true);
    setStartError("");
    try {
      const nextSession = await api.createSession({
          participant_code: code.trim(),
          mode,
          lesson_id: lesson,
          study_kind: studyKind,
          camera_consent: cameraConsent,
          researcher_token: researcherToken,
        });
      if (studyKind !== "demo") sessionStorage.setItem("idp.researcher-token", researcherToken);
      onStart(nextSession);
    } catch (e) {
      setStartError(
        e instanceof Error ? e.message : "Unable to create session",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="shell start-shell">
      <header className="topline">
        <span className="logo-mark">↻</span>
        <span>LOOP / ALGORITHM STUDIO</span>
        <span className="status-dot" />{" "}
        <span className="muted">adaptive learning studio</span>
      </header>
      <main className="start-grid">
        <section className="studio-intro">
          <p className="eyebrow">AN INTERACTIVE ALGORITHM STUDIO</p>
          <h1>
            See how it
            <br />
            <em>thinks.</em>
          </h1>
          <p className="lead">
            Step through a real search or sort. Change the numbers and watch
            the algorithm update its bounds, comparisons, or swaps.
          </p>
          {selectedLesson?.visualizer && (
            <AlgorithmVisualizer
              key={selectedLesson.id}
              config={selectedLesson.visualizer}
              preview
            />
          )}
          <div className="studio-loop" aria-label="How learning support works">
            <span><b>01</b> You try</span><i>→</i>
            <span><b>02</b> We observe answers</span><i>→</i>
            <span><b>03</b> Help is offered</span><i>→</i>
            <span><b>04</b> Two checks measure it</span>
          </div>
          <p className="studio-note">
            Support is based on your answers and completed follow-up checks.
            Webcam is optional and never used to guess how you feel.
          </p>
        </section>
        <section className="start-card">
          <div className="card-kicker">CHOOSE YOUR PRACTICE</div>
          {studyKind === "demo" ? (
            <p className="privacy-note">Private demo history is kept on this browser. Demo results are always labelled synthetic.</p>
          ) : (
            <label>
              Participant code
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. P01" />
            </label>
          )}
          <label>
            Lesson
            <select value={lesson} onChange={(e) => setLesson(e.target.value)}>
              {lessons.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Session purpose
            <select
              value={studyKind}
              onChange={(e) =>
                setStudyKind(e.target.value as "demo" | "practice" | "study")
              }
            >
              <option value="demo">Public demonstration</option>
              <option value="practice">Research practice / setup</option>
              <option value="study">Measured study session</option>
            </select>
          </label>
          {studyKind !== "demo" && (
            <label>
              Researcher credential
              <input type="password" autoComplete="off" value={researcherToken} onChange={(e) => setResearcherToken(e.target.value)} />
            </label>
          )}
          <div className="mode-label">Learning mode</div>
          <div className="mode-list">
            {(Object.keys(modeCopy) as Mode[]).map((m) => (
              <button
                type="button"
                className={`mode-option ${mode === m ? "selected" : ""}`}
                key={m}
                onClick={() => setMode(m)}
              >
                <span className="radio">{mode === m ? "●" : "○"}</span>
                <span>
                  <strong>{modeCopy[m].label}</strong>
                  <small>{modeCopy[m].detail}</small>
                </span>
              </button>
            ))}
          </div>
          <label className="consent-row">
            <input
              type="checkbox"
              checked={cameraConsent}
              onChange={(e) => setCameraConsent(e.target.checked)}
            />
            Allow optional webcam summaries: blink count, gaze direction, and
            head pose
          </label>
          {(error || startError) && (
            <p className="error">{error || startError}</p>
          )}
          <button
            className="primary-button"
            disabled={(studyKind !== "demo" && (!code.trim() || !researcherToken.trim())) || !lessons.length || busy}
            onClick={begin}
          >
            {busy ? "Opening…" : "Open lesson →"}
          </button>
          <button className="ghost-button research-entry" onClick={onResearch}>
            Research workspace
          </button>
          <p className="privacy-note">
            Camera is optional. Blink counts and approximate gaze/head-pose
            summaries may be stored; raw frames and landmarks stay in your
            browser. These signals do not measure attention or emotion.
          </p>
        </section>
      </main>
      <footer>
        <span>VIT CHENNAI · CSE</span>
        <span>Academic prototype · v1.0</span>
      </footer>
    </div>
  );
}

function LessonRunner({
  session,
  lesson,
  onStartSession,
  onExit,
}: {
  session: Session;
  lesson: Lesson;
  onStartSession: (session: Session) => void;
  onExit: () => void;
}) {
  const [phase, setPhase] = useState<
    "pre" | "learn" | "checkpoint" | "post" | "retention" | "done"
  >(
    session.study_kind === "retention"
      ? "retention"
      : session.study_kind === "study"
        ? "pre"
        : "learn",
  );
  const [questionIndex, setQuestionIndex] = useState(0);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [state, setState] = useState<StateResponse | null>(null);
  const [notice, setNotice] = useState("");
  const [pendingEvents, setPendingEvents] = useState(outboxSize());
  const startedAt = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [activeSeconds, setActiveSeconds] = useState(0);
  const [questionStartedAt, setQuestionStartedAt] = useState(Date.now());
  const [section, setSection] = useState("explain");
  const sectionVisits = useRef<Record<string, number>>({ explain: 1 });
  const [showDebug, setShowDebug] = useState(false);
  const camera = useCamera();
  const latestCameraSignalRef = useRef(camera.signal);
  useEffect(() => {
    latestCameraSignalRef.current = camera.signal;
  }, [camera.signal]);
  const [incorrectStreak, setIncorrectStreak] = useState(0);
  const [answerBusy, setAnswerBusy] = useState(false);
  const answerInFlight = useRef(false);
  const signalInFlight = useRef(false);
  const progressSync = useSessionSync(session.session_id);
  const restored = useRef(false);
  const currentPhase = useRef(phase);
  const currentQuestionIndex = useRef(questionIndex);
  const currentSection = useRef(section);
  const currentActiveSeconds = useRef(activeSeconds);
  const currentElapsed = useRef(elapsed);
  const questions = phase === "learn" ? [] : lesson.questions[phase] || [];
  const question = questions[questionIndex];
  useEffect(() => {
    const t = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.current) / 1000));
      if (!document.hidden) setActiveSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    currentPhase.current = phase;
    currentQuestionIndex.current = questionIndex;
    currentSection.current = section;
    currentActiveSeconds.current = activeSeconds;
    currentElapsed.current = elapsed;
  }, [phase, questionIndex, section, activeSeconds, elapsed]);
  useEffect(() => {
    const t = window.setInterval(() => {
      if (!restored.current || currentPhase.current === "done" || progressSync.isPending()) return;
      const currentQuestions = lesson.questions[currentPhase.current] || [];
      void progressSync.save({
          phase: currentPhase.current,
          question_id:
            currentQuestions[currentQuestionIndex.current]?.id || null,
          question_index: currentQuestionIndex.current,
          section_id: currentSection.current,
          section_visits: sectionVisits.current,
          active_time_ms: currentActiveSeconds.current * 1000,
          elapsed_time_ms: currentElapsed.current * 1000,
        })
        .catch(() => setNotice("Progress is not saved yet. Check your connection."));
    }, 5000);
    return () => window.clearInterval(t);
  }, [session.session_id, lesson.questions, progressSync.save, progressSync.isPending]);
  useEffect(() => {
    setQuestionStartedAt(Date.now());
  }, [phase, questionIndex]);
  useEffect(() => {
    api
      .detail(session.session_id)
      .then((next) => {
        setDetail(next);
        if (!restored.current) {
          const progress = next.progress;
          const unstartedPracticeBaseline =
            session.study_kind === "practice" &&
            progress?.phase === "pre" &&
            !next.answers.some((answer) => answer.phase === "pre");
          if (unstartedPracticeBaseline) {
            const sectionId = progress?.section_id || "explain";
            setPhase("learn");
            setSection(sectionId);
            void progressSync.save({
                phase: "learn",
                question_id: null,
                question_index: 0,
                section_id: sectionId,
                section_visits: progress?.section_visits || { explain: 1 },
                active_time_ms: progress?.active_time_ms || 0,
                elapsed_time_ms: progress?.elapsed_time_ms || 0,
              })
              .catch(() => undefined);
          } else if (progress?.phase) {
            setPhase(progress.phase as typeof phase);
          }
          if (typeof progress?.question_index === "number")
            setQuestionIndex(progress.question_index);
          if (progress?.elapsed_time_ms) {
            startedAt.current = Date.now() - progress.elapsed_time_ms;
            setElapsed(Math.floor(progress.elapsed_time_ms / 1000));
          }
          if (progress?.active_time_ms)
            setActiveSeconds(Math.floor(progress.active_time_ms / 1000));
          if (progress?.section_id) setSection(progress.section_id);
          if (progress?.section_visits)
            sectionVisits.current = { explain: 1, ...progress.section_visits };
          const recent = next.answers.filter((item) => item.phase === "checkpoint").reverse();
          let streak = 0;
          for (const item of recent) { if (item.correct) break; streak += 1; }
          setIncorrectStreak(streak);
          const active = [...next.interventions].reverse().find((item) => ["offered", "viewed", "accepted"].includes(item.status));
          if (active) setState({ level: "support_active", triggered: false, reasons: [], intervention: active });
          restored.current = true;
        }
      })
      .catch(() => undefined);
  }, [session.session_id, progressSync.save]);
  useEffect(() => {
    if (phase === "done") camera.stop();
  }, [phase, camera.stop]);
  useEffect(() => {
    const t = window.setInterval(async () => {
      if (!restored.current || currentPhase.current === "done" || signalInFlight.current) return;
      signalInFlight.current = true;
      try {
      const flushed = await flushOutbox();
      if (flushed.discarded) setNotice(`${flushed.discarded} queued event${flushed.discarded === 1 ? " was" : "s were"} discarded because the session no longer accepts them.`);
        const result = await api.event(session.session_id, {
          client_event_id: crypto.randomUUID(),
          event_type: "signal_summary",
          payload: {
            interaction: {
              concept: lesson.id,
              incorrect_streak: incorrectStreak,
              revisits: Math.max(0, (sectionVisits.current[section] || 1) - 1),
            },
            signal_summary: latestCameraSignalRef.current,
          },
        });
        setPendingEvents(outboxSize());
        if (result.state.level === "offline")
          setNotice(
            "Offline: this signal summary is queued locally and will retry.",
          );
        else {
          if (!flushed.discarded && (flushed.saved || notice.startsWith("Offline:"))) setNotice("");
          if (result.state.intervention) setState(result.state);
        }
      } catch {
        setPendingEvents(outboxSize());
      } finally {
        signalInFlight.current = false;
      }
    }, 5000);
    return () => window.clearInterval(t);
  }, [
    session.session_id,
    lesson.id,
    incorrectStreak,
    section,
    notice,
  ]);
  const progress =
    phase === "retention"
      ? 50
      : phase === "pre"
        ? 8
        : phase === "learn"
          ? session.study_kind === "practice" ? 8 : 35
          : phase === "checkpoint"
            ? 58
            : phase === "post"
              ? 82
              : 100;
  const phaseSteps: Array<[string, string]> =
    session.study_kind === "retention"
      ? [["retention", "Retention check"]]
      : session.study_kind === "study" || phase === "pre"
        ? [
            ["pre", "Warm-up"],
            ["learn", "Lesson"],
            ["checkpoint", "Checkpoint"],
            ["post", "Post-test"],
          ]
        : [
            ["learn", "Lesson"],
            ["checkpoint", "Checkpoint"],
            ["post", "Post-test"],
          ];
  const currentStepIndex = phaseSteps.findIndex(([key]) => key === phase);
  async function saveProgress(
    nextPhase: typeof phase,
    nextQuestionId: string | null,
    nextIndex: number,
    nextSection = section,
  ) {
    await progressSync.save({
      phase: nextPhase,
      question_id: nextQuestionId,
      question_index: nextIndex,
      section_id: nextSection,
      section_visits: sectionVisits.current,
      active_time_ms: activeSeconds * 1000,
      elapsed_time_ms: elapsed * 1000,
    });
  }
  async function answer() {
    if (!question || !selected || answerInFlight.current) return;
    answerInFlight.current = true;
    setAnswerBusy(true);
    setNotice("");
    try {
    const response = await api.answer(session.session_id, {
      question_id: question.id,
      phase: phase as "pre" | "checkpoint" | "post" | "retention",
      concept: question.concept,
      answer: selected,
      response_time_ms: Date.now() - questionStartedAt,
      response_started_at: new Date(questionStartedAt).toISOString(),
      section_id: section,
    });
    const nextStreak = response.incorrect_streak;
    setIncorrectStreak(nextStreak);
    setSelected("");
    if (
      phase === "checkpoint" &&
      !response.correct &&
      session.mode !== "static"
    )
      await requestIntervention(
        nextStreak,
        false,
        response.response_time_ms || 0,
        Math.max(0, (sectionVisits.current[section] || 1) - 1),
      );
    if (questionIndex < questions.length - 1) {
      const next = questionIndex + 1;
      setQuestionIndex(next);
      await saveProgress(phase, questions[next].id, next);
    } else if (phase === "pre") {
      setPhase("learn");
      setQuestionIndex(0);
      await saveProgress("learn", null, 0);
    } else if (phase === "checkpoint") {
      setPhase("post");
      setQuestionIndex(0);
      await saveProgress("post", questions[0]?.id || null, 0);
    } else if (phase === "post" || phase === "retention") {
      await finish();
    }
    } catch {
      setNotice("Answer or progress could not be saved. Your choice is still selected; retry.");
    } finally {
      answerInFlight.current = false;
      setAnswerBusy(false);
    }
  }
  async function requestIntervention(
    streak: number,
    helpRequested = false,
    responseTimeMs = 0,
    revisits = 0,
  ) {
    try {
      const result = await api.event(session.session_id, {
        client_event_id: crypto.randomUUID(),
        event_type: helpRequested ? "help_requested" : "difficulty_detected",
        payload: {
          interaction: {
            concept: lesson.id,
            incorrect_streak: streak,
            quiz_correct: false,
            help_requested: helpRequested,
            revisits,
            response_time_ms: responseTimeMs,
          },
          signal_summary: camera.signal,
        },
      });
      if (result.state.intervention) setState(result.state);
    } catch {
      setNotice(
        "The intervention could not be loaded, but your answer was saved.",
      );
    }
  }
  async function finish() {
    await saveProgress("done", null, 0);
    await api.end(session.session_id);
    setPhase("done");
    setDetail(await api.detail(session.session_id));
  }
  if (phase === "done")
    return (
      <Results
        session={session}
        lesson={lesson}
        detail={detail}
        onStartSession={onStartSession}
        onExit={onExit}
      />
    );
  function changeSection(next: string) {
    setSection(next);
    sectionVisits.current[next] = (sectionVisits.current[next] || 0) + 1;
    void saveProgress(
      currentPhase.current,
      currentPhase.current === "learn"
        ? null
        : questions[currentQuestionIndex.current]?.id || null,
      currentQuestionIndex.current,
      next,
    );
  }
  return (
    <div className="shell app-shell">
      <header className="app-header">
        <div className="topline">
          <span className="logo-mark">↻</span>
          <span>LOOP / {lesson.title.toUpperCase()}</span>
        </div>
        <div className="header-actions">
          <span className={`mode-pill ${session.mode}`}>
            {modeCopy[session.mode].label}
          </span>
          <span className="save-state">
            {answerBusy ? "saving answer…" : pendingEvents ? `${pendingEvents} pending` : notice.includes("not saved") || notice.includes("could not") ? "save failed" : "saved"}
          </span>
          <button
            className="ghost-button"
            onClick={() => setShowDebug((v) => !v)}
          >
            {showDebug ? "Hide signals" : "Show signals"}
          </button>
          <button className="ghost-button" onClick={onExit}>
            Exit
          </button>
        </div>
        <div
          className="progress"
          aria-label={`Lesson progress ${progress}%`}
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span style={{ width: `${progress}%` }} />
        </div>
      </header>
      <main className="lesson-layout">
        <aside>
          <p className="eyebrow">SESSION {session.participant_code}</p>
          <h2>{lesson.title}</h2>
          <p className="muted">{lesson.summary}</p>
          <div className="phase-list">
            {phaseSteps.map(([key, label], i) => {
              const completed = currentStepIndex > i;
              return (
                <div
                  className={`phase-item ${phase === key ? "active" : ""} ${completed ? "complete" : ""}`}
                  key={key}
                >
                  <span>
                    {completed ? "✓" : String(i + 1).padStart(2, "0")}
                  </span>
                  {label}
                </div>
              );
            })}
          </div>
          <div className="camera-card">
            <div className="camera-heading">
              <span>LEARNER SIGNAL</span>
              <span
                className={`signal-light ${camera.signal.enabled ? "on" : ""}`}
              />
            </div>
            <div className="camera-preview">
              <video
                ref={camera.videoRef}
                muted
                playsInline
                aria-label="Optional local webcam preview"
              />
              <canvas
                ref={camera.canvasRef}
                className="landmark-overlay"
                aria-hidden="true"
              />
            </div>
            <p>{camera.signal.status}</p>
            {session.camera_consent ? (
              <div className="camera-actions">
                <button
                  className="small-button"
                  onClick={camera.signal.enabled ? camera.stop : camera.start}
                  disabled={camera.busy}
                >
                  {camera.busy
                    ? "Requesting…"
                    : camera.signal.enabled
                      ? "Turn camera off"
                      : "Enable camera"}
                </button>
                {camera.signal.enabled && (
                  <>
                    <button
                      className="small-button"
                      onClick={camera.toggleLandmarks}
                      aria-pressed={camera.showLandmarks}
                    >
                      {camera.showLandmarks ? "Hide landmarks" : "Show landmarks"}
                    </button>
                    <button className="small-button" onClick={camera.calibrate}>
                      Calibrate
                    </button>
                  </>
                )}
              </div>
            ) : (
              <p className="muted">
                Webcam summaries were not enabled for this session.
              </p>
            )}
          </div>
        </aside>
        <section className="lesson-main">
          {phase === "learn" ? (
            <LearningView
              lesson={lesson}
              section={section}
              setSection={changeSection}
              onContinue={() => {
                setPhase("checkpoint");
                setQuestionIndex(0);
                void saveProgress(
                  "checkpoint",
                  lesson.questions.checkpoint?.[0]?.id || null,
                  0,
                );
              }}
            />
          ) : (
            <QuestionView
              phase={phase}
              question={question}
              selected={selected}
              setSelected={setSelected}
              onAnswer={answer}
              busy={answerBusy}
            />
          )}
          {phase === "pre" && session.study_kind === "practice" && (
            <button
              className="skip-baseline"
              onClick={() => {
                setPhase("learn");
                setQuestionIndex(0);
                void saveProgress("learn", null, 0);
              }}
            >
              Skip the baseline and explore the lesson <span aria-hidden="true">→</span>
            </button>
          )}
          {session.mode !== "static" && phase !== "retention" && (
            <button
              className="help-link"
              onClick={() => requestIntervention(0, true)}
            >
              Need help with this idea
            </button>
          )}
          {notice && <p className="notice" role="status" aria-live="polite">{notice}</p>}
          {showDebug && (
            <div className="debug-panel">
              <strong>Signal debug</strong>
              <span>state: {state?.level || "observing"}</span>
              <span>
                face:{" "}
                {camera.signal.face_present === null
                  ? "unavailable"
                  : camera.signal.face_present
                    ? "present"
                    : "not detected"}
              </span>
              <span>
                looking away:{" "}
                {camera.signal.looking_away === null
                  ? "unavailable"
                  : camera.signal.looking_away
                    ? "yes"
                    : "no"}
              </span>
              <span>
                multiple faces:{" "}
                {camera.signal.ambiguous === null
                  ? "unavailable"
                  : camera.signal.ambiguous
                    ? "yes"
                    : "no"}
              </span>
              <span>
                gaze direction: {camera.signal.gaze_direction || "unavailable"}
              </span>
              <span>
                head pose: {formatDegrees(camera.signal.head_yaw_degrees)} yaw ·{" "}
                {formatDegrees(camera.signal.head_pitch_degrees)} pitch ·{" "}
                {formatDegrees(camera.signal.head_roll_degrees)} roll
              </span>
              <span>
                blinks this session:{" "}
                {camera.signal.blink_count === null
                  ? "unavailable"
                  : camera.signal.blink_count}
              </span>
              <span>interactions: {incorrectStreak} recent incorrect</span>
              <span>
                active time: {activeSeconds}s · elapsed: {elapsed}s
              </span>
              <span>
                outbox:{" "}
                {pendingEvents
                  ? `${pendingEvents} pending event${pendingEvents === 1 ? "" : "s"}`
                  : "empty"}
              </span>
              {state?.observations?.map((r) => (
                <span key={r}>observation: {r}</span>
              ))}
              {state?.reasons.map((r) => (
                <span key={r}>reason: {r}</span>
              ))}
            </div>
          )}
        </section>
      </main>
      {state?.intervention && (
        <InterventionModal
          sessionId={session.session_id}
          intervention={state.intervention}
          lesson={lesson}
          onClose={() => setState(null)}
        />
      )}
    </div>
  );
}

function LearningView({
  lesson,
  section,
  setSection,
  onContinue,
}: {
  lesson: Lesson;
  section: string;
  setSection: (s: string) => void;
  onContinue: () => void;
}) {
  const current = lesson.sections.find((s) => s.id === section)!;
  return (
    <>
      <p className="eyebrow">CORE LESSON</p>
      <h1>{current.title}</h1>
      <p className="lesson-copy">{current.body}</p>
      <div className="example-block">
        <span className="example-label">WORKED EXAMPLE</span>
        <p>{current.example}</p>
      </div>
      <div className="lesson-meta">
        {lesson.objectives?.map((objective) => (
          <span key={objective}>{objective}</span>
        ))}
      </div>
      {lesson.visualizer && <AlgorithmVisualizer config={lesson.visualizer} />}
      <div className="section-tabs">
        {lesson.sections.map((s) => (
          <button
            key={s.id}
            className={s.id === section ? "active" : ""}
            onClick={() => setSection(s.id)}
          >
            {s.title}
          </button>
        ))}
      </div>
      <button className="primary-button continue" onClick={onContinue}>
        Try a checkpoint →
      </button>
    </>
  );
}

function QuestionView({
  phase,
  question,
  selected,
  setSelected,
  onAnswer,
  busy,
}: {
  phase: string;
  question?: Question;
  selected: string;
  setSelected: (s: string) => void;
  onAnswer: () => void;
  busy: boolean;
}) {
  if (!question) return null;
  return (
    <>
      <p className="eyebrow">
        {phase === "pre"
          ? "BASELINE"
          : phase === "retention"
            ? "RETENTION CHECK"
            : phase === "post"
              ? "CHECK YOUR LEARNING"
              : "IN THE MOMENT"}
      </p>
      <h1>
        {phase === "checkpoint"
          ? "A quick checkpoint"
          : phase === "pre"
            ? "Before we begin"
            : phase === "retention"
              ? "What do you remember?"
              : "What stayed with you?"}
      </h1>
      <div className="question-card">
        <span className="question-number">QUESTION</span>
        <h2>{question.prompt}</h2>
        <div className="option-list">
          {question.options.map((option) => (
            <button
              key={option}
              className={selected === option ? "selected" : ""}
              onClick={() => setSelected(option)}
              disabled={busy}
            >
              <span>{selected === option ? "●" : "○"}</span>
              {option}
            </button>
          ))}
        </div>
        <button
          className="primary-button"
          disabled={!selected || busy}
          onClick={onAnswer}
        >
          {busy ? "Saving…" : phase === "post" || phase === "retention"
            ? "Finish question →"
            : "Submit answer →"}
        </button>
      </div>
    </>
  );
}
