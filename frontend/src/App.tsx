import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Masthead from "./components/Masthead";
import ProtectedRoute from "./components/ProtectedRoute";
import Home from "./routes/Home";
import NewStory from "./routes/NewStory";
import StoryView from "./routes/Story";
import ReviewStub from "./routes/ReviewStub";
import ChatStub from "./routes/ChatStub";
import Settings from "./routes/Settings";
import Login from "./routes/Login";
import Signup from "./routes/Signup";
import ForgotPassword from "./routes/ForgotPassword";
import ResetPassword from "./routes/ResetPassword";
import VerifyEmail from "./routes/VerifyEmail";
import { useMastheadDate } from "./lib/dateLabel";
import { useTheme } from "./lib/preferences";
import { AuthProvider, useAuth } from "./lib/auth";

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
    <div className="kapp">
      <div className="kframe">
        <Masthead
          edition={edition}
          theme={theme}
          onToggleTheme={() => setTheme(theme === "light" ? "dark" : "light")}
        />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot" element={<ForgotPassword />} />
          <Route path="/reset" element={<ResetPassword />} />
          <Route path="/verify" element={<VerifyEmail />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Home />
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
            path="/story/:id"
            element={
              <ProtectedRoute>
                <StoryView />
              </ProtectedRoute>
            }
          />
          <Route
            path="/review"
            element={
              <ProtectedRoute>
                <ReviewStub />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatStub />
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
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
