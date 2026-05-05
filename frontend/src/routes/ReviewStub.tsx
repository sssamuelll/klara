import { useNavigate } from "react-router-dom";

export default function ReviewStub() {
  const navigate = useNavigate();
  return (
    <main className="k-page placeholder">
      <button className="story__back k-mono" onClick={() => navigate("/")}>
        ← Volver
      </button>
      <div className="ph__head">
        <span className="k-mono">Repaso</span>
        <h1 className="ph__title">Próximamente.</h1>
        <p className="ph__dek">
          Klara repasa contigo las palabras de las historias que ya leíste. Sin contadores. Sin presión.
        </p>
      </div>
    </main>
  );
}
