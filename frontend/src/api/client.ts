import i18n from "../i18n";
import type {
  CardOut,
  Invitation,
  InvitationCreate,
  PronunciationScoreResponse,
  Story,
  StoryListItem,
  User,
  UserUpdate,
} from "./types";

const API_BASE = "/api/v1";

class ApiError extends Error {
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

  createStory: (topic?: string) =>
    request<Story>("/stories", {
      method: "POST",
      body: JSON.stringify({ topic: topic ?? null }),
    }),

  addCard: (vocabItemId: string) =>
    request<CardOut>("/srs/cards", {
      method: "POST",
      body: JSON.stringify({ vocab_item_id: vocabItemId }),
    }),

  dueCards: (limit = 20) => request<CardOut[]>(`/srs/cards/due?limit=${limit}`),

  reviewCard: (cardId: string, rating: "again" | "hard" | "good" | "easy") =>
    request(`/srs/cards/${cardId}/review`, {
      method: "POST",
      body: JSON.stringify({ rating }),
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
};
