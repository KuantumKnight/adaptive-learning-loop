export type Mode = "static" | "rule_based" | "personalized";
export type Lesson = {
  id: string;
  title: string;
  summary: string;
  objectives?: string[];
  prerequisites?: string[];
  complexity?: string;
  visualizer?: { kind: string; values: number[]; target?: number };
  sections: { id: string; title: string; body: string; example: string }[];
  questions: Record<string, Question[]>;
};
export type Question = {
  id: string;
  concept: string;
  prompt: string;
  options: string[];
};
export type AnswerRecord = {
  id: number;
  question_id: string;
  phase: "pre" | "checkpoint" | "post" | "retention" | "follow_up";
  concept: string;
  answer: string;
  correct: boolean;
  response_time_ms?: number | null;
  response_started_at?: string | null;
  submitted_at?: string | null;
  created_at?: string;
};
export type FollowUpRecord = {
  id: number;
  intervention_id: number;
  question_id: string;
  answer: string;
  correct: boolean;
  helpfulness?: number | null;
  created_at?: string;
};
export type InterventionRecord = {
  id: number;
  concept: string;
  kind: string;
  trigger?: string;
  reason: string;
  selection_reason?: string;
  follow_up_bank?: "follow_up" | "follow_up_repeat";
  status: string;
  accepted?: boolean | number | null;
  created_at?: string;
  follow_ups?: FollowUpRecord[];
};
export type EventRecord = {
  id: number;
  event_type: string;
  payload: {
    signal_summary?: {
      face_present?: boolean | null;
      ambiguous?: boolean | null;
      looking_away?: boolean | null;
      blink_count?: number | null;
      gaze_direction?: "LEFT" | "CENTER" | "RIGHT" | null;
      head_yaw_degrees?: number | null;
      head_pitch_degrees?: number | null;
      head_roll_degrees?: number | null;
    };
    [key: string]: unknown;
  };
  created_at?: string;
};
export type ResearchSessionRow = {
  session_id: string;
  participant_code: string;
  mode: Mode;
  study_kind: "practice" | "study" | "retention";
  lesson_id: string;
  data_origin: string;
  content_version: string;
  policy_version: string;
  answer_count: number;
  intervention_count: number;
  started_at?: string;
  ended_at?: string | null;
};
export type EventRequest = {
  client_event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
};
export type ProgressRequest = {
  phase: "pre" | "learn" | "checkpoint" | "post" | "retention" | "done";
  question_id: string | null;
  question_index: number;
  section_id: string;
  section_visits: Record<string, number>;
  active_time_ms: number;
  elapsed_time_ms: number;
};
export type Session = {
  session_id: string;
  access_token: string;
  participant_code: string;
  mode: Mode;
  lesson_id: string;
  study_kind?: "demo" | "practice" | "study" | "retention";
  demo_token?: string;
  software_revision?: string;
  policy_config?: Record<string, number>;
  camera_consent?: boolean;
  content_version?: string;
  policy_version?: string;
};
export type SessionDetail = {
  id: string;
  participant_code: string;
  mode: Mode;
  lesson_id: string;
  study_kind?: "demo" | "practice" | "study" | "retention";
  data_origin?: string;
  software_revision?: string;
  policy_config?: Record<string, number>;
  ended_at?: string | null;
  progress?: {
    phase: string;
    question_id: string | null;
    question_index: number;
    section_id: string;
    section_visits?: Record<string, number>;
    active_time_ms?: number;
    elapsed_time_ms?: number;
  };
  answers: AnswerRecord[];
  interventions: InterventionRecord[];
  events?: EventRecord[];
  feedback?: {
    id: number;
    support_helpfulness?: number;
    usability_rating?: number;
    ease_rating?: number;
    comment?: string;
    created_at?: string;
  } | null;
};
export type StateResponse = {
  level: string;
  triggered: boolean;
  reasons: string[];
  observations?: string[];
  intervention: {
    id: number;
    kind: string;
    concept: string;
    reason: string;
    selection_reason?: string;
    follow_up_bank?: "follow_up" | "follow_up_repeat";
    status?: string;
    follow_ups?: FollowUpRecord[];
  } | null;
};

