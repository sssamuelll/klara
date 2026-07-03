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

export interface WordBreakdown {
  word: string;
  translation: string;
  pos?: string | null;
}

export interface StorySentence {
  target: string;
  native: string;
  new_words: string[];
  /**
   * Per-word translations for the in-sentence tooltip. Optional — older
   * stories generated before this field existed don't have it; the UI
   * falls back to making only LLM-flagged target_words tappable.
   */
  breakdown?: WordBreakdown[] | null;
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
  frequency_rank: number | null;
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
  module_id?: string | null;
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

export interface DiagnoseRequest {
  language: string;
  word: string;
  phonemes: PhonemeScore[];
}

export interface DiagnoseResponse {
  tip: string;
  weakest_phoneme: string;
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

export interface GenderClozeQuizItem {
  type: "gender_cloze";
  cap: string;
  lemma: string;
  vocab_item_id: string;
  en?: string | null;
}

export interface GenderReviewItem {
  vocab_item_id: string;
  lemma: string;
  en?: string | null;
}

export type QuizItem =
  | MCQuizItem
  | ClozeQuizItem
  | ShadowQuizItem
  | GenderClozeQuizItem;

export interface QuizResponse {
  items: QuizItem[];
}

export interface InsightResponse {
  title: string;
  body: string;
}

export interface KlaraNoteResponse {
  body: string;
}

export interface L1GenderNote {
  lemma: string;
  gender: "der" | "die" | "das";
  note: string;
}

export interface L1GenderNotesResponse {
  notes: L1GenderNote[];
}

export interface PronunciationAttemptIn {
  sentence_index: number;
  reference_text: string;
  recognized_text?: string | null;
  overall_score: number;
  word_bands: Record<string, "good" | "ok" | "bad">;
}

export interface GenderAttemptIn {
  vocab_item_id: string;
  picked_article: "der" | "die" | "das";
}

export interface GenderRule {
  suffix: string;
  suffix_class: "hard" | "tendency";
  rule_gender: "der" | "die" | "das";
  is_exception: boolean;
}

export interface GenderAttemptOut {
  was_correct: boolean;
  correct_gender: string;
  rule?: GenderRule | null;
}

export interface QuizAttemptIn {
  question_index: number;
  // No "gender_cloze": gender is graded server-side via recordGenderAttempt, not
  // through this client-trusted generic attempt. The Quiz dispatcher guards the
  // recordQuizAttempt call with `q.type !== "gender_cloze"`, which narrows q.type
  // to these three at the call site.
  question_type: "mc" | "cloze" | "shadow";
  was_correct: boolean;
  was_revealed?: boolean;
  detail?: Record<string, unknown> | null;
}

export type ScheduleBucket =
  | "not_in_srs"
  | "due_now"
  | "soon"
  | "this_week"
  | "next_week"
  | "later";

export interface ScheduleEntry {
  vocab_item_id: string;
  has_card: boolean;
  bucket: ScheduleBucket;
  next_review_at: string | null;
}

export interface ScheduleResponse {
  entries: ScheduleEntry[];
}

export interface MCResolveResponse {
  transcript: string;
  picked_index: number | null;
  option_scores: number[];
}

export interface UserUpdate {
  display_name?: string;
  level?: CEFRLevel;
  native_language?: LanguageCode;
  target_language?: LanguageCode;
  learning_context?: string | null;
}

export interface PronunciationReviewIn {
  cardId: string;
  focusText: string;
  sentenceTarget: string;
  wordBands: Record<number, "bad" | "ok" | "good">;
}

export interface RescheduledCard {
  focusText: string;
  intervalDays: number;
  nextReviewAt: string; // ISO 8601
}

export interface PronunciationBatchOut {
  rescheduled: RescheduledCard[];
}

// ---- Speak (voice conversation) — camelCase, serialized via aliases ------

export type SpeakBand = "good" | "ok" | "bad";

export interface SpeakToken {
  t: string;
  s: SpeakBand;
  focus: boolean;
}

export interface SpeakTarget {
  word: string;
  gloss: string | null;
  focusAccuracy: number;
  shouldIpa: string;
  modelSentence: string | null;
}

export interface SpeakReply {
  target: string;
  native: string;
}

/**
 * Discriminated on noSpeech: when true, every other field is default/null —
 * branch on it FIRST. lowConfidence carries the transcript but no
 * target/reply (the recognition is too shaky to correct honestly).
 */
export interface SpeakTurnResponse {
  noSpeech: boolean;
  lowConfidence: boolean;
  recognizedText: string;
  tokens: SpeakToken[];
  scores: { accuracy: number; fluency: number; pronunciation: number } | null;
  target: SpeakTarget | null;
  focusHit: boolean;
  focusClear: boolean;
  reply: SpeakReply | null;
}

export interface SpeakHistoryTurn {
  who: "klara" | "you";
  text: string;
}

export interface SpeakFinishWord {
  word: string;
  gloss: string | null;
  modelSentence: string | null;
}

export interface SpeakFinishRequest {
  language: string;
  focusSound: string;
  clearCount: number;
  totalCount: number;
  durationSeconds: number;
  words: SpeakFinishWord[];
}

export interface SpeakFinishResponse {
  added: number;
  skipped: number;
}

export interface ModuleCurrent {
  id: string;
  title: string;
  cefr_level: string;
  can_dos: string[];
  grammatical_focus: string[];
  encountered: number;
  mastered: number;
  total: number;
}

export interface ModulePathItem {
  id: string;
  sequence_order: number;
  title: string;
  cefr_level: string;
  can_dos: string[];
  grammatical_focus: string[];
  encountered: number;
  mastered: number;
  total: number;
  gender_encountered: number;
  gender_mastered: number;
  gender_total: number;
  stories_finished: number;
  stories_to_complete: number;
  completed: boolean;
  is_current: boolean;
  unlocked: boolean;
  library_available: number;
}
