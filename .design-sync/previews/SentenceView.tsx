import { SentenceView } from "klara-frontend";

// La superficie de lectura: una oración a la vez, en serif grande, con el dock
// de transporte abajo. Cuando el usuario habla, cada palabra recibe una banda
// (good/ok/bad) que se pinta como subrayado de 3px bajo la palabra — el puntaje
// vive junto al texto, nunca en un panel aparte.

const oracion = {
  target: "Am Montag fahre ich mit dem Zug nach Berlin.",
  native: "El lunes viajo en tren a Berlín.",
  new_words: ["Zug"],
  breakdown: [
    { word: "Am", translation: "el", pos: "preposition" },
    { word: "Montag", translation: "lunes", pos: "noun" },
    { word: "fahre", translation: "viajo", pos: "verb" },
    { word: "ich", translation: "yo", pos: "pronoun" },
    { word: "mit", translation: "con", pos: "preposition" },
    { word: "dem", translation: "el", pos: "article" },
    { word: "Zug", translation: "tren", pos: "noun" },
    { word: "nach", translation: "a", pos: "preposition" },
    { word: "Berlin", translation: "Berlín", pos: "noun" },
  ],
};

const zug = {
  id: "w-zug",
  lemma: "Zug",
  pos: "noun",
  gender: "der",
  plural: "Züge",
  translation: "tren",
  example_target: "Der Zug fährt um acht Uhr ab.",
  frequency_rank: 812,
};

const base = {
  storyTitle: "Die Reise nach Berlin",
  storyLevel: "A2",
  onExit: () => {},
  sentence: oracion,
  index: 3,
  total: 9,
  targetLanguage: "de",
  lemmaIndex: { Zug: "w-zug" },
  wordsById: { "w-zug": zug },
  activeWordKey: null,
  onWordTap: () => {},
  playing: false,
  progress: 0,
  duration: 0,
  recording: false,
  micAnalyser: null,
  micLevel: "ok" as const,
  evaluating: false,
  diagnosing: false,
  rate: 1,
  onPlayPause: () => {},
  onCycleSpeed: () => {},
  onRecordStart: () => {},
  onRecordStop: () => {},
  onRetry: () => {},
  onListenFromFeedback: () => {},
  onPrev: () => {},
  onNext: () => {},
  canPrev: true,
  canNext: true,
};

const Telefono = ({ children }: { children: React.ReactNode }) => (
  <div style={{ width: 390, height: 720, border: "1px solid var(--rule)", background: "var(--paper)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
    {children}
  </div>
);

export const Leyendo = () => (
  <Telefono>
    <SentenceView {...base} />
  </Telefono>
);

export const Sonando = () => (
  <Telefono>
    <SentenceView {...base} playing progress={0.42} duration={4.6} />
  </Telefono>
);

export const ConCorreccion = () => (
  <Telefono>
    <SentenceView
      {...base}
      feedback={{ 0: "good", 1: "good", 2: "ok", 3: "good", 4: "good", 5: "good", 6: "bad", 7: "good", 8: "good" }}
      phoneticHints={{ Zug: "tsuːk" }}
      diagnosis={{ word: "Zug", tip: "La <z> alemana suena /ts/, no /s/: «tsuːk»." }}
    />
  </Telefono>
);

// micLevel="quiet" a propósito: es el único nivel con copy real en los locales.
// Con "ok" el componente pinta la clave cruda story.sentence.micLevel.ok — ver
// NOTES.md, es un bug de Klara, no de esta preview.
export const Grabando = () => (
  <Telefono>
    <SentenceView {...base} recording micLevel="quiet" />
  </Telefono>
);