const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? "/api" : "http://localhost:8000/api");
let sessionToken = "";
const OUTBOX_KEY = "idp.event-outbox";
let flushInProgress = false;

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type PendingEvent = {
  path: string;
  body: EventRequest;
  queuedAt: string;
  token?: string;
  attempts?: number;
  nextAttemptAt?: number;
};

function readOutbox(): PendingEvent[] {
  try {
    return JSON.parse(
      localStorage.getItem(OUTBOX_KEY) || "[]",
    ) as PendingEvent[];
  } catch {
    return [];
  }
}

function writeOutbox(items: PendingEvent[]) {
  localStorage.setItem(OUTBOX_KEY, JSON.stringify(items.slice(-200)));
}
export function outboxSize() {
  return readOutbox().length;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(sessionToken ? { "X-Session-Token": sessionToken } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok)
    throw new ApiError(
      res.status,
      (await res.text()) || `Request failed (${res.status})`,
    );
  return res.json() as Promise<T>;
}

export const api = {
  lessons: () => request<Lesson[]>("/lessons"),
  createSession: async (body: {
    participant_code: string;
    mode: Mode;
    lesson_id: string;
    study_kind?: "demo" | "practice" | "study" | "retention";
    camera_consent?: boolean;
    researcher_token?: string;
  }) => {
    const { researcher_token, ...payload } = body;
    if (payload.study_kind === "demo") {
      const savedToken = localStorage.getItem("idp.demo-token");
      if (savedToken) Object.assign(payload, { demo_token: savedToken });
    }
    const session = await request<Session>("/sessions", {
      method: "POST",
      headers: researcher_token ? { "X-Researcher-Token": researcher_token } : undefined,
      body: JSON.stringify(payload),
    });
    if (session.demo_token) localStorage.setItem("idp.demo-token", session.demo_token);
    sessionToken = session.access_token;
    localStorage.setItem("idp.session", JSON.stringify(session));
    return session;
  },
  setSessionToken: (token: string) => {
    sessionToken = token;
  },
  detail: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  supportHistory: (id: string) => request<{ concept: string; kind: string; completed_interventions: number; outcome_sum: number; smoothed_score: number }[]>(`/sessions/${id}/support-history`),
  event: async (id: string, body: EventRequest) => {
    const path = `/sessions/${id}/events`;
    try {
      return await request<{ state: StateResponse }>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
    } catch (error) {
      // Only transport failures are queued. Validation/auth failures must stay visible.
      if (error instanceof TypeError) {
        const pending = readOutbox();
        if (
          !pending.some(
            (item) => item.body?.client_event_id === body.client_event_id,
          )
        ) {
          pending.push({
            path,
            body,
            token: sessionToken,
            queuedAt: new Date().toISOString(),
          });
          writeOutbox(pending);
        }
        return {
          state: {
            level: "offline",
            triggered: false,
            reasons: [],
            observations: [
              "Event saved locally and will retry when the connection returns",
            ],
            intervention: null,
          },
        };
      }
      throw error;
    }
  },
  answer: (
    id: string,
    body: {
      question_id: string;
      phase: "pre" | "checkpoint" | "post" | "retention";
      concept: string;
      answer: string;
      response_time_ms: number;
      response_started_at: string;
      section_id: string;
    },
  ) =>
    request<{
      correct: boolean;
      incorrect_streak: number;
      response_time_ms?: number | null;
    }>(`/sessions/${id}/answers`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  progress: (id: string, body: ProgressRequest) =>
    request<{ progress: SessionDetail["progress"] }>(
      `/sessions/${id}/progress`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),
  resume: (id: string) =>
    request<
      Pick<Session, "session_id" | "access_token"> & {
        progress: SessionDetail["progress"];
        ended: boolean;
      }
    >(`/sessions/${id}/resume`),
  intervention: (
    id: string,
    interventionId: number,
    body: {
      action: "view" | "accept" | "dismiss" | "skip";
      helpfulness?: number;
    },
  ) =>
    request(`/sessions/${id}/interventions/${interventionId}/response`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  followUp: (
    id: string,
    interventionId: number,
    body: { question_id: string; answer: string; helpfulness?: number },
  ) =>
    request<{
      saved: boolean;
      deduplicated?: boolean;
      correct: boolean;
      completed_follow_ups: number;
    }>(`/sessions/${id}/interventions/${interventionId}/follow-ups`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  feedback: (
    id: string,
    body: {
      support_helpfulness?: number;
      usability_rating?: number;
      ease_rating?: number;
      comment?: string;
    },
  ) =>
    request<{
      saved: boolean;
      deduplicated: boolean;
      feedback: NonNullable<SessionDetail["feedback"]>;
    }>(`/sessions/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  end: (id: string) => request(`/sessions/${id}/end`, { method: "POST" }),
  researchSessions: (token: string) =>
    request<ResearchSessionRow[]>("/research/sessions", {
      headers: { "X-Researcher-Token": token },
    }),
  researchAssignments: (token: string) =>
    request<{
      content_version: string;
      policy_version: string;
      assignments: {
        participant_code: string;
        session_1: string;
        session_2: string;
        session_3: string;
      }[];
    }>("/research/assignments", { headers: { "X-Researcher-Token": token } }),
  resetParticipant: (token: string, code: string) =>
    request<{ reset: boolean; participant_code: string; reset_group: string }>(
      `/research/participants/${encodeURIComponent(code)}/reset`,
      {
        method: "POST",
        headers: { "X-Researcher-Token": token },
      },
    ),
};

export async function flushOutbox() {
  if (flushInProgress) return { saved: 0, discarded: 0, pending: outboxSize() };
  flushInProgress = true;
  try {
  const pending = readOutbox();
  if (!pending.length) return { saved: 0, discarded: 0, pending: 0 };
  const remaining: PendingEvent[] = [];
  let saved = 0;
  let discarded = 0;
  for (const item of pending) {
    if ((item.nextAttemptAt || 0) > Date.now()) {
      remaining.push(item);
      continue;
    }
    try {
      await request(item.path, {
        method: "POST",
        headers: item.token ? { "X-Session-Token": item.token } : undefined,
        body: JSON.stringify(item.body),
      });
      saved++;
    } catch (error) {
      // A completed, expired, or invalid session cannot accept a queued event.
      // Retrying these responses forever creates noise and hides the real save state.
      if (
        error instanceof ApiError &&
        [400, 401, 404, 409, 422].includes(error.status)
      ) {
        discarded++;
        continue;
      }
      const attempts = (item.attempts || 0) + 1;
      remaining.push({
        ...item,
        attempts,
        nextAttemptAt:
          Date.now() + Math.min(30000, 1000 * 2 ** Math.min(attempts, 5)),
      });
    }
  }
  writeOutbox(remaining);
  return { saved, discarded, pending: remaining.length };
  } finally { flushInProgress = false; }
}

export async function downloadCsv(sessionId: string) {
  const res = await fetch(`${API_URL}/sessions/${sessionId}/export.csv`, {
    headers: sessionToken ? { "X-Session-Token": sessionToken } : {},
  });
  if (!res.ok) throw new Error("Unable to download this session export");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${sessionId}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadResearchCsv(token: string) {
  const res = await fetch(`${API_URL}/research/export.csv`, {
    headers: { "X-Researcher-Token": token },
  });
  if (!res.ok) throw new Error("Unable to download the study export");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "study-export.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}
