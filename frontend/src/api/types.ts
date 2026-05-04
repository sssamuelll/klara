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
  de: string;
  es: string;
  new_words: string[];
}

export interface ComprehensionQuestion {
  q_de: string;
  q_es: string;
  options_de: string[];
  correct_index: number;
}

export interface StoryWord {
  id: string;
  lemma: string;
  pos: PartOfSpeech;
  gender: string | null;
  plural: string | null;
  translation_es: string | null;
  example_de: string | null;
}

export interface StoryContent {
  sentences: StorySentence[];
  comprehension_questions: ComprehensionQuestion[];
}

export interface Story {
  id: string;
  level: CEFRLevel;
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
  title: string;
  created_at: string;
}

export interface CardOut {
  id: string;
  vocab_item_id: string;
  lemma: string;
  pos: PartOfSpeech;
  translation_es: string | null;
  example_de: string | null;
  state: "new" | "learning" | "reviewing" | "relearning" | "suspended";
  interval_days: number;
  next_review_at: string | null;
  repetitions: number;
}
