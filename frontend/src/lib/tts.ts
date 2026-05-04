let currentAudio: HTMLAudioElement | null = null;

function ttsUrl(text: string): string {
  return `/api/v1/tts?text=${encodeURIComponent(text)}`;
}

export async function speakGerman(text: string, opts: { rate?: number } = {}): Promise<void> {
  if (!text.trim()) return;
  stopSpeaking();
  const audio = new Audio(ttsUrl(text));
  audio.preload = "auto";
  if (opts.rate) audio.playbackRate = opts.rate;
  currentAudio = audio;
  try {
    await audio.play();
  } catch (err) {
    console.warn("TTS playback failed, falling back to Web Speech", err);
    fallbackWebSpeech(text);
  }
}

export function stopSpeaking(): void {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

export function preloadAudio(text: string): void {
  if (!text.trim()) return;
  const a = new Audio(ttsUrl(text));
  a.preload = "auto";
}

function fallbackWebSpeech(text: string): void {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(text);
  const voice = window.speechSynthesis
    .getVoices()
    .find((v) => v.lang?.toLowerCase().startsWith("de"));
  if (voice) utter.voice = voice;
  utter.lang = voice?.lang ?? "de-DE";
  utter.rate = 0.95;
  window.speechSynthesis.speak(utter);
}
