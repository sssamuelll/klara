import i18n from "../i18n";
import type { PracticeQueue } from "../lib/practiceQueue";
import { apiBase } from "../lib/apiBase";
import { authHeaders, clearToken, isNative, setToken } from "../lib/native";
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
  LearnerProfileIn,
  LearnerProfileOut,
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
  StoryDifficultyValue,
  StoryListItem,
  StudyCardOut,
  TallerBulkOut,
  TallerCardList,
  TallerOverview,
  TodayOut,
  User,
  UserUpdate,
  WaitlistRow,
} from "./types";

export class ApiError extends Error {
  status: number;
  /**
   * Machine-readable cause, when the backend sent a structured `detail`
   * (currently the audio quality gate: {error, reason, reasons, message}).
   * Classifiers should branch on this, never on the human message.
   */
  reason?: string;
  constructor(status: number, message: string, reason?: string) {
    super(message);
    this.status = status;
    this.reason = reason;
  }
}

/**
 * Turn a failed audio response into an ApiError. `detail` is a plain string on
 * most endpoints, but the audio quality gate sends an object — reading that
 * with `body.detail ?? …` stringified it to "[object Object]" and threw the
 * reason away, which is why every gate rejection looked like "speak louder".
 */
async function audioApiError(resp: Response): Promise<ApiError> {
  let message = "";
  let reason: string | undefined;
  try {
    const body = await resp.json();
    const detail = body?.detail;
    if (detail !== null && typeof detail === "object") {
      message = typeof detail.message === "string" ? detail.message : "";
      reason = typeof detail.reason === "string" ? detail.reason : undefined;
    } else {
      message = typeof detail === "string" ? detail : JSON.stringify(body);
    }
  } catch {
    message = await resp.text();
  }
  return new ApiError(resp.status, message || `${resp.status} ${resp.statusText}`, reason);
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

async function handleUnauthorized(): Promise<never> {
  // The bearer is dead server-side; keeping it means replaying it after
  // every restart. Clearing is a no-op on the web, where there is none.
  await clearToken();
  for (const fn of unauthorizedListeners) fn();
  throw new AuthRequiredError();
}

/**
 * Base headers, then the caller's, then the session's — in that order, through
 * the Headers API rather than object spread.
 *
 * Object spread was wrong in three ways that all end as a silent logout: it
 * cannot merge a `Headers` instance or an array of tuples at all, it treats
 * `authorization` and `Authorization` as two different keys, and whichever side
 * came last simply won. The session's Authorization is applied last and on
 * purpose: a caller may override Content-Type, never the credential.
 *
 * Exported for its own tests — no caller passes init.headers today, which is
 * exactly why this needs pinning before one does.
 */
export function mergeHeaders(
  init: HeadersInit | undefined,
  session: Record<string, string>,
): Headers {
  const headers = new Headers({
    "Content-Type": "application/json",
    "Accept-Language": i18n.language || "es",
  });
  if (init) new Headers(init).forEach((value, key) => headers.set(key, value));
  for (const [key, value] of Object.entries(session)) headers.set(key, value);
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    credentials: "include",
    ...init,
    headers: mergeHeaders(init?.headers, await authHeaders()),
  });
  if (resp.status === 401) await handleUnauthorized();
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
    // Same credentials, two transports: the cookie one on the web, the
    // revocable bearer one inside the shell, where there is no cookie jar.
    const path = isNative() ? "/auth/bearer/login" : "/auth/jwt/login";
    const resp = await fetch(`${apiBase()}${path}`, {
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
    if (isNative()) {
      const data = (await resp.json()) as { access_token: string };
      await setToken(data.access_token);
    }
  },

  logout: async (): Promise<void> => {
    const path = isNative() ? "/auth/bearer/logout" : "/auth/jwt/logout";
    try {
      await request<void>(path, { method: "POST" });
    } finally {
      // Even if the round trip failed, the phone forgets the token. The server
      // session outlives it until expiry, but the safe failure is the device
      // holding nothing.
      await clearToken();
    }
  },

  googleNative: async (idToken: string): Promise<string> => {
    const data = await request<{ access_token: string }>("/auth/google/native", {
      method: "POST",
      body: JSON.stringify({ id_token: idToken }),
    });
    return data.access_token;
  },

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

  /** 404 = nunca llenado. Devuelve null en vez de tirar: «sin llenar» es un
   *  estado legítimo del perfil, no un error que haya que reportar. */
  getLearningProfile: async (): Promise<LearnerProfileOut | null> => {
    try {
      return await request<LearnerProfileOut>("/me/learning-profile");
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },

  /** `expectedVersion` va solo cuando el perfil ya existe; sin él, un perfil
   *  existente responde 409 en vez de dejar que dos pestañas se pisen. */
  putLearningProfile: (body: LearnerProfileIn, expectedVersion?: number) =>
    request<LearnerProfileOut>(
      `/me/learning-profile${expectedVersion === undefined ? "" : `?expected_version=${expectedVersion}`}`,
      { method: "PUT", body: JSON.stringify(body) }
    ),

  listModules: () => request<ModulePathItem[]>("/modules"),

  today: (since: string) => request<TodayOut>(`/today?since=${encodeURIComponent(since)}`),

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

  // --- waitlist ---
  listWaitlist: () => request<WaitlistRow[]>("/admin/waitlist"),

  markWaitlistInvited: (id: string) =>
    request<WaitlistRow>(`/admin/waitlist/${id}/invited`, {
      method: "POST",
    }),

  joinWaitlist: (email: string, locale: string) =>
    request<{ ok: boolean }>("/waitlist", {
      method: "POST",
      body: JSON.stringify({ email, locale }),
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
    const resp = await fetch(`${apiBase()}/pronunciation/score`, {
      method: "POST",
      credentials: "include",
      headers: { "Accept-Language": i18n.language || "es", ...(await authHeaders()) },
      body: fd,
    });
    if (resp.status === 401) await handleUnauthorized();
    if (!resp.ok) throw await audioApiError(resp);
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

  setStoryDifficulty: (storyId: string, value: StoryDifficultyValue) =>
    request<{ value: StoryDifficultyValue }>(`/stories/${storyId}/difficulty`, {
      method: "POST",
      body: JSON.stringify({ value }),
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
    const resp = await fetch(`${apiBase()}/stories/${storyId}/quiz/resolve-mc`, {
      method: "POST",
      credentials: "include",
      headers: { "Accept-Language": i18n.language || "es", ...(await authHeaders()) },
      body: fd,
    });
    if (resp.status === 401) await handleUnauthorized();
    if (!resp.ok) throw await audioApiError(resp);
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
      sessionId?: string;
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
    if (opts.sessionId) fd.append("session_id", opts.sessionId);

    const signals = [AbortSignal.timeout(60_000)];
    if (opts.signal) signals.push(opts.signal);
    const resp = await fetch(`${apiBase()}/speak/turn`, {
      method: "POST",
      credentials: "include",
      headers: { "Accept-Language": i18n.language || "es", ...(await authHeaders()) },
      body: fd,
      signal: AbortSignal.any(signals),
    });
    if (resp.status === 401) await handleUnauthorized();
    if (!resp.ok) throw await audioApiError(resp);
    return resp.json() as Promise<SpeakTurnResponse>;
  },

  speakFinish: (payload: SpeakFinishRequest) =>
    request<SpeakFinishResponse>("/speak/finish", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- el taller (F0) ---
  tallerOverview: () => request<TallerOverview>("/taller/overview"),

  createTallerCard: (front: string, back: string, tags: string[], batchId: string) =>
    request<StudyCardOut>("/taller/cards", {
      method: "POST",
      body: JSON.stringify({ front, back, tags, batch_id: batchId }),
    }),

  createTallerCardsBulk: (
    cards: { front: string; back: string }[],
    tags: string[],
    batchId: string,
  ) =>
    request<TallerBulkOut>("/taller/cards/bulk", {
      method: "POST",
      body: JSON.stringify({ cards, tags, batch_id: batchId }),
    }),

  listTallerCards: (opts?: { tag?: string; limit?: number; offset?: number }) => {
    const params = new URLSearchParams();
    if (opts?.tag) params.set("tag", opts.tag);
    if (opts?.limit !== undefined) params.set("limit", String(opts.limit));
    if (opts?.offset !== undefined) params.set("offset", String(opts.offset));
    const qs = params.toString();
    return request<TallerCardList>(`/taller/cards${qs ? `?${qs}` : ""}`);
  },

  dueTallerCards: (limit = 20) => request<StudyCardOut[]>(`/taller/cards/due?limit=${limit}`),

  reviewTallerCard: (
    cardId: string,
    rating: ReviewRating,
    device: "desktop" | "mobile",
    elapsedSeconds?: number,
  ) =>
    request<StudyCardOut>(`/taller/cards/${cardId}/review`, {
      method: "POST",
      body: JSON.stringify(
        elapsedSeconds === undefined
          ? { rating, device }
          : { rating, device, elapsed_seconds: elapsedSeconds },
      ),
    }),

  archiveTallerCard: (cardId: string) =>
    request<void>(`/taller/cards/${cardId}/archive`, { method: "POST" }),

  // TSV crudo, no JSON — bypassa request() (mismo patrón que login()).
  exportTaller: async (): Promise<string> => {
    const resp = await fetch(`${apiBase()}/taller/export`, {
      credentials: "include",
      headers: await authHeaders(),
    });
    if (resp.status === 401) await handleUnauthorized();
    if (!resp.ok) {
      const text = await resp.text();
      throw new ApiError(resp.status, `${resp.status} ${resp.statusText}: ${text}`);
    }
    return resp.text();
  },
};
