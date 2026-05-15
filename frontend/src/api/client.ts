import i18n from "../i18n";
import type { CardOut, Story, StoryListItem, User, UserUpdate } from "./types";

const API_BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": i18n.language || "es",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!resp.ok) {
    let detail: string;
    try {
      const body = await resp.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      detail = await resp.text();
    }
    throw new Error(`${resp.status} ${resp.statusText}: ${detail}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  getMe: () => request<User>("/me"),

  updateMe: (patch: UserUpdate) =>
    request<User>("/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
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
};
