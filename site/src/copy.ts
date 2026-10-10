export type Lang = 'en' | 'es';

export interface Screen {
  key: 'today' | 'read' | 'speak' | 'review';
  title: string;
  body: string;
  alt: string;
}

export interface MapTile {
  key: 'ja' | 'de' | 'en';
  glyph: string;
  mono?: boolean;
  title: string;
  body: string;
}

export interface PageCopy {
  /** Prefijo relativo a los assets de `public/` desde esta página. */
  assetBase: './' | '../';
  homeHref: string;
  thisLabel: string;
  otherLabel: string;
  otherLang: Lang;
  otherHref: string;
  navLabel: string;
  code: string;
  hero: { title: string; dek: string };
  why: { cap: string; paragraphs: string[] };
  screens: { cap: string; items: Screen[] };
  maps: { cap: string; badge: string; intro: string; tiles: MapTile[] };
  made: {
    cap: string;
    badges: string[];
    rows: [string, string][];
    alert: string;
    code: string;
    run: string;
  };
  footer: { email: string };
}

export const copy: Record<Lang, PageCopy> = {
  en: {
    assetBase: './',
    homeHref: './',
    thisLabel: 'EN',
    otherLabel: 'ES',
    otherLang: 'es',
    otherHref: './es/',
    navLabel: 'Language and code',
    code: 'Code',
    hero: {
      title: 'Your study library',
      dek: 'Read, speak, review. Every course is shaped to the way you learn.',
    },
    why: {
      cap: 'Why it exists',
      paragraphs: [
        "I'm learning German and Japanese, and improving my English. The apps I tried asked me back every day so I wouldn't lose a streak. I wanted to have a conversation. So I built the tutor I wanted.",
        "Every day Klara writes me a short story at my level. I read it and tap the words I don't know. I read it out loud and Klara tells me which sound missed, the ö, the ch, and how to make it. Days later the words come back as cards, right before I'd forget them. No streaks, no hearts, no guilt. A magazine that learns with me.",
        "It's my own tool, and the code is open. If you want one, run it with your own keys.",
      ],
    },
    screens: {
      cap: 'What it does',
      items: [
        { key: 'today', title: 'Today', body: "Your route for the day, with the story's own illustration at the stop you're at.", alt: "Klara on a phone: today's plan as a route with its stops: read, pronounce, speak, review." },
        { key: 'read', title: 'Read', body: "Short stories in the language you're studying. Tap any word to open it: meaning, gender, context.", alt: 'Klara on a phone: a short German story with one word opened, showing its meaning and its part of speech.' },
        { key: 'speak', title: 'Speak', body: 'You talk and Klara corrects the exact sound that missed. What you said yesterday, it remembers today.', alt: "Klara on a phone: the day's conversation, with Klara's opening line in German, its Spanish gloss and the microphone ready." },
        { key: 'review', title: 'Review', body: "Flashcards that come back right before you'd forget. No streaks, no hearts, no guilt.", alt: 'Klara on a phone: a review card asking for the gender of a German noun.' },
      ],
    },
    maps: {
      cap: 'Three languages, three maps',
      badge: 'In the works',
      intro: 'Each language gets its own map, and every lesson is built from drills that teach one thing well. Klara keeps track of what you master, facet by facet.',
      tiles: [
        { key: 'ja', glyph: 'あ', title: 'Hiragana', body: 'Trace each kana with your finger until the stroke is yours.' },
        { key: 'de', glyph: 'der · die · das', mono: true, title: 'der, die, das', body: 'Pick the article by case.' },
        { key: 'en', glyph: 'ship · sheep', title: 'ship, sheep', body: "Hear the sounds Spanish doesn't have, and tell them apart." },
      ],
    },
    made: {
      cap: "How it's made",
      badges: ['MIT', '6 languages', 'Invitation only'],
      rows: [
        ['Languages', 'six in the interface, any of them as the one you study'],
        ['Tutor', 'whichever model you give a key for: Anthropic, DeepSeek or OpenAI'],
        ['Voice', 'ElevenLabs or Inworld'],
        ['Pronunciation', 'scored sound by sound'],
        ['Runs', 'with Docker Compose and your own keys'],
        ['License', 'MIT'],
      ],
      alert: 'My instance is invitation only. To run yours, start at the README.',
      code: 'See the code',
      run: 'Run it yourself',
    },
    footer: { email: 'Email me' },
  },
  es: {
    assetBase: '../',
    homeHref: './',
    thisLabel: 'ES',
    otherLabel: 'EN',
    otherLang: 'en',
    otherHref: '../',
    navLabel: 'Idioma y código',
    code: 'Código',
    hero: {
      title: 'Tu biblioteca de estudio',
      dek: 'Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú.',
    },
    why: {
      cap: 'Por qué existe',
      paragraphs: [
        'Estoy aprendiendo alemán y japonés, y mejorando mi inglés. Las apps que probé me pedían volver cada día para no perder la racha. Yo quería tener una conversación. Así que construí la tutora que quería.',
        'Cada día Klara me escribe una historia corta a mi nivel. La leo y toco las palabras que no sé. La leo en voz alta y Klara me dice qué sonido falló, la ö, la ch, y cómo se hace. Días después las palabras vuelven en fichas, justo antes de que se me olviden. Sin rachas, sin corazones, sin culpa. Una revista que aprende conmigo.',
        'Es mi herramienta, y el código está abierto. Si quieres una, móntala con tus propias llaves.',
      ],
    },
    screens: {
      cap: 'Qué hace',
      items: [
        { key: 'today', title: 'Hoy', body: 'Tu recorrido del día, con la ilustración de la historia en la parada en la que estás.', alt: 'Klara en un teléfono: el plan de hoy como un recorrido con sus paradas: leer, pronunciar, hablar, repasar.' },
        { key: 'read', title: 'Leer', body: 'Historias cortas en el idioma que estudias. Cada palabra se abre con un toque: significado, género, contexto.', alt: 'Klara en un teléfono: una historia corta en alemán con una palabra abierta, con su significado y su categoría gramatical.' },
        { key: 'speak', title: 'Hablar', body: 'Conversas y Klara te corrige el sonido exacto que falló. Lo que dijiste ayer lo recuerda hoy.', alt: 'Klara en un teléfono: la conversación del día, con la frase de apertura de Klara en alemán, su glosa en español y el micrófono listo.' },
        { key: 'review', title: 'Repasar', body: 'Fichas que vuelven justo antes del olvido. Sin rachas, sin corazones, sin culpa.', alt: 'Klara en un teléfono: una ficha de repaso que pregunta el género de un sustantivo alemán.' },
      ],
    },
    maps: {
      cap: 'Tres idiomas, tres mapas',
      badge: 'En construcción',
      intro: 'Cada idioma tiene su propio mapa, y cada lección se arma con dinámicas que enseñan una sola cosa bien. Klara lleva la cuenta de lo que dominas, faceta por faceta.',
      tiles: [
        { key: 'ja', glyph: 'あ', title: 'Hiragana', body: 'Traza cada kana con el dedo hasta que el trazo sea tuyo.' },
        { key: 'de', glyph: 'der · die · das', mono: true, title: 'der, die, das', body: 'Elige el artículo según el caso.' },
        { key: 'en', glyph: 'ship · sheep', title: 'ship, sheep', body: 'Escucha los sonidos que el español no tiene y distínguelos.' },
      ],
    },
    made: {
      cap: 'Cómo está hecha',
      badges: ['MIT', '6 idiomas', 'Por invitación'],
      rows: [
        ['Idiomas', 'seis en la interfaz, cualquiera como el que estudias'],
        ['Tutora', 'el modelo al que le des una llave: Anthropic, DeepSeek u OpenAI'],
        ['Voz', 'ElevenLabs o Inworld'],
        ['Pronunciación', 'calificada sonido por sonido'],
        ['Corre', 'con Docker Compose y tus llaves'],
        ['Licencia', 'MIT'],
      ],
      alert: 'Mi instancia es por invitación. Para montar la tuya, empieza por el README.',
      code: 'Ver el código',
      run: 'Móntala tú',
    },
    footer: { email: 'Escríbeme' },
  },
};
