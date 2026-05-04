import { Link } from "react-router-dom";

export default function ChatStub() {
  return (
    <div className="fade-in">
      <h2>Hablar con Klara</h2>
      <p className="muted">
        Próximamente: conversación libre en alemán con Klara — corregida, sin juicio.
      </p>
      <Link to="/" className="btn btn-ghost">
        ← Volver
      </Link>
    </div>
  );
}
