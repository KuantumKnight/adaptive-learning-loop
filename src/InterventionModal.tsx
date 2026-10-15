import { useEffect, useRef, useState } from "react";
import { api, type Lesson, type StateResponse } from "./api";

export default function InterventionModal({
  sessionId,
  intervention,
  lesson,
  onClose,
}: {
  sessionId: string;
  intervention: NonNullable<StateResponse["intervention"]>;
  lesson: Lesson;
  onClose: () => void;
}) {
  const [accepted, setAccepted] = useState(intervention.status === "accepted");
  const [followIndex, setFollowIndex] = useState(intervention.follow_ups?.length || 0);
  const [supportError, setSupportError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof api.supportHistory>>>([]);
  const [guidedChoice, setGuidedChoice] = useState("");
  const [viewSaved, setViewSaved] = useState(
    intervention.status === "viewed" || intervention.status === "accepted",
  );
  const cardRef = useRef<HTMLDivElement>(null);
  const viewRequest = useRef<Promise<void> | null>(null);
  const followUpBank = intervention.follow_up_bank || "follow_up";
  const followUps = (
    lesson.questions[followUpBank] ||
    lesson.questions.follow_up ||
    lesson.questions.checkpoint
  ).slice(0, 2);
  const guided = lesson.id === "binary-search"
    ? { prompt: "In [2, 4, 6], the middle is 4 and the target is 6. What moves next?", options: ["Move low right", "Move high left", "Stop as found"], answer: "Move low right" }
    : lesson.id === "bubble-sort"
      ? { prompt: "In [3, 1], what is the next step?", options: ["Swap the neighbors", "Keep their order", "Stop"], answer: "Swap the neighbors" }
      : { prompt: "In [5, 9], the target is 9. After checking 5, what happens?", options: ["Check the next value", "Stop as found", "Sort first"], answer: "Check the next value" };
  const text =
    intervention.kind === "simplified"
      ? {
          title: "Let’s simplify the idea",
          body: lesson.sections.find((s) => s.id === "simplify")?.body,
        }
      : intervention.kind === "worked_example"
        ? {
            title: "Here is another example",
            body: lesson.sections.find((s) => s.id === "explain")?.example,
          }
        : {
            title: "Let’s practise together",
            body: lesson.sections.find((s) => s.id === "practice")?.body,
          };
  async function saveViewed() {
    if (viewRequest.current) return viewRequest.current;
    setSupportError("");
    const request = api
      .intervention(sessionId, intervention.id, { action: "view" })
      .then(() => setViewSaved(true))
      .catch(() => {
        setSupportError("This support offer could not be saved. Retry before continuing.");
      })
      .finally(() => {
        if (viewRequest.current === request) viewRequest.current = null;
      });
    viewRequest.current = request;
    return request;
  }
  useEffect(() => {
    if (!viewSaved) void saveViewed();
  }, [sessionId, intervention.id]);
  useEffect(() => {
    void api.supportHistory(sessionId).then(setHistory).catch(() => undefined);
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cardRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); void closeWith(accepted ? "skip" : "dismiss"); }
      if (event.key !== "Tab" || !cardRef.current) return;
      const controls = [...cardRef.current.querySelectorAll<HTMLButtonElement>("button:not([disabled])")];
      if (!controls.length) { event.preventDefault(); return; }
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === cardRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previousFocus?.focus(); };
  }, [sessionId, accepted]);
  async function accept() {
    if (!viewSaved || submitting || (intervention.kind === "guided_practice" && guidedChoice !== guided.answer)) return;
    setSubmitting(true);
    setSupportError("");
    try {
      await api.intervention(sessionId, intervention.id, { action: "accept" });
      setAccepted(true);
    } catch {
      setSupportError("Support could not be saved yet. Please try again.");
    } finally { setSubmitting(false); }
  }
  async function doneFollow(answer: string) {
    if (!viewSaved || submitting) return;
    setSubmitting(true);
    setSupportError("");
    try {
      await api.followUp(sessionId, intervention.id, {
        question_id: followUps[followIndex].id,
        answer,
      });
      if (followIndex < followUps.length - 1) setFollowIndex((i) => i + 1);
      else onClose();
    } catch {
      setSupportError("Your answer was not saved. Choose an answer again to retry.");
    } finally { setSubmitting(false); }
  }
  async function closeWith(action: "dismiss" | "skip") {
    if (submitting) return;
    setSubmitting(true);
    try { await api.intervention(sessionId, intervention.id, { action }); onClose(); }
    catch { setSupportError("Support status could not be saved. Retry the action."); }
    finally { setSubmitting(false); }
  }
  return (
    <div className="modal-backdrop">
      <div
        ref={cardRef}
        tabIndex={-1}
        className="intervention-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="support-title"
      >
        <div className="intervention-tag">
          ADAPTIVE SUPPORT · {intervention.kind.replace("_", " ")}
        </div>
        <h2 id="support-title">{accepted ? "One quick check" : text.title}</h2>
        <p>{accepted ? followUps[followIndex].prompt : text.body}</p>
        <p className="support-reason">
          {intervention.reason} ·{" "}
          {intervention.selection_reason || "policy selected"}
        </p>
        {history.filter((item) => item.concept === lesson.id).length > 0 && (
          <p className="support-history">Completed history: {history.filter((item) => item.concept === lesson.id).map((item) => `${item.kind.replace("_", " ")} ${item.completed_interventions} × · score ${item.smoothed_score.toFixed(2)}`).join("; ")}</p>
        )}
        {!accepted && intervention.kind === "guided_practice" && (
          <div className="guided-practice">
            <strong>Your turn: predict the next algorithm action</strong>
            <p>{guided.prompt}</p>
            <div className="option-list compact">{guided.options.map((option) => <button key={option} onClick={() => setGuidedChoice(option)} aria-pressed={guidedChoice === option}>{option}</button>)}</div>
            <p aria-live="polite">{guidedChoice ? guidedChoice === guided.answer ? "Correct. You can continue to the follow-up checks." : "Try again. Trace the current comparison first." : "Choose an action to continue."}</p>
          </div>
        )}
        {supportError && <p className="error" role="alert">{supportError}</p>}
        {!viewSaved && supportError && (
          <button className="small-button" onClick={saveViewed}>
            Retry saving support
          </button>
        )}
        {accepted ? (
          <>
            <div className="option-list compact">
              {followUps[followIndex].options.map((o) => (
                <button key={o} onClick={() => doneFollow(o)} disabled={!viewSaved || submitting}>
                  {o}
                </button>
              ))}
            </div>
            <button className="ghost-button" onClick={() => closeWith("skip")} disabled={!viewSaved || submitting}>
              Skip follow-up
            </button>
          </>
        ) : (
          <div className="modal-actions">
            <button
              className="ghost-button"
              onClick={() => closeWith("dismiss")}
              disabled={!viewSaved || submitting}
            >
              Dismiss
            </button>
            <button className="ghost-button" onClick={() => closeWith("skip")} disabled={!viewSaved || submitting}>
              Skip support
            </button>
            <button className="primary-button" onClick={accept} disabled={!viewSaved || submitting || (intervention.kind === "guided_practice" && guidedChoice !== guided.answer)}>
              Use this support →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
