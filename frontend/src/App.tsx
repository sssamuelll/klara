import { useEffect, type ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Masthead from "./components/Masthead";
import NativeChrome from "./components/NativeChrome";
import ProtectedRoute from "./components/ProtectedRoute";
import TabBar from "./components/TabBar";
import Landing from "./routes/Landing";
import Hoy from "./routes/Hoy";
import Biblioteca from "./routes/Biblioteca";
import Portada from "./routes/Portada";
import MapaCurso from "./routes/MapaCurso";
import Perfil from "./routes/Perfil";
import PerfilAprendizaje from "./perfil/PerfilAprendizaje";
import NuevoPlaceholder from "./routes/NuevoPlaceholder";
import Module from "./routes/Module";
import NewStory from "./routes/NewStory";
import StoryView from "./routes/Story";
import Taller from "./routes/Taller";
import Practice from "./routes/Practice";
import Pronunciar from "./routes/Pronunciar";
import Repaso from "./routes/Repaso";
import Speak from "./routes/Speak";
import Settings from "./routes/Settings";
import Onboarding from "./onboarding/Onboarding";
import GenderReview from "./routes/GenderReview";
import Login from "./routes/Login";
import Signup from "./routes/Signup";
import ForgotPassword from "./routes/ForgotPassword";
import ResetPassword from "./routes/ResetPassword";
import VerifyEmail from "./routes/VerifyEmail";
import { useMastheadDate } from "./lib/dateLabel";
import { isNative } from "./lib/native";
import { useTheme } from "./lib/preferences";
import { AuthProvider, useAuth } from "./lib/auth";

function LegacyShell({ theme, setTheme, edition }: {
  theme: "light" | "dark";
  setTheme: (t: "light" | "dark") => void;
  edition: string;
}) {
  return (
    <div className="kapp">
      <div className="kframe">
        <Masthead
          edition={edition}
          theme={theme}
          onToggleTheme={() => setTheme(theme === "light" ? "dark" : "light")}
        />
        <Outlet />
      </div>
    </div>
  );
}

function V4Frame({ children }: { children: ReactNode }) {
  return (
    <div className="k-app">
      {children}
      <TabBar />
    </div>
  );
}

function V4Shell() {
  return (
    <V4Frame>
      <Outlet />
    </V4Frame>
  );
}

function RootGate() {
  const { user, loading } = useAuth();
  // El cascarón vacío mientras se resuelve la sesión: pinta el papel a alto
  // completo y así la portada no entra desde un fondo distinto del suyo.
  if (loading) return <div className="k-app" />;
  if (!user) return <Landing />;
  return (
    <V4Frame>
      <ProtectedRoute>
        <Hoy />
      </ProtectedRoute>
    </V4Frame>
  );
}

function AuthShell() {
  return (
    <div className="k-app">
      <div className="k-page">
        <header className="k-topline">
          <span className="k-topline__mark">
            <span className="wordmark">Klara</span>
          </span>
        </header>
        {/* El scroll lo pone cada pantalla con su `.k-live`: la página del
            cascarón no scrollea (§7.3) y la tira de arriba se queda fija. */}
        <Outlet />
      </div>
    </div>
  );
}

// /story/:id → /estudiar/:id conservando el state del navigate original.
// Los deep-links y bookmarks legacy no se rompen (Global Constraint de URLs).
function LegacyStoryRedirect() {
  const { id } = useParams();
  const location = useLocation();
  return <Navigate to={`/estudiar/${id}`} replace state={location.state} />;
}

function AppShell() {
  const [theme, setTheme] = useTheme();
  const { user } = useAuth();
  const { i18n } = useTranslation();
  const edition = useMastheadDate();

  useEffect(() => {
    if (user && user.native_language && user.native_language !== i18n.language) {
      i18n.changeLanguage(user.native_language);
    }
  }, [user?.native_language, i18n]);

  return (
    <Routes>
      <Route path="/" element={<RootGate />} />

      <Route element={<V4Shell />}>
        <Route
          path="/biblioteca"
          element={
            <ProtectedRoute>
              <Biblioteca />
            </ProtectedRoute>
          }
        />
        <Route
          path="/curso/:id"
          element={
            <ProtectedRoute>
              <Portada />
            </ProtectedRoute>
          }
        />
        <Route
          path="/curso/:id/mapa"
          element={
            <ProtectedRoute>
              <MapaCurso />
            </ProtectedRoute>
          }
        />
        <Route
          path="/perfil"
          element={
            <ProtectedRoute>
              <Perfil />
            </ProtectedRoute>
          }
        />
        <Route
          path="/perfil/aprendizaje"
          element={
            <ProtectedRoute>
              <PerfilAprendizaje />
            </ProtectedRoute>
          }
        />
        <Route
          path="/nuevo"
          element={
            <ProtectedRoute>
              <NuevoPlaceholder />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route element={<AuthShell />}>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/forgot" element={<ForgotPassword />} />
        <Route path="/reset" element={<ResetPassword />} />
        <Route path="/verify" element={<VerifyEmail />} />
      </Route>

      {/* Onboarding sale de LegacyShell: pinta su propio .k-app (100dvh) y ese
          armazón no se puede anidar dentro de .kframe. De paso deja de asomar
          el Masthead de la app a quien todavía no ha entrado en ella. */}
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute>
            <Onboarding />
          </ProtectedRoute>
        }
      />

      <Route element={<LegacyShell theme={theme} setTheme={setTheme} edition={edition} />}>
        <Route
          path="/story/new"
          element={
            <ProtectedRoute>
              <NewStory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/module/:id"
          element={
            <ProtectedRoute>
              <Module />
            </ProtectedRoute>
          }
        />
        <Route
          path="/review"
          element={
            <ProtectedRoute>
              <Practice />
            </ProtectedRoute>
          }
        />
        <Route
          path="/gender"
          element={
            <ProtectedRoute>
              <GenderReview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Sesión v4: sin TabBar (mockup) y sin LegacyShell (sin Masthead).
          Story y su cierre (StoryFinish) pintan su propio .k-app. */}
      <Route
        path="/estudiar/:id"
        element={
          <ProtectedRoute>
            <StoryView />
          </ProtectedRoute>
        }
      />
      <Route path="/story/:id" element={<LegacyStoryRedirect />} />

      {/* Repaso: la misma superficie suelta que /estudiar/:id — pinta su propio
          .k-app y el armazón de sesión no se puede anidar en .kframe. */}
      <Route
        path="/repaso"
        element={
          <ProtectedRoute>
            <Repaso />
          </ProtectedRoute>
        }
      />

      {/* Pronunciar: la misma superficie suelta que /repaso. Práctica se
          quedó con el selector y navega aquí; el flujo entero (preparar,
          sesión, resumen) vive en la ruta porque comparten la cola. */}
      <Route
        path="/pronunciar"
        element={
          <ProtectedRoute>
            <Pronunciar />
          </ProtectedRoute>
        }
      />

      {/* Hablar: la misma superficie suelta que /repaso — pinta su propio
          .k-app y el armazón de sesión no se puede anidar en .kframe. */}
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <Speak />
          </ProtectedRoute>
        }
      />

      {/* El taller (F0): suelta fuera de V4Shell, como /estudiar/:id — el
          taller es su propia superficie, no un panel dentro del shell móvil. */}
      <Route
        path="/taller"
        element={
          <ProtectedRoute>
            <Taller />
          </ProtectedRoute>
        }
      />
      {/* ponytail: sin pantalla 404 — con el Masthead dentro de LegacyShell una URL
          suelta pinta en blanco; redirigir a Inicio es la respuesta correcta y barata. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      {isNative() && <NativeChrome />}
      <AppShell />
    </AuthProvider>
  );
}
