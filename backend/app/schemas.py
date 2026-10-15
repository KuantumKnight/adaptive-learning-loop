from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


Mode = Literal["static", "rule_based", "personalized"]


class SessionCreate(BaseModel):
    participant_code: str = Field(min_length=2, max_length=32)
    mode: Mode
    lesson_id: str
    study_kind: Literal["demo", "practice", "study", "retention"] = "demo"
    camera_consent: bool = False
    demo_token: str | None = Field(default=None, min_length=32, max_length=100)


class InteractionSummary(BaseModel):
    concept: str = Field(default="", max_length=100)
    help_requested: bool = False
    incorrect_streak: int = Field(default=0, ge=0, le=1000)
    quiz_correct: bool | None = None
    revisits: int = Field(default=0, ge=0, le=100000)
    response_time_ms: int = Field(default=0, ge=0, le=86400000)


class SignalSummary(BaseModel):
    enabled: bool = False
    face_present: bool | None = None
    looking_away: bool | None = None
    ambiguous: bool | None = None
    blink_count: int | None = Field(default=None, ge=0, le=1000000)
    gaze_direction: Literal["LEFT", "CENTER", "RIGHT"] | None = None
    head_yaw_degrees: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    head_pitch_degrees: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    head_roll_degrees: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    sustained_seconds: int = Field(default=0, ge=0, le=86400)
    status: str = Field(default="unavailable", max_length=200)


class EventPayload(BaseModel):
    interaction: InteractionSummary = Field(default_factory=InteractionSummary)
    signal_summary: SignalSummary | None = None


class EventCreate(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=100)
    event_type: Literal["difficulty_detected", "help_requested", "signal_summary"]
    payload: dict[str, Any] = Field(default_factory=dict)


class AnswerCreate(BaseModel):
    question_id: str
    phase: Literal["pre", "checkpoint", "post", "retention", "follow_up"]
    concept: str
    answer: str
    response_time_ms: int | None = None
    response_started_at: str | None = None
    section_id: str | None = None


class InterventionResponse(BaseModel):
    action: Literal["accept", "dismiss", "skip", "view"]
    helpfulness: int | None = Field(default=None, ge=1, le=5)


class FollowUpCreate(BaseModel):
    question_id: str
    answer: str
    helpfulness: int | None = Field(default=None, ge=1, le=5)


class ProgressUpdate(BaseModel):
    phase: Literal["pre", "learn", "checkpoint", "post", "retention", "done"]
    question_id: str | None = None
    question_index: int = Field(default=0, ge=0)
    section_id: str = "explain"
    section_visits: dict[str, int] = Field(default_factory=dict)
    active_time_ms: int = Field(default=0, ge=0)
    elapsed_time_ms: int = Field(default=0, ge=0)


class FeedbackCreate(BaseModel):
    support_helpfulness: int | None = Field(default=None, ge=1, le=5)
    usability_rating: int | None = Field(default=None, ge=1, le=5)
    ease_rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
