import { Route, Routes } from "react-router-dom";
import Masthead from "./components/Masthead";
import Home from "./routes/Home";
import NewStory from "./routes/NewStory";
import StoryView from "./routes/Story";
import ReviewStub from "./routes/ReviewStub";
import ChatStub from "./routes/ChatStub";
import { mastheadDate } from "./lib/dateLabel";
import { useTheme } from "./lib/preferences";

export default function App() {
  const [theme, setTheme] = useTheme();
  const edition = mastheadDate();
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
        </Routes>
      </div>
    </div>
  );
}
