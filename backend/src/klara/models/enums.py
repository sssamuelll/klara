from enum import StrEnum


class CEFRLevel(StrEnum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"


class PartOfSpeech(StrEnum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    PRONOUN = "pronoun"
    PREPOSITION = "preposition"
    CONJUNCTION = "conjunction"
    ARTICLE = "article"
    PHRASE = "phrase"
    OTHER = "other"


class CardState(StrEnum):
    NEW = "new"
    LEARNING = "learning"
    REVIEWING = "reviewing"
    RELEARNING = "relearning"
    SUSPENDED = "suspended"


class ReviewRating(StrEnum):
    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class SessionType(StrEnum):
    STORY = "story"
    REVIEW = "review"
    CHAT = "chat"
    MIXED = "mixed"
