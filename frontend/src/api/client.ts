import i18n from "../i18n";
import type { PracticeQueue } from "../lib/practiceQueue";
import type {
  CardOut,
  DiagnoseResponse,
  GenderAttemptIn,
  GenderAttemptOut,
  GenderReviewItem,
  InsightResponse,
  Invitation,
  InvitationCreate,
  KlaraNoteResponse,
  L1GenderNotesResponse,
  MCResolveResponse,
  ModulePathItem,
  PhonemeScore,
  PhoneticHintsResponse,
  PronunciationAttemptIn,
  PronunciationBatchOut,
  PronunciationReviewIn,
  PronunciationScoreResponse,
  QuizAttemptIn,
  QuizResponse,
  ReviewRating,
  ScheduleResponse,
  SpeakFinishRequest,
  SpeakFinishResponse,
  SpeakHistoryTurn,
  SpeakTurnResponse,
  Story,
  StoryListItem,
  User,
  UserUpdate,
} from "./types";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export class AuthRequiredError extends ApiError {
  constructor() {
    super(401, "auth required");
  }
}

// Anything listening here can react to a session expiring mid-session.
// AuthProvider hooks this up to clear in-memory state and redirect to /login.
type UnauthorizedListener = () => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();
export function onUnauthorized(fn: UnauthorizedListener): () => void {
  unauthorizedListeners.add(fn);
  return () => unauthorizedListeners.delete(fn);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": i18n.language || "es",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (resp.status === 401) {
    for (const fn of unauthorizedListeners) fn();
    throw new AuthRequiredError();
  }
  if (!resp.ok) {
    // Read body once as text; try to parse as JSON. Reading both .json() and
    // .text() on the same Response throws "body stream already read" because
    // the body is consumed on first read.
    const text = await resp.text();
    let detail: string;
    try {
      const body = JSON.parse(text);
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      detail = text;
    }
    throw new ApiError(resp.status, `${resp.status} ${resp.statusText}: ${detail}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

interface SignupPayload {
  email: string;
  password: string;
  display_name?: string;
  native_language?: string;
  invite_token?: string;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  // --- auth ---
  signup: (payload: SignupPayload) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: async (email: string, password: string): Promise<void> => {
    const body = new URLSearchParams({ username: email, password });
    const resp = await fetch(`${API_BASE}/auth/jwt/login`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Language": i18n.language || "es",
      },
      body: body.toString(),
    });
    if (!resp.ok) {
      const text = await resp.text();
      let detail: string;
      try {
        const j = JSON.parse(text);
        detail = j.detail ?? JSON.stringify(j);
      } catch {
        detail = text;
      }
      throw new ApiError(resp.status, `${resp.status}: ${detail}`);
    }
  },

  logout: () =>
    request<void>("/auth/jwt/logout", { method: "POST" }),

  forgotPassword: (email: string) =>
    request<void>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    request<void>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  verifyEmail: (token: string) =>
    request<User>("/auth/verify", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  requestVerifyToken: (email: string) =>
    request<void>("/auth/request-verify-token", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  // --- protected ---
  getMe: () => request<User>("/me"),

  updateMe: (patch: UserUpdate) =>
    request<User>("/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  completeOnboarding: (): Promise<User> =>
    request<User>("/me/onboarding/complete", { method: "POST" }),

  setPassword: (password: string): Promise<User> =>
    request<User>("/me/password", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  listStories: (limit = 20, offset = 0) =>
    request<StoryListItem[]>(`/stories?limit=${limit}&offset=${offset}`),

  getStory: (id: string) => request<Story>(`/stories/${id}`),

  createStory: (
    topic?: string,
    opts?: { moduleId?: string; topicOrigin?: "chip" | "free" | "none" }
  ) =>
    request<Story>("/stories", {
      method: "POST",
      body: JSON.stringify({
        topic: topic ?? null,
        module_id: opts?.moduleId ?? null,
        topic_origin: opts?.topicOrigin ?? "none",
      }),
    }),

  addCard: (vocabItemId: string) =>
    request<CardOut>("/srs/cards", {
      method: "POST",
      body: JSON.stringify({ vocab_item_id: vocabItemId }),
    }),

  dueCards: (limit = 20) => request<CardOut[]>(`/srs/cards/due?limit=${limit}`),

  listModules: () => request<ModulePathItem[]>("/modules"),

  claimModuleStory: (moduleId: string) =>
    request<Story>(`/modules/${moduleId}/story`, { method: "POST" }),

  finishStory: (storyId: string) =>
    request<{ finished_at: string; module_advanced: boolean }>(
      `/stories/${storyId}/finish`,
      { method: "POST" }
    ),

  listModuleStories: (moduleId: string, limit = 20) =>
    request<StoryListItem[]>(`/stories?limit=${limit}&module_id=${moduleId}`),

  // --- practice ("Pronunciar") ---
  // Backend emits camelCase (focusText, focusTx, targetLanguage, sourceTitle)
  // so the payload deserializes straight into PracticeQueue with no mapping.
  getPracticeQueue: (limit = 6) =>
    request<PracticeQueue>(`/practice/queue?limit=${limit}`),

  reviewCard: (cardId: string, rating: ReviewRating, elapsedSeconds?: number) =>
    request(`/srs/cards/${cardId}/review`, {
      method: "POST",
      body: JSON.stringify(
        elapsedSeconds === undefined ? { rating } : { rating, elapsed_seconds: elapsedSeconds },
      ),
    }),

  submitPronunciationReviews: (reviews: PronunciationReviewIn[]) =>
    request<PronunciationBatchOut>("/srs/cards/review-batch", {
      method: "POST",
      body: JSON.stringify({ reviews }),
    }),

  // --- invitations (admin only) ---
  listInvitations: () => request<Invitation[]>("/admin/invitations"),

  createInvitation: (payload: InvitationCreate) =>
    request<Invitation>("/admin/invitations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  revokeInvitation: (id: string) =>
    request<Invitation>(`/admin/invitations/${id}/revoke`, {
      method: "POST",
    }),

  // --- pronunciation ---
  scorePronunciation: async (
    audio: Blob,
    referenceText: string,
    language: string,
  ): Promise<PronunciationScoreResponse> => {
    const fd = new FormData();
    fd.append("audio", audio, "user.webm");
    fd.append("reference_text", referenceText);
    fd.append("language", language);
    const resp = await fetch(`${API_BASE}/pronunciation/score`, {
      method: "POST",
      credentials: "include",
      headers: { "Accept-Language": i18n.language || "es" },
      body: fd,
    });
    if (resp.status === 401) {
      for (const fn of unauthorizedListeners) fn();
      throw new AuthRequiredError();
    }
    if (!resp.ok) {
      let detail: string;
      try {
        const body = await resp.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch {
        detail = await resp.text();
      }
      throw new ApiError(resp.status, detail || `${resp.status} ${resp.statusText}`);
    }
    return resp.json() as Promise<PronunciationScoreResponse>;
  },

  /**
   * Best-effort: returns `{}` if the LLM is unreachable, the response was
   * malformed, etc. The endpoint itself swallows errors and returns 200
   * with an empty `hints` object.
   */
  getPhoneticHints: (words: string[], language: string) =>
    request<PhoneticHintsResponse>("/pronunciation/phonetic-hints", {
      method: "POST",
      body: JSON.stringify({ words, language }),
    }),

  /**
   * Corrective tip for the single worst mispronounced word. Best-effort: the
   * endpoint returns `{tip: "", weakest_phoneme: ""}` on any failure, so the
   * caller keeps showing the stress hint.
   */
  diagnose: (word: string, phonemes: PhonemeScore[], language: string) =>
    request<DiagnoseResponse>("/pronunciation/diagnose", {
      method: "POST",
      body: JSON.stringify({ word, phonemes, language }),
    }),

  // --- finish quiz + insight + attempts ---
  getStoryQuiz: (storyId: string) =>
    request<QuizResponse>(`/stories/${storyId}/quiz`),

  getStoryInsight: (storyId: string) =>
    request<InsightResponse | null>(`/stories/${storyId}/insight`),

  getStoryKlaraNote: (storyId: string) =>
    request<KlaraNoteResponse | null>(`/stories/${storyId}/klara-note`),

  getStoryL1Notes: (storyId: string) =>
    request<L1GenderNotesResponse>(`/stories/${storyId}/gender/l1-notes`),

  recordPronunciationAttempt: (storyId: string, payload: PronunciationAttemptIn) =>
    request<void>(`/stories/${storyId}/pronunciation/attempts`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  recordQuizAttempt: (storyId: string, payload: QuizAttemptIn) =>
    request<void>(`/stories/${storyId}/quiz/attempts`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  recordGenderAttempt: (storyId: string, payload: GenderAttemptIn) =>
    request<GenderAttemptOut>(`/stories/${storyId}/gender/attempts`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  genderReview: (limit = 20) => request<GenderReviewItem[]>(`/gender/review?limit=${limit}`),

  gradeGender: (payload: GenderAttemptIn) =>
    request<GenderAttemptOut>("/gender/attempts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getStorySchedule: (storyId: string) =>
    request<ScheduleResponse>(`/stories/${storyId}/schedule`),

  resolveMC: async (
    storyId: string,
    audio: Blob,
    options: string[],
    language: string,
  ): Promise<MCResolveResponse> => {
    const fd = new FormData();
    fd.append("audio", audio, "mc.webm");
    fd.append("options", JSON.stringify(options));
    fd.append("language", language);
    const resp = await fetch(`${API_BASE}/stories/${storyId}/quiz/resolve-mc`, {
      method: "POST",
      credentials: "include",
      headers: { "Accept-Language": i18n.language || "es" },
      body: fd,
    });
    if (resp.status === 401) {
      for (const fn of unauthorizedListeners) fn();
      throw new AuthRequiredError();
    }
    if (!resp.ok) {
      let detail: string;
      try {
        const body = await resp.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch {
        detail = await resp.text();
      }
      throw new ApiError(resp.status, detail || `${resp.status} ${resp.statusText}`);
    }
    return resp.json() as Promise<MCResolveResponse>;
  },

  // --- speak (voice conversation) ---

  /**
   * One conversation turn: audio in, assessment + Klara's reply out.
   * Hard 60s client deadline (the backend chains ffmpeg + Azure + LLM; the
   * state machine needs a guaranteed exit from "thinking"), composed with
   * the caller's abort signal for unmount teardown.
   */
  speakTurn: async (
    audio: Blob,
    opts: {
      language: string;
      focusSound: string;
      focusExamples: string[];
      history: SpeakHistoryTurn[];
      retryWord?: string;
      signal?: AbortSignal;
    },
  ): Promise<SpeakTurnResponse> => {
    const fd = new FormData();
    fd.append("audio", audio, "turn.webm");
    fd.append("language", opts.language);
    fd.append("focus_sound", opts.focusSound);
    fd.append("focus_examples", opts.focusExamples.join(","));
    fd.append("history", JSON.stringify(opts.history));
    if (opts.retryWord) fd.append("retry_word", opts.retryWord);

    const signals = [AbortSignal.timeout(60_000)];
    if (opts.signal) signals.push(opts.signal);
    const resp = await fetch(`${API_BASE}/speak/turn`, {
      method: "POST",
      credentials: "include",
      headers: { "Accept-Language": i18n.language || "es" },
      body: fd,
      signal: AbortSignal.any(signals),
    });
    if (resp.status === 401) {
      for (const fn of unauthorizedListeners) fn();
      throw new AuthRequiredError();
    }
    if (!resp.ok) {
      let detail: string;
      try {
        const body = await resp.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch {
        detail = await resp.text();
      }
      throw new ApiError(resp.status, detail || `${resp.status} ${resp.statusText}`);
    }
    return resp.json() as Promise<SpeakTurnResponse>;
  },

  speakFinish: (payload: SpeakFinishRequest) =>
    request<SpeakFinishResponse>("/speak/finish", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
