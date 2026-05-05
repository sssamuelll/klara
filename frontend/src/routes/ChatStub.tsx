import { useNavigate } from "react-router-dom";

export default function ChatStub() {
  const navigate = useNavigate();
  return (
    <main className="k-page placeholder">
      <button className="story__back k-mono" onClick={() => navigate("/")}>
        ← Volver
      </button>
      <div className="ph__head">
        <span className="k-mono">Hablar con Klara</span>
        <h1 className="ph__title">Próximamente.</h1>
        <p className="ph__dek">
          Conversación libre. Voz a voz, cuando estés listo.
        </p>
      </div>
    </main>
  );
}
