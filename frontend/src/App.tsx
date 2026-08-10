import { useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Masthead from "./components/Masthead";
import ProtectedRoute from "./components/ProtectedRoute";
import TabBar from "./components/TabBar";
import Inicio from "./routes/Inicio";
import Portada from "./routes/Portada";
import MapaCurso from "./routes/MapaCurso";
import Perfil from "./routes/Perfil";
import PerfilAprendizaje from "./perfil/PerfilAprendizaje";
import NuevoPlaceholder from "./routes/NuevoPlaceholder";
import Module from "./routes/Module";
import NewStory from "./routes/NewStory";
import StoryView from "./routes/Story";
import Practice from "./routes/Practice";
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

function V4Shell() {
  return (
    <div className="m3-app">
      <Outlet />
      <TabBar />
    </div>
  );
}

function AuthShell() {
  return (
    <div className="m3-app">
      <div className="m3-page auth-page">
        <header className="m3-top">
          <span className="marca">
            <span className="wordmark">Klara</span>
          </span>
        </header>
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
      <Route element={<V4Shell />}>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Inicio />
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

      <Route element={<LegacyShell theme={theme} setTheme={setTheme} edition={edition} />}>
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute>
              <Onboarding />
            </ProtectedRoute>
          }
        />
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
          path="/chat"
          element={
            <ProtectedRoute>
              <Speak />
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
          Story renderiza su propio .m3-app; StoryFinish interino trae su kframe. */}
      <Route
        path="/estudiar/:id"
        element={
          <ProtectedRoute>
            <StoryView />
          </ProtectedRoute>
        }
      />
      <Route path="/story/:id" element={<LegacyStoryRedirect />} />

      {/* ponytail: sin pantalla 404 — con el Masthead dentro de LegacyShell una URL
          suelta pinta en blanco; redirigir a Inicio es la respuesta correcta y barata. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
