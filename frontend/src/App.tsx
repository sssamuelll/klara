import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Masthead from "./components/Masthead";
import Home from "./routes/Home";
import NewStory from "./routes/NewStory";
import StoryView from "./routes/Story";
import ReviewStub from "./routes/ReviewStub";
import ChatStub from "./routes/ChatStub";
import Settings from "./routes/Settings";
import { useMastheadDate } from "./lib/dateLabel";
import { useTheme } from "./lib/preferences";
import { useUser } from "./lib/user";

export default function App() {
  const [theme, setTheme] = useTheme();
  const { user } = useUser();
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
          <Route path="/" element={<Home />} />
          <Route path="/story/new" element={<NewStory />} />
          <Route path="/story/:id" element={<StoryView />} />
          <Route path="/review" element={<ReviewStub />} />
          <Route path="/chat" element={<ChatStub />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </div>
  );
}
