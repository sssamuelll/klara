import { Link, Route, Routes } from "react-router-dom";
import Home from "./routes/Home";
import NewStory from "./routes/NewStory";
import StoryView from "./routes/Story";
import ReviewStub from "./routes/ReviewStub";
import ChatStub from "./routes/ChatStub";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>
          <h1>Deutsch · Samuel</h1>
        </Link>
        <span className="subtitle">A0 → DTZ B1</span>
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/story/new" element={<NewStory />} />
        <Route path="/story/:id" element={<StoryView />} />
        <Route path="/review" element={<ReviewStub />} />
        <Route path="/chat" element={<ChatStub />} />
      </Routes>
    </div>
  );
}
