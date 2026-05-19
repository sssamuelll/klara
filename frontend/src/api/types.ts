import type { LanguageCode } from "../lib/languages";

export type { LanguageCode };

export type CEFRLevel = "A0" | "A1" | "A2" | "B1" | "B2" | "C1";

export type PartOfSpeech =
  | "noun"
  | "verb"
  | "adjective"
  | "adverb"
  | "pronoun"
  | "preposition"
  | "conjunction"
  | "article"
  | "phrase"
  | "other";

export type ReviewRating = "again" | "hard" | "good" | "easy";

export interface StorySentence {
  target: string;
  native: string;
  new_words: string[];
}

export interface ComprehensionQuestion {
  q_target: string;
  q_native: string;
  options_target: string[];
  correct_index: number;
}

export interface StoryWord {
  id: string;
  lemma: string;
  pos: PartOfSpeech;
  gender: string | null;
  plural: string | null;
  translation: string | null;
  example_target: string | null;
}

export interface StoryContent {
  sentences: StorySentence[];
  comprehension_questions: ComprehensionQuestion[];
}

export interface Story {
  id: string;
  level: CEFRLevel;
  target_language: LanguageCode;
  native_language: LanguageCode;
  title: string;
  content: StoryContent;
  target_words: StoryWord[];
  generated_by_provider: string | null;
  generated_by_model: string | null;
  generation_cost_usd: number | null;
  created_at: string;
}

export interface StoryListItem {
  id: string;
  level: CEFRLevel;
  target_language: LanguageCode;
  title: string;
  created_at: string;
}

export interface CardOut {
  id: string;
  vocab_item_id: string;
  lemma: string;
  pos: PartOfSpeech;
  translation: string | null;
  example_target: string | null;
  state: "new" | "learning" | "reviewing" | "relearning" | "suspended";
  interval_days: number;
  next_review_at: string | null;
  repetitions: number;
}

export type AuthMethod = "password" | "google";

export interface User {
  id: string;
  email: string | null;
  is_superuser: boolean;
  display_name: string;
  level: CEFRLevel;
  native_language: LanguageCode;
  target_language: LanguageCode;
  learning_context: string | null;
  auth_methods: AuthMethod[];
  needs_onboarding: boolean;
}

export type InvitationState = "active" | "expired" | "used" | "revoked";

export interface Invitation {
  id: string;
  token: string;
  email: string | null;
  note: string | null;
  created_at: string;
  expires_at: string;
  used_at: string | null;
  used_by: string | null;
  revoked_at: string | null;
  state: InvitationState;
  share_url: string;
}

export interface InvitationCreate {
  email?: string;
  note?: string;
  ttl_days?: number;
}

export interface PhonemeScore {
  phoneme: string;
  accuracy_score: number;
}

export interface WordScore {
  word: string;
  accuracy_score: number;
  error_type: "None" | "Mispronunciation" | "Omission" | "Insertion" | string;
  phonemes: PhonemeScore[];
}

export interface PronunciationOverallScores {
  accuracy: number;
  fluency: number;
  completeness: number;
  pronunciation: number;
}

export interface PronunciationScoreResponse {
  recognized_text: string;
  reference_text: string;
  language: string;
  scores: PronunciationOverallScores;
  words: WordScore[];
}

export interface PhoneticHintsResponse {
  /** Map of original word → hyphenated stress hint, e.g. "au-to-BÚS". */
  hints: Record<string, string>;
}

// ---- Finish quiz + insight + attempts ----------------------------------

export interface MCQuizItem {
  type: "mc";
  cap: string;
  prompt: string;
  options: string[];
  correct: number;
  after?: string | null;
}

export interface ClozeQuizItem {
  type: "cloze";
  cap: string;
  sentence_pre: string;
  sentence_post: string;
  answer: string;
  en?: string | null;
  hint?: string | null;
}

export interface ShadowQuizItem {
  type: "shadow";
  cap: string;
  sentence: string;
  en?: string | null;
  after?: string | null;
}

export type QuizItem = MCQuizItem | ClozeQuizItem | ShadowQuizItem;

export interface QuizResponse {
  items: QuizItem[];
}

export interface InsightResponse {
  title: string;
  body: string;
}

export interface PronunciationAttemptIn {
  sentence_index: number;
  reference_text: string;
  recognized_text?: string | null;
  overall_score: number;
  word_bands: Record<string, "good" | "ok" | "bad">;
}

export interface QuizAttemptIn {
  question_index: number;
  question_type: "mc" | "cloze" | "shadow";
  was_correct: boolean;
  was_revealed?: boolean;
  detail?: Record<string, unknown> | null;
}

export interface UserUpdate {
  display_name?: string;
  level?: CEFRLevel;
  native_language?: LanguageCode;
  target_language?: LanguageCode;
  learning_context?: string | null;
}
