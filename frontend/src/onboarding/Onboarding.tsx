import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ComponentType,
} from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import KlaraMark from "../components/KlaraMark";
import {
  INITIAL_DATA,
  WHISPERS,
  type Level,
  type NativeLang,
  type OnboardingData,
  type TargetLang,
} from "./data";
import StepWelcome from "./steps/StepWelcome";
import StepName from "./steps/StepName";
import StepLanguages from "./steps/StepLanguages";
import StepLevel from "./steps/StepLevel";
import StepContext from "./steps/StepContext";
import StepPassword from "./steps/StepPassword";
import StepDone from "./steps/StepDone";

const STORAGE_KEY = "klara:onboarding:draft";

type Direction = "forward" | "backward";

interface DraftShape {
  step: number;
  data: OnboardingData;
}

const NATIVE_CODES: NativeLang[] = ["es", "en", "pt", "fr"];
const TARGET_CODES: TargetLang[] = ["de", "en", "fr", "pt", "ja"];
const LEVEL_CODES: Level[] = ["A0", "A1", "A2", "B1", "B2", "C1"];

function isString(v: unknown): v is string {
  return typeof v === "string";
}

function readDraft(): DraftShape | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    const obj = parsed as Record<string, unknown>;
    const step = typeof obj.step === "number" ? obj.step : 0;
    const d = (obj.data ?? {}) as Record<string, unknown>;

    const native = NATIVE_CODES.includes(d.native as NativeLang)
      ? (d.native as NativeLang)
      : INITIAL_DATA.native;
    const target = TARGET_CODES.includes(d.target as TargetLang)
      ? (d.target as TargetLang)
      : INITIAL_DATA.target;
    const level =
      d.level === null
        ? null
        : LEVEL_CODES.includes(d.level as Level)
          ? (d.level as Level)
          : null;

    const data: OnboardingData = {
      name: isString(d.name) ? d.name : INITIAL_DATA.name,
      native,
      target,
      level,
      context: isString(d.context) ? d.context : INITIAL_DATA.context,
      password: isString(d.password) ? d.password : INITIAL_DATA.password,
      passwordConfirm: isString(d.passwordConfirm)
        ? d.passwordConfirm
        : INITIAL_DATA.passwordConfirm,
    };

    return { step: Math.max(0, Math.floor(step)), data };
  } catch {
    return null;
  }
}

function clearDraft() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function writeDraft(draft: DraftShape) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* ignore */
  }
}

function roman(n: number): string {
  // We never need more than V for chapters here.
  const map = ["—", "I", "II", "III", "IV", "V"];
  return map[n] ?? String(n);
}

export default function Onboarding() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const hasPassword = user?.auth_methods.includes("password") ?? false;

  // Build step list. Welcome is always 0; chapters 1..N; Done is last.
  type ChapterComp = ComponentType<{
    data: OnboardingData;
    setField: <K extends keyof OnboardingData>(k: K, v: OnboardingData[K]) => void;
    next: () => void;
    prev: () => void;
  }>;

  const chapterComponents = useMemo<ChapterComp[]>(() => {
    const base: ChapterComp[] = [StepName, StepLanguages, StepLevel, StepContext];
    if (!hasPassword) base.push(StepPassword);
    return base;
  }, [hasPassword]);

  const total = chapterComponents.length; // visible chapters (5 or 4)
  const lastIndex = total + 1; // Done step

  const initial = useMemo(readDraft, []);

  const [step, setStep] = useState<number>(() => {
    if (!initial) return 0;
    return Math.min(initial.step, lastIndex);
  });
  const [direction, setDirection] = useState<Direction>("forward");
  const [data, setData] = useState<OnboardingData>(
    () => initial?.data ?? INITIAL_DATA,
  );

  // Defensive: if hasPassword changes after mount (e.g. auth refresh sets
  // password), reclamp step.
  useEffect(() => {
    setStep((s) => Math.min(s, lastIndex));
  }, [lastIndex]);

  // Persist on every change.
  useEffect(() => {
    writeDraft({ step, data });
  }, [step, data]);

  const setField = useCallback(
    <K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => {
      setData((d) => ({ ...d, [key]: value }));
    },
    [],
  );

  const goNext = useCallback(() => {
    setDirection("forward");
    setStep((s) => Math.min(s + 1, lastIndex));
  }, [lastIndex]);

  const goPrev = useCallback(() => {
    setDirection("backward");
    setStep((s) => Math.max(s - 1, 0));
  }, []);

  async function handleExit() {
    try {
      await logout();
    } catch {
      /* ignore */
    }
    navigate("/login", { replace: true });
  }

  const isChapter = step >= 1 && step <= total;
  const chapterIndex = isChapter ? step : 0; // 1..total

  function renderBody() {
    if (step === 0) {
      return <StepWelcome next={goNext} />;
    }
    if (step === lastIndex) {
      return <StepDone data={data} onCompleted={clearDraft} />;
    }
    const chapterIdx = step - 1; // 0-based index into chapterComponents
    const Chapter = chapterComponents[chapterIdx];
    if (!Chapter) {
      // Defensive — shouldn't happen.
      return <StepWelcome next={goNext} />;
    }
    return (
      <Chapter
        data={data}
        setField={setField}
        next={goNext}
        prev={goPrev}
      />
    );
  }

  return (
    <div className="ob">
      <header className="ob__chrome">
        <button
          type="button"
          className="ob__exit k-mono"
          onClick={() => void handleExit()}
        >
          ← Salir
        </button>
        <div className="ob__chrome-mark">
          <KlaraMark size={18} />
          <span className="k-mono ob__chrome-label">Klara</span>
        </div>
        <span className="ob__chrome-spacer" />
      </header>

      <main className="ob__main" data-step={step} data-direction={direction}>
        <aside className="ob__rail" aria-hidden="true">
          {isChapter && (
            <div className="ob__rail-inner">
              <span className="k-mono ob__rail-label">Capítulo</span>
              <span className="ob__rail-numeral">{roman(chapterIndex)}</span>
              <span className="k-mono ob__rail-of">de {roman(total)}</span>
            </div>
          )}
        </aside>

        <section className="ob__content" key={step}>
          {renderBody()}
        </section>

        <aside className="ob__margin">
          {isChapter && WHISPERS[chapterIndex] && (
            <div className="ob__whisper">
              <KlaraMark size={12} />
              <p className="ob__whisper-text">{WHISPERS[chapterIndex](data)}</p>
            </div>
          )}
        </aside>
      </main>

      {isChapter && (
        <footer className="ob__progress">
          <div className="ob__pips">
            {Array.from({ length: total }).map((_, i) => {
              const pos = i + 1;
              const state =
                pos < chapterIndex ? "done" : pos === chapterIndex ? "now" : "next";
              return <span key={i} className="ob__pip" data-state={state} />;
            })}
          </div>
        </footer>
      )}
    </div>
  );
}
